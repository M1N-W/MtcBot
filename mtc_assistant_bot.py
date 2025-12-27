# -*- coding: utf-8 -*-
"""
MTC Assistant v.17 ปลายภาคเทอม 2
"""

# --- 1. Imports ---
import os
import datetime
import logging
import re
import json
import math
from typing import Optional
from zoneinfo import ZoneInfo

import requests
from flask import Flask, request, abort

import google.generativeai as genai
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, ImageMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

# ==========================================================================================
# --- 2. Configuration & Constants ---
# ==========================================================================================
app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Credentials (from environment) ---
ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not ACCESS_TOKEN:
    app.logger.warning("CHANNEL_ACCESS_TOKEN is not set. LINE API calls will fail.")
if not CHANNEL_SECRET:
    app.logger.warning("CHANNEL_SECRET is not set. Signature verification will fail.")
if not GEMINI_API_KEY:
    app.logger.info("GEMINI_API_KEY is not set. AI features will be disabled.")

# --- Bot Constants & Links ---
WORKSHEET_LINK = "https://docs.google.com/spreadsheets/d/1SwKs4s8HJt2HxAzj_StIh_nopVMe1kwqg7yW13jOdQ4/edit?usp=sharing"
SCHOOL_LINK = "https://www.ben.ac.th/main/"
TIMETABLE_IMG = "https://img5.pic.in.th/file/secure-sv1/-2395abd52df9b5e08.jpg"
GRADE_LINK = "http://www.dograde2.online/bjrb/"
ABSENCE_LINK = "https://forms.gle/WjCBTYNxEeCpHShr9"
Bio_LINK = "https://drive.google.com/file/d/1zd5NND3612JOym6HSzKZnqAS42TH9gmh/view?usp=sharing"
Physic_LINK = "https://drive.google.com/file/d/15oSPs3jFYpvJRUkFqrCSpETGwOoK0Qpv/view?usp=sharing"

EXAM_DATES = {
    "กลางภาค": datetime.date(2025, 12, 21),
    "ปลายภาค": datetime.date(2026, 2, 20)
}

LINE_MAX_TEXT = 5000
LINE_SAFE_TRUNCATE = 4800
LOCAL_TZ = ZoneInfo("Asia/Bangkok")

# --- Class Schedule Data ---
SCHEDULE = {
    0: [ # วันจันทร์
        {"start": "08:30", "end": "09:25", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "331"},
        {"start": "09:25", "end": "10:20", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "331"},
        {"start": "10:20", "end": "11:15", "subject": "เคมี (ครูพิทยาภรณ์)", "room": "311"},
        {"start": "11:15", "end": "12:10", "subject": "แนะแนว (ครูทศพร)", "room": "947"},
        {"start": "13:05", "end": "14:00", "subject": "นาฏศิลป์ (ครูบังเอิญ)", "room": "575"},
        {"start": "14:00", "end": "14:55", "subject": "การงานอาชีพ (ครูอัญชลี)", "room": "947"},
        {"start": "14:55", "end": "15:50", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start": "15:50", "end": "16:45", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
    ],
    1: [ # วันอังคาร
        {"start": "08:30", "end": "09:25", "subject": "เคมี (ครูพิทยาภรณ์)", "room": "311"},
        {"start": "09:25", "end": "10:20", "subject": "เคมี (ครูพิทยาภรณ์)", "room": "311"},
        {"start": "10:20", "end": "11:15", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "333"},
        {"start": "11:15", "end": "12:10", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "333"},
        {"start": "13:05", "end": "14:00", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start": "14:00", "end": "14:55", "subject": "สังคมศึกษา (ครูบังอร)", "room": "947"},
        {"start": "14:55", "end": "15:50", "subject": "ไทย (ครูเบญจมาศ)", "room": "947"},
        {"start": "15:50", "end": "16:45", "subject": "อังกฤษพื้นฐาน (ครูวาสนา)", "room": "947"},
    ],
    2: [ # วันพุธ
        {"start": "08:30", "end": "09:25", "subject": "อังกฤษพื้นฐาน (ครูวาสนา)", "room": "947"},
        {"start": "09:25", "end": "10:20", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start": "10:20", "end": "11:15", "subject": "ประวัติศาสตร์ (ครูณฐพร)", "room": "947"},
        {"start": "11:15", "end": "12:10", "subject": "คณิตพื้นฐาน (ครูปรียา)", "room": "947"},
    ],
    3: [ # วันพฤหัสบดี
        {"start": "08:30", "end": "09:25", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start": "09:25", "end": "10:20", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start": "10:20", "end": "11:15", "subject": "ชีววิทยา (ครูพิชามญช์)", "room": "323"},
        {"start": "11:15", "end": "12:10", "subject": "ไทย (ครูเบญจมาศ)", "room": "947"},
        {"start": "13:05", "end": "14:00", "subject": "สุขศึกษา&พละศึกษา (ครูนรเศรษฐ์)", "room": "ห้องเรียน/โดม"},
        {"start": "14:00", "end": "14:55", "subject": "อังกฤษเพิ่มเติม (Teacher Mitch)", "room": "947"},
        {"start": "14:55", "end": "15:50", "subject": "คณิตพื้นฐาน (ครูปรียา)", "room": "947"},
    ],
    4: [ # วันศุกร์
        {"start": "08:30", "end": "09:25", "subject": "ชีววิทยา (ครูพิชามญช์)", "room": "323"},
        {"start": "09:25", "end": "10:20", "subject": "ชีววิทยา (ครูพิชามญช์)", "room": "323"},
        {"start": "10:20", "end": "11:15", "subject": "อังกฤษพื้นฐาน (ครูวาสนา)", "room": "947"},
        {"start": "11:15", "end": "12:10", "subject": "สังคมศึกษา (ครูบังอร)", "room": "947"},
        {"start": "13:05", "end": "14:00", "subject": "คอมพิวเตอร์ (ครูจินดาพร)", "room": "221"},
        {"start": "14:00", "end": "14:55", "subject": "คอมพิวเตอร์ (ครูจินดาพร)", "room": "221"},
        {"start": "14:55", "end": "15:50", "subject": "IS (ครูปรียา)", "room": "947"},
        {"start": "15:50", "end": "16:45", "subject": "IS (ครูปรียา)", "room": "947"},
    ]
}

# ==========================================================================================
# --- 3. Initialize APIs ---
# ==========================================================================================
configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
gemini_model = None
GEMINI_MODEL_NAME = "gemini-3-flash-preview"

try:
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        try:
            gemini_model = getattr(genai, "GenerativeModel")(GEMINI_MODEL_NAME)
            app.logger.info("Gemini model instantiated via GenerativeModel.")
        except Exception:
            gemini_model = None
            app.logger.info("Gemini API configured, will use function-level calls as fallback.")
    else:
        app.logger.warning("GEMINI_API_KEY is not set. AI features will be disabled.")
except Exception as e:
    app.logger.error(f"Error configuring Gemini AI: {e}", exc_info=True)
    gemini_model = None

# ==========================================================================================
# --- 4. Core Helper Functions ---
# ==========================================================================================

def get_next_class_info() -> str:
    """Checks the schedule and returns a string with the next class information."""
    now = datetime.datetime.now(tz=LOCAL_TZ)
    weekday = now.weekday()
    current_time = now.time()

    if weekday not in SCHEDULE:
        return "วันนี้วันหยุดไม่ใช่วันเรียน กลับไปนอนเถอะ 🎉"

    for period in SCHEDULE[weekday]:
        start_time = datetime.datetime.strptime(period["start"], "%H:%M").time()
        if current_time < start_time:
            return (f"คาบต่อไป มีรายละเอียดดังนี้ครับ\n"
                    f"เริ่มคาบ : {period['start']}\n"
                    f"จบคาบ : {period['end']}\n"
                    f"วิชา : {period['subject']}\n"
                    f"ห้อง : {period['room']}")
    return "วันนี้ไม่มีคาบเรียนแล้วครับ กลับบ้านไปนอนได้ 🏠"

def create_countdown_message(exam_name: str, exam_date: datetime.date) -> str:
    """Calculates days left until an exam and returns a formatted string."""
    today = datetime.datetime.now(tz=LOCAL_TZ).date()
    delta = exam_date - today
    days_left = delta.days

    if days_left > 0:
        return f"เหลืออีก {days_left} วันจะถึงวันสอบ{exam_name} ({exam_date.strftime('%d %b %Y')})"
    elif days_left == 0:
        return f"วันนี้วันสอบ{exam_name}แล้ว โชคดีนะครับ :)"
    else:
        return f"การสอบ{exam_name}ได้สิ้นสุดลงแล้วครับ"

def _safe_parse_gemini_response(response) -> str:
    """Defensively extract text from various SDK response shapes."""
    try:
        if response is None:
            return ""
        if hasattr(response, 'parts') and response.parts:
             return "".join(part.text for part in response.parts if hasattr(part, 'text')).strip()
        if hasattr(response, "text"):
            return str(response.text).strip()
        if isinstance(response, dict):
            if "text" in response and response["text"]:
                return str(response["text"]).strip()
            if "candidates" in response and response["candidates"]:
                first_candidate = response["candidates"][0]
                if isinstance(first_candidate, dict):
                    if "content" in first_candidate and isinstance(first_candidate["content"], dict):
                        if "parts" in first_candidate["content"] and first_candidate["content"]["parts"]:
                             return "".join(p.get("text", "") for p in first_candidate["content"]["parts"]).strip()
                    if "text" in first_candidate: 
                         return str(first_candidate["text"]).strip()
                return str(first_candidate).strip() 
        if hasattr(response, "result"):
            return str(getattr(response, "result")).strip()
        if hasattr(response, "candidates") and response.candidates:
             first_candidate_obj = response.candidates[0]
             if hasattr(first_candidate_obj, 'content') and hasattr(first_candidate_obj.content, 'parts') and first_candidate_obj.content.parts:
                 return "".join(part.text for part in first_candidate_obj.content.parts if hasattr(part, 'text')).strip()
             if hasattr(first_candidate_obj, 'text'):
                 return str(getattr(first_candidate_obj, 'text')).strip()
             return str(first_candidate_obj).strip()

        return str(response).strip() 
    except Exception as e:
        app.logger.debug(f"Error parsing Gemini response: {e}", exc_info=True)
        return str(response) 

def get_gemini_response(user_message: str) -> str:
    """Gets a response from the Gemini AI model and post-processes it to enforce bot persona."""
    identity_msg = (
        "ผมเป็นบอทผู้ช่วยอเนกประสงค์ของห้อง MTC ม.4/2 "
        "ผมช่วยได้หลายอย่าง เช่น แจ้งตาราง, ลิงก์เว็บโรงเรียน, หาตารางสอน, และช่วยหาข้อมูลทั่วไปด้วย AI"
    )

    identity_queries = ["คุณคือใคร", "เป็นใคร", "who are you", "คุณชื่ออะไร", "ชื่ออะไร", "ตัวตน"]
    lowered = user_message.lower()
    if any(q in lowered for q in identity_queries):
        return identity_msg

    if not GEMINI_API_KEY:
        return "ขออภัยครับ ระบบ AI ของส่วนนี้ยังไม่สมบูรณ์"

    try:
        response = None
        # --- Attempt 1: Use instantiated model if available ---
        if gemini_model is not None:
            try:
                if hasattr(gemini_model, "generate_content"):
                    response = gemini_model.generate_content(user_message)
                elif hasattr(gemini_model, "generate"): # Older SDK method
                    response = gemini_model.generate(user_message)
            except Exception as model_e:
                app.logger.warning(f"Instantiated Gemini model call failed: {model_e}", exc_info=True)
                response = None # Fallback to module-level

        # --- Attempt 2: Use module-level calls as fallback ---
        if response is None:
            try:
                if hasattr(genai, "generate_content"):
                     response = genai.generate_content(model=GEMINI_MODEL_NAME, contents=user_message)
                elif hasattr(genai, "generate_text"):
                    response = genai.generate_text(model=GEMINI_MODEL_NAME, prompt=user_message)
                else:
                     app.logger.warning("Neither generate_content nor generate_text found at module level.")
                     response = None
            except Exception as module_e:
                app.logger.error(f"Gemini module-level call failed: {module_e}", exc_info=True)
                response = None

        reply_text = _safe_parse_gemini_response(response)
        if not reply_text:
            return "ขออภัยครับ ระบบ AI ตอบไม่ได้ในขณะนี้ ลองใหม่อีกครั้ง"

        # --- Post-processing ---
        reply_text = re.sub(r'\b[Gg]oogle\b', 'Gemini', reply_text)
        reply_text = reply_text.replace('กูเกิล', 'Gemini')

        if re.search(r'(แบบจำลอง|ฝึกโดย|ฝึกอบรม|trained by|model)', reply_text, flags=re.IGNORECASE):
            lines = reply_text.splitlines()
            filtered_lines = [ln for ln in lines if not re.search(r'(แบบจำลอง|ฝึกโดย|ฝึกอบรม|trained by|model)', ln, flags=re.IGNORECASE)]
            remaining = "\n".join(filtered_lines).strip()
            reply_text = identity_msg
            if remaining:
                reply_text = reply_text + "\n\n" + remaining

        if len(reply_text) > LINE_SAFE_TRUNCATE:
            reply_text = reply_text[:LINE_SAFE_TRUNCATE] + "... (ระบบตัดข้อความที่ยาวเกิน 5,000 คำโดยอัตโนมัติ)"

        return reply_text
    except Exception as e:
        app.logger.error(f"General Gemini API Error: {e}", exc_info=True)
        return "ขออภัยครับ ตอนนี้ผมมีปัญหาในการเชื่อมต่อกับ AI ลองใหม่อีกครั้งนะ"


def reply_to_line(reply_token: str, messages: list):
    """Sends a reply message to the LINE user."""
    if not messages:
        app.logger.warning("reply_to_line called with no messages.")
        return
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            response = line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(reply_token=reply_token, messages=messages)
            )
            if response.status_code != 200:
                 app.logger.error(f"Error sending reply to LINE (Status: {response.status_code}): {response.body}")

    except Exception as e:
        app.logger.error(f"Error sending reply to LINE: {e}", exc_info=True)


# ==========================================================================================
# --- 5. Command-Specific Action Functions ---
# ==========================================================================================
def get_worksheet_message():
    return TextMessage(text=f'นี่คือตารางเช็คงานห้องเรานะครับ\n{WORKSHEET_LINK}')

def get_school_link_message():
    return TextMessage(text=f'นี่คือลิงก์เว็บโรงเรียนนะครับ\n{SCHOOL_LINK}')

def get_timetable_image_message():
    return ImageMessage(original_content_url=TIMETABLE_IMG, preview_image_url=TIMETABLE_IMG)

def get_grade_link_message():
    return TextMessage(text=f'นี่คือลิงก์เว็บดูเกรดนะครับ\n{GRADE_LINK}')

def get_next_class_message():
    return TextMessage(text=get_next_class_info())

def get_absence_form_message():
    return TextMessage(text=f'นี่คือแบบฟอร์มลากิจ-ลาป่วยนะครับ\n{ABSENCE_LINK}')

def get_bio_link_message():
    return TextMessage(text=f'นี่คือเฉลยชีวะ บทที่ 4-7 นะครับ\n{Bio_LINK}')

def get_physic_link_message():
    return TextMessage(text=f'นี่คือเฉลยฟิสิกส์นะครับ\n{Physic_LINK}')


def get_help_message():
    help_text = (
        'คำสั่งทั้งหมด\n'
        '- "งาน" = ดูตารางงาน (worksheet)\n'
        '- "เว็บ" = เข้าเว็บโรงเรียน\n'
        '- "ตารางสอน" = ตารางสอนเทอม 2 ห้อง 4/2\n'
        '- "เกรด" = เข้าเว็บเช็คเกรด\n'
        '- "คาบต่อไป/เรียนไรต่อ" = เช็คคาบถัดไปแบบเรียลไทม์\n'
        '- "อีกกี่นาที/เหลือเวลา/เช็คเวลา" = เช็คเวลาคาบต่อไป (แบบข้ามคาบซ้ำ)\n'
        '- "ลาป่วย/ลากิจ/ลา" = แบบฟอร์มลากิจ-ลาป่วย\n'
        '- "สอบ" = นับถอยหลังวันสอบ\n'
        '- "อีกกี่นาที" = เช็คว่าอีกกี่นาทีจะถึงคาบถัดไปแบบเรียลไทม์\n'
        '- "ชีวะ" = เฉลยชีวะ\n'
        '- "ฟิสิกส์" = เฉลยฟิสิกส์\n'
        '- ถ้าพิมพ์ข้อความอื่น ๆ ผมจะตอบด้วยเอไอ'
    )
    return TextMessage(text=help_text)
    
def get_exam_countdown_message(user_message: str):
    if "กลางภาค" in user_message:
        reply_text = create_countdown_message("กลางภาค", EXAM_DATES["กลางภาค"])
    elif "ปลายภาค" in user_message:
        reply_text = create_countdown_message("ปลายภาค", EXAM_DATES["ปลายภาค"])
    else:
        midterm = create_countdown_message("กลางภาค", EXAM_DATES["กลางภาค"]) if "กลางภาค" in EXAM_DATES else ""
        final = create_countdown_message("ปลายภาค", EXAM_DATES["ปลายภาค"]) if "ปลายภาค" in EXAM_DATES else ""
        if midterm and final:
            reply_text = f"{midterm}\n\n{final}"
        else:
            reply_text = midterm or final or "ไม่พบวันสอบในระบบครับ"
    return TextMessage(text=reply_text)

# ==========================================================================================
# --- New: Time-until-next-class helper ---
# ==========================================================================================
def get_time_until_next_class_message(user_message: str = ""):
    """
    คำนวณจำนวนเวลาที่เหลือจนถึงคาบถัดไป (ข้ามคาบที่เป็นวิชาเดียวกันติดกัน)
    คืนค่าเป็น TextMessage ในรูปแบบ:
    เหลือเวลาอีก... ถึงจะเริ่มคาบถัดไปครับ
    คาบถัดไปคือ [วิชา(คุณครู)]
    ห้อง ...
    """
    now = datetime.datetime.now(tz=LOCAL_TZ)
    weekday = now.weekday()
    current_time = now.time()

    if weekday not in SCHEDULE:
        return TextMessage(text="วันนี้วันหยุดไม่ใช่วันเรียน กลับไปนอนไป๊ 🎉")

    periods = SCHEDULE[weekday]

    current_index = None
    for idx, period in enumerate(periods):
        start_t = datetime.datetime.strptime(period["start"], "%H:%M").time()
        end_t = datetime.datetime.strptime(period["end"], "%H:%M").time()
        if start_t <= current_time < end_t:
            current_index = idx
            break

    if current_index is None:
        for idx, period in enumerate(periods):
            start_t = datetime.datetime.strptime(period["start"], "%H:%M").time()
            if current_time < start_t:
                target_idx = idx
                target = period
                break
        else:
            return TextMessage(text="วันนี้ไม่มีคาบเรียนอีกแล้วครับ กลับบ้านได้เลย 🏠")
    else:
        current_subject = periods[current_index]["subject"]
        target_idx = None
        for idx in range(current_index + 1, len(periods)):
            if periods[idx]["subject"] != current_subject:
                target_idx = idx
                break
        if target_idx is None:
            return TextMessage(text="วันนี้ไม่มีคาบเรียนที่ต่างจากคาบปัจจุบันอีกแล้วครับ")
        target = periods[target_idx]

    target_start_time = datetime.datetime.strptime(target["start"], "%H:%M").time()
    target_dt = datetime.datetime.combine(now.date(), target_start_time).replace(tzinfo=LOCAL_TZ)
    delta_seconds = (target_dt - now).total_seconds()
    if delta_seconds <= 0:
        minutes_left = 0
    else:
        minutes_left = max(0, math.ceil(delta_seconds / 60))

    if minutes_left == 0:
        minutes_text = "น้อยกว่า 1 นาที"
    else:
        minutes_text = f"{minutes_left} นาที"

    subject = target.get("subject", "ไม่ระบุวิชา")
    room = target.get("room", "ไม่ระบุห้อง")

    reply = (
        f'เหลือเวลาอีก {minutes_text}\n'
        f'คาบถัดไปคือ {subject}\n'
        f'ห้อง {room}'
    )
    return TextMessage(text=reply)

# ==========================================================================================
# --- 6. LINE Bot Event Handlers & Command Matching ---
# ==========================================================================================
@handler.add(FollowEvent)
def handle_follow(event):
    welcome_message = TextMessage(
        text='สวัสดีคับ! ผมคือ MTC Assistant ผู้ช่วยอเนกประสงค์ของห้อง ม.4/2\n'
             'คุณจะลองพิมพ์คำสั่งต่างๆ หรือจะคุยเล่นกับผมก็ได้นะ!\n\n'
             'พิมพ์ "คำสั่ง" เพื่อดูรายการคำสั่งทั้งหมดนะครับ'
    )
    reply_to_line(event.reply_token, [welcome_message])

COMMANDS = [
    (("งาน", "การบ้าน", "เช็คงาน"), get_worksheet_message),
    (("เว็บโรงเรียน", "เว็บ"), get_school_link_message),
    (("ตารางเรียน", "ตารางสอน"), get_timetable_image_message),
    (("เกรด", "ดูเกรด"), get_grade_link_message),
    (("คาบต่อไป", "เรียนอะไร", "เรียนไรต่อ"), get_next_class_message),
    (("อีกกี่นาที", "เหลือเวลา", "เช็คเวลา"), lambda msg: get_time_until_next_class_message(msg)),
    (("ลาป่วย", "ลากิจ", "ลา"), get_absence_form_message),
    (("ชีวะ", "เฉลยชีวะ"), get_bio_link_message),
    (("ฟิสิกส์", "เฉลยฟิสิกส์"), get_physic_link_message),
    (("เปิดเพลง", "หาเพลง", "ขอเพลง"), lambda msg: get_music_link_message(msg)),
    (("คำสั่ง", "help", "ช่วยเหลือ"), get_help_message),
    (("สอบ",), lambda msg: get_exam_countdown_message(msg)),
]

def _keyword_matches(user_message: str, keyword: str) -> bool:
    """Matches keyword as a whole word, even for Thai."""
    try:
        kw = keyword.lower()
        um = user_message.lower()

        pattern = rf'(?<![\w\u0E00-\u0E7F]){re.escape(kw)}(?![\w\u0E00-\u0E7F])'

        return bool(re.search(pattern, um, flags=re.IGNORECASE))
    except re.error:
        app.logger.warning(f"Regex error for keyword '{keyword}'. Falling back to substring match.")
        return keyword in user_message 

def call_action(action, user_message: str):
    """Safely call an action that may accept 0 or 1 arguments."""
    try:
        return action(user_message)
    except TypeError:
        try:
            return action()
        except TypeError:
             app.logger.error(f"Action {action.__name__} failed both 0 and 1 arg calls.")
             return action(user_message) 

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = getattr(event.message, "text", "")
    user_message = user_text.strip() 
    user_message_lower = user_message.lower()
    reply_message = None

    for keywords, action in COMMANDS:
        matched = False
        for keyword in sorted(keywords, key=len, reverse=True):
            if _keyword_matches(user_message_lower, keyword.lower()):
                try:
                    reply_message = call_action(action, user_message)
                except Exception as e:
                    app.logger.error(f"Error executing action for keyword '{keyword}': {e}", exc_info=True)
                    reply_message = TextMessage(text="ขออภัยครับ เกิดข้อผิดพลาดขณะประมวลผลคำสั่งของคุณ")
                matched = True
                break
        if matched:
            break

    if not reply_message:
        ai_response_text = get_gemini_response(user_message)
        reply_message = TextMessage(text=ai_response_text)

    if reply_message:
        reply_to_line(event.reply_token, [reply_message])
    else:
        app.logger.warning(f"No reply was generated for message: {user_message}")

# ==========================================================================================
# --- 7. Flask Web Server ---
# ==========================================================================================
@app.route("/callback", methods=['POST'])
def callback():
    """Webhook endpoint for LINE platform."""
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        app.logger.error("Missing X-Line-Signature header.")
        abort(400)
    body = request.get_data(as_text=True)
    app.logger.info(f"Request body: {body}")
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature. Please check your channel secret.")
        abort(400)
    except Exception as e:
        app.logger.error(f"Error handling request: {e}", exc_info=True)
        abort(500)
    return 'OK'

@app.route("/", methods=['GET'])
def home():
    """A simple endpoint to check if the server is running."""
    cfg_ok = "OK" if ACCESS_TOKEN and CHANNEL_SECRET else "CONFIG_MISSING"
    gemini_status = "OK" if GEMINI_API_KEY else "MISSING"
    return f"MTC Assistant v15 is running! LINE Config: {cfg_ok}, Gemini Config: {gemini_status}"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5001))
    debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug_mode)
