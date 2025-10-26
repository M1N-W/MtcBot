# -*- coding: utf-8 -*-
"""
MTC Assistant v14 - Song Searching Feature + YouTube validation
"""

# --- 1. Imports ---
import os
import datetime
import logging
import re
import json
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
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')  # Optional but highly recommended

if not ACCESS_TOKEN:
    app.logger.warning("CHANNEL_ACCESS_TOKEN is not set. LINE API calls will fail.")
if not CHANNEL_SECRET:
    app.logger.warning("CHANNEL_SECRET is not set. Signature verification will fail.")
if not GEMINI_API_KEY:
    app.logger.info("GEMINI_API_KEY is not set. AI features will be disabled.")
if not YOUTUBE_API_KEY:
    app.logger.info("YOUTUBE_API_KEY is not set. YouTube validation will use fallback (less reliable).")

# --- Bot Constants & Links ---
WORKSHEET_LINK = "https://docs.google.com/spreadsheets/d/1oCG--zkyp-iyJ8iFKaaTrDZji_sds2VzLWNxOOh7-xk/edit?usp=sharing"
SCHOOL_LINK = "https://www.ben.ac.th/main/"
TIMETABLE_IMG = "https://img5.pic.in.th/file/secure-sv1/-2395abd52df9b5e08.jpg"
GRADE_LINK = "http://www.dograde2.online/bjrb/"
ABSENCE_LINK = "https://forms.gle/WjCBTYNxEeCpHShr9"
Bio_LINK = "https://drive.google.com/file/d/1zd5NND3612JOym6HSzKZnqAS42TH9gmh/view?usp=sharing"

EXAM_DATES = {
    "กลางภาค": datetime.date(2025, 12, 20),
    "ปลายภาค": datetime.date(2026, 2, 20)
}

LINE_MAX_TEXT = 5000
LINE_SAFE_TRUNCATE = 4800
LOCAL_TZ = ZoneInfo("Asia/Bangkok")

# --- Class schedule omitted for brevity (same as before) ---
SCHEDULE = {
    0: [
        {"start": "08:30", "end": "09:25", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "331"},
        {"start": "09:25", "end": "10:20", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "331"},
        {"start": "10:20", "end": "11:15", "subject": "เคมี (ครูพิทยาภรณ์)", "room": "311"},
        {"start": "11:15", "end": "12:10", "subject": "แนะแนว (ครูทศพร)", "room": "947"},
        {"start": "13:05", "end": "14:00", "subject": "นาฏศิลป์ (ครูบังเอิญ)", "room": "575"},
        {"start": "14:00", "end": "14:55", "subject": "การงานอาชีพ (ครูอัญชลี)", "room": "947"},
        {"start": "14:55", "end": "15:50", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start": "15:50", "end": "16:45", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
    ],
    1: [
        {"start": "08:30", "end": "09:25", "subject": "เคมี (ครูพิทยาภรณ์)", "room": "311"},
        {"start": "09:25", "end": "10:20", "subject": "เคมี (ครูพิทยาภรณ์)", "room": "311"},
        {"start": "10:20", "end": "11:15", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "333"},
        {"start": "11:15", "end": "12:10", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "333"},
        {"start": "13:05", "end": "14:00", "subject": "คณิตเพิ่มพูน (ครูมานพ)", "room": "947"},
        {"start": "14:00", "end": "14:55", "subject": "สังคมศึกษา (ครูบังอร)", "room": "947"},
        {"start": "14:55", "end": "15:50", "subject": "ไทย (ครูเบญจมาศ)", "room": "947"},
        {"start": "15:50", "end": "16:45", "subject": "อังกฤษพื้นฐาน (ครูวาสนา)", "room": "947"},
    ],
    2: [
        {"start": "08:30", "end": "09:25", "subject": "อังกฤษพื้นฐาน (ครูวาสนา)", "room": "947"},
        {"start": "09:25", "end": "10:20", "subject": "คณิตเพิ่มพูน (ครูมานพ)", "room": "947"},
        {"start": "10:20", "end": "11:15", "subject": "ประวัติศาสตร์ (ครูณฐพร)", "room": "947"},
        {"start": "11:15", "end": "12:10", "subject": "คณิตพื้นฐาน (ครูปรียา)", "room": "947"},
    ],
    3: [
        {"start": "08:30", "end": "09:25", "subject": "คณิตเพิ่มพูน (ครูมานพ)", "room": "947"},
        {"start": "09:25", "end": "10:20", "subject": "คณิตเพิ่มพูน (ครูมานพ)", "room": "947"},
        {"start": "10:20", "end": "11:15", "subject": "ชีววิทยา (ครูพิชามญช์)", "room": "323"},
        {"start": "11:15", "end": "12:10", "subject": "ไทย (ครูเบญจมาศ)", "room": "947"},
        {"start": "13:05", "end": "14:00", "subject": "สุขศึกษา&พละศึกษา (ครูนรเศรษฐ์)", "room": "ห้องเรียน/โดม"},
        {"start": "14:00", "end": "14:55", "subject": "อังกฤษเพิ่มเติม (Teacher Mitch)", "room": "947"},
        {"start": "14:55", "end": "15:50", "subject": "คณิตพื้นฐาน (ครูปรียา)", "room": "947"},
    ],
    4: [
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
GEMINI_MODEL_NAME = "gemini-2.5-flash"

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
    now = datetime.datetime.now(tz=LOCAL_TZ)
    weekday = now.weekday()
    current_time = now.time()

    if weekday not in SCHEDULE:
        return "วันนี้วันหยุดไม่ใช่วันเรียน กลับไปนอนไป๊ 🎉"

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
    try:
        if response is None:
            return ""
        if hasattr(response, "text"):
            return str(response.text).strip()
        if isinstance(response, dict):
            if "text" in response and response["text"]:
                return str(response["text"]).strip()
            if "candidates" in response and response["candidates"]:
                first = response["candidates"][0]
                if isinstance(first, dict) and "content" in first:
                    return str(first["content"]).strip()
                return str(first).strip()
        if hasattr(response, "result"):
            return str(getattr(response, "result")).strip()
        if hasattr(response, "candidates"):
            c = getattr(response, "candidates")
            if c:
                first = c[0]
                if hasattr(first, "content"):
                    return str(getattr(first, "content")).strip()
                return str(first).strip()
        return str(response).strip()
    except Exception as e:
        app.logger.debug(f"Error parsing Gemini response: {e}", exc_info=True)
        return str(response)

def get_gemini_response(user_message: str) -> str:
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
        if gemini_model is not None:
            if hasattr(gemini_model, "generate_content"):
                response = gemini_model.generate_content(user_message)
            elif hasattr(gemini_model, "generate"):
                response = gemini_model.generate(user_message)
            else:
                response = None

        if response is None:
            try:
                if hasattr(genai, "generate_text"):
                    response = genai.generate_text(model=GEMINI_MODEL_NAME, input=user_message)
                elif hasattr(genai, "chat"):
                    chat_create = getattr(genai, "chat").create if hasattr(genai.chat, "create") else getattr(genai.chat, "generate", None)
                    if chat_create:
                        response = chat_create(model=GEMINI_MODEL_NAME, messages=[{"role": "user", "content": user_message}])
                    else:
                        response = None
                else:
                    if hasattr(genai, "generate"):
                        response = genai.generate(model=GEMINI_MODEL_NAME, prompt=user_message)
                    else:
                        response = None
            except Exception as e:
                app.logger.debug(f"Gemini module-level call failed: {e}", exc_info=True)
                response = None

        reply_text = _safe_parse_gemini_response(response)
        if not reply_text:
            return "ขออภัยครับ ระบบ AI ตอบไม่ได้ในขณะนี้ ลองใหม่อีกครั้ง"

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
        app.logger.error(f"Gemini API Error: {e}", exc_info=True)
        return "ขออภัยครับ ตอนนี้ผมมีปัญหาในการเชื่อมต่อกับ AI ลองใหม่อีกครั้งนะ"

def reply_to_line(reply_token: str, messages: list):
    if not messages:
        app.logger.warning("reply_to_line called with no messages.")
        return
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(reply_token=reply_token, messages=messages)
            )
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

def get_help_message():
    help_text = (
        'คำสั่งทั้งหมด\n'
        '- "งาน" = ดูตารางงาน (worksheet)\n'
        '- "เว็บ" = เข้าเว็บโรงเรียน\n'
        '- "ตารางสอน" = ตารางสอนเทอม 2 ห้อง 4/2\n'
        '- "เกรด" = เข้าเว็บเช็คเกรด\n'
        '- "คาบต่อไป/เรียนไรต่อ" = เช็คคาบถัดไปแบบเรียลไทม์\n'
        '- "ลาป่วย/ลากิจ/ลา" = แบบฟอร์มลากิจ-ลาป่วย\n'
        '- "สอบ" = นับถอยหลังวันสอบ\n'
        '- "ชีวะ" = เฉลยชีวะ\n'
        '- "เปิดเพลง [ชื่อเพลง]" = หาเพลงจาก Youtube\n'
        '- ถ้าพิมพ์ข้อความอื่น ๆ ผมจะตอบด้วยเอไอ'
    )
    return TextMessage(text=help_text)

# --- YouTube helpers (validation + search) ---
def extract_youtube_id(url_or_text: str) -> Optional[str]:
    if not url_or_text:
        return None
    # Look for common URL patterns; YouTube video IDs are typically 11 chars
    m = re.search(r'(?:v=|\/v\/|youtu\.be\/|\/embed\/)([A-Za-z0-9_\-]{11})', url_or_text)
    if m:
        return m.group(1)
    # If the user provided just an ID
    m2 = re.match(r'^[A-Za-z0-9_\-]{11}$', url_or_text.strip())
    if m2:
        return url_or_text.strip()
    return None

def youtube_check_video_status(video_id: str, region_code: str = "TH") -> dict:
    if not video_id:
        return {"ok": False, "reason": "no_video_id", "info": None}

    if YOUTUBE_API_KEY:
        params = {"part": "status,contentDetails", "id": video_id, "key": YOUTUBE_API_KEY}
        try:
            r = requests.get("https://www.googleapis.com/youtube/v3/videos", params=params, timeout=6)
        except Exception as e:
            return {"ok": False, "reason": f"yt_api_request_failed_{e}", "info": None}
        if r.status_code != 200:
            return {"ok": False, "reason": f"yt_api_error_{r.status_code}", "info": r.text}
        data = r.json()
        items = data.get("items", [])
        if not items:
            return {"ok": False, "reason": "not_found", "info": data}
        item = items[0]
        status = item.get("status", {})
        content = item.get("contentDetails", {})

        if status.get("privacyStatus") != "public":
            return {"ok": False, "reason": f"privacy_{status.get('privacyStatus')}", "info": item}
        if status.get("uploadStatus") and status.get("uploadStatus") != "processed":
            return {"ok": False, "reason": f"upload_{status.get('uploadStatus')}", "info": item}
        region = content.get("regionRestriction", {})
        blocked = region.get("blocked")
        allowed = region.get("allowed")
        if blocked and region_code and region_code in blocked:
            return {"ok": False, "reason": f"region_blocked_{region_code}", "info": item}
        return {"ok": True, "reason": "ok", "info": item}

    # Fallback: oEmbed check or page text scan
    try:
        oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
        r2 = requests.get(oembed_url, timeout=6)
        if r2.status_code == 200:
            return {"ok": True, "reason": "ok_oembed", "info": r2.json()}
        else:
            watch = requests.get(f"https://www.youtube.com/watch?v={video_id}", timeout=6)
            txt = watch.text.lower()
            if "video unavailable" in txt or "ไม่พร้อมใช้งาน" in txt or "this video is unavailable" in txt:
                return {"ok": False, "reason": "page_unavailable", "info": {"status_code": watch.status_code}}
            return {"ok": True, "reason": "assume_ok", "info": {"status_code": watch.status_code}}
    except Exception as e:
        return {"ok": False, "reason": f"fallback_error_{e}", "info": None}

def youtube_search_videos(query: str, max_results: int = 5) -> list:
    if not query:
        return []
    if not YOUTUBE_API_KEY:
        return []
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": max_results,
        "key": YOUTUBE_API_KEY,
        "regionCode": "TH"
    }
    try:
        r = requests.get("https://www.googleapis.com/youtube/v3/search", params=params, timeout=6)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    resp = r.json()
    items = resp.get("items", [])
    ids = []
    for it in items:
        vid = it.get("id", {}).get("videoId")
        if vid:
            ids.append(vid)
    return ids

# --- Modified music function with validation ---
def get_music_link_message(user_message: str):
    app.logger.info(f"Handling music request: {user_message}")
    music_keywords = ["เปิดเพลง", "หาเพลง", "ขอเพลง"]
    song_title = user_message
    for keyword in music_keywords:
        if song_title.startswith(keyword):
            song_title = song_title[len(keyword):].strip()
            break
    if not song_title:
        return TextMessage(text="กรุณาระบุชื่อเพลงด้วยครับ เช่น 'เปิดเพลง [ชื่อเพลง]'")

    search_prompt = (
        f"คุณคือผู้ช่วยค้นหาเพลง กรุณาค้นหาลิงก์ YouTube ที่เป็นทางการ (Official) หรือเพลงที่มีคุณภาพดี "
        f"สำหรับเพลงนี้: '{song_title}' และตอบกลับมาเฉพาะลิงก์ YouTube ที่ถูกต้องลิงก์เดียวเท่านั้น ถ้าหาไม่เจอให้ตอบว่า 'หาไม่เจอ'"
    )
    ai_response = get_gemini_response(search_prompt)

    url_match = re.search(r'(https?://(?:www\.)?(?:youtube\.com|youtu\.be)[^\s\'"]+)', ai_response or "")
    if url_match:
        candidate_url = url_match.group(0).strip(")'\"")
        vid = extract_youtube_id(candidate_url)
        if vid:
            status = youtube_check_video_status(vid)
            if status.get("ok"):
                return TextMessage(text=f"จัดไปครับ! 🎵\nhttps://www.youtube.com/watch?v={vid}")
            else:
                app.logger.info(f"Found video but not playable: {status}")
                if YOUTUBE_API_KEY:
                    alt_ids = youtube_search_videos(song_title, max_results=5)
                    for alt in alt_ids:
                        st = youtube_check_video_status(alt)
                        if st.get("ok"):
                            return TextMessage(text=f"วิดีโอตัวแรกไม่พร้อมใช้งาน ผมหาวิดีโอตัวอื่นมาให้แทน 🎵\nhttps://www.youtube.com/watch?v={alt}")
                return TextMessage(text="วิดีโอตัวที่พบไม่พร้อมใช้งานแล้วครับ ลองพิมพ์อีกครั้งหรือระบุชื่อศิลปินเพิ่ม (เช่น 'เปิดเพลง Just the two of us - Bill Withers')")

    if "หาไม่เจอ" in (ai_response or "").lower() or not url_match:
        if YOUTUBE_API_KEY:
            candidates = youtube_search_videos(song_title, max_results=5)
            for c in candidates:
                st = youtube_check_video_status(c)
                if st.get("ok"):
                    return TextMessage(text=f"ผมหาวิดีโอที่ตรงกันเจอครับ 🎵\nhttps://www.youtube.com/watch?v={c}")
            return TextMessage(text="ผมหาวิดีโอที่เล่นได้ไม่เจอ หรือถูกจำกัดในประเทศของคุณ ลองระบุชื่อศิลปินหรือชื่อเพลงให้ละเอียดขึ้นครับ")
        else:
            return TextMessage(text=f"{ai_response}\n(หมายเหตุ: หากลิงก์ใช้งานไม่ได้ บอทแนะนำให้ตั้งค่า YOUTUBE_API_KEY เพื่อให้ตรวจสอบสถานะวิดีโอก่อนส่งลิงก์ได้อย่างแม่นยำ)")

    return TextMessage(text=f"ผมหาลิงก์ให้ไม่ได้ครับ แต่ได้ผลการค้นหามาว่า:\n{ai_response}")

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
    (("ลาป่วย", "ลากิจ", "ลา"), get_absence_form_message),
    (("ชีวะ", "เฉลยชีวะ"), get_bio_link_message),
    (("เปิดเพลง", "หาเพลง", "ขอเพลง"), lambda msg: get_music_link_message(msg)),
    (("คำสั่ง", "help", "ช่วยเหลือ"), get_help_message),
    (("สอบ",), lambda msg: get_exam_countdown_message(msg)),
]

def _keyword_matches(user_message: str, keyword: str) -> bool:
    try:
        kw = keyword.lower()
        um = user_message.lower()
        # Ensure keyword is not adjacent to ASCII word chars or Thai chars (Unicode range \u0E00-\u0E7F)
        pattern = rf'(?<![\w\u0E00-\u0E7F]){re.escape(kw)}(?![\w\u0E00-\u0E7F])'
        return bool(re.search(pattern, um, flags=re.IGNORECASE))
    except re.error:
        return keyword in user_message

def call_action(action, user_message: str):
    try:
        return action(user_message)
    except TypeError:
        try:
            return action()
        except TypeError:
            return action(user_message)

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_text = getattr(event.message, "text", "")
    user_message = user_text.lower().strip()
    reply_message = None

    # Rule-based commands (check longer keywords first to avoid short accidental matches)
    for keywords, action in COMMANDS:
        matched = False
        for keyword in sorted(keywords, key=len, reverse=True):
            if _keyword_matches(user_message, keyword):
                try:
                    reply_message = call_action(action, user_message)
                except Exception as e:
                    app.logger.error(f"Error calling action for keywords {keywords}: {e}", exc_info=True)
                    reply_message = TextMessage(text="ขออภัยครับ เกิดข้อผิดพลาดขณะประมวลผลคำสั่งของคุณ")
                matched = True
                break
        if matched:
            break

    # AI fallback
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
    cfg_ok = "OK" if ACCESS_TOKEN and CHANNEL_SECRET else "CONFIG_MISSING"
    return f"MTC Assistant is running! ({cfg_ok})"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
