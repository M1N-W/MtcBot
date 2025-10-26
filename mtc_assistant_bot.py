# -*- coding: utf-8 -*-
"""
MTC Assistant v14 - Song Searching Feature
"""

# --- 1. Imports ---
import os
import datetime
import logging
import inspect
import re
from zoneinfo import ZoneInfo
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
# ตั้งค่า logging เพื่อให้แสดงผลใน production environment
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- Credentials (ดึงจาก Environment Variables เพื่อความปลอดภัย) ---
ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# Log a warning if important env vars missing
if not ACCESS_TOKEN:
    app.logger.warning("CHANNEL_ACCESS_TOKEN is not set. LINE API calls will fail.")
if not CHANNEL_SECRET:
    app.logger.warning("CHANNEL_SECRET is not set. Signature verification will fail.")
if not GEMINI_API_KEY:
    app.logger.info("GEMINI_API_KEY is not set. AI features will be disabled.")

# --- Bot Constants & Links ---
WORKSHEET_LINK = "https://docs.google.com/spreadsheets/d/1oCG--zkyp-iyJ8iFKaaTrDZji_sds2VzLWNxOOh7-xk/edit?usp=sharing"
SCHOOL_LINK = "https://www.ben.ac.th/main/"
TIMETABLE_IMG = "https://img5.pic.in.th/file/secure-sv1/-2395abd52df9b5e08.jpg"
GRADE_LINK = "http://www.dograde2.online/bjrb/"
ABSENCE_LINK = "https://forms.gle/WjCBTYNxEeCpHShr9"
Bio_LINK = "https://drive.google.com/file/d/1zd5NND3612JOym6HSzKZnqAS42TH9gmh/view?usp=sharing"
# --- Exam Dates ---
EXAM_DATES = {
    "กลางภาค": datetime.date(2025, 12, 20),
    "ปลายภาค": datetime.date(2026, 2, 20)
}

# LINE text length safety limits
LINE_MAX_TEXT = 5000
LINE_SAFE_TRUNCATE = 4800

# Default timezone
LOCAL_TZ = ZoneInfo("Asia/Bangkok")

# --- Class Schedule Data ---
# (0=จันทร์, 1=อังคาร, ..., 4=ศุกร์)
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
        {"start": "13:05", "end": "14:00", "subject": "คณิตเพิ่มพูน (ครูมานพ)", "room": "947"},
        {"start": "14:00", "end": "14:55", "subject": "สังคมศึกษา (ครูบังอร)", "room": "947"},
        {"start": "14:55", "end": "15:50", "subject": "ไทย (ครูเบญจมาศ)", "room": "947"},
        {"start": "15:50", "end": "16:45", "subject": "อังกฤษพื้นฐาน (ครูวาสนา)", "room": "947"},
    ],
    2: [ # วันพุธ
        {"start": "08:30", "end": "09:25", "subject": "อังกฤษพื้นฐาน (ครูวาสนา)", "room": "947"},
        {"start": "09:25", "end": "10:20", "subject": "คณิตเพิ่มพูน (ครูมานพ)", "room": "947"},
        {"start": "10:20", "end": "11:15", "subject": "ประวัติศาสตร์ (ครูณฐพร)", "room": "947"},
        {"start": "11:15", "end": "12:10", "subject": "คณิตพื้นฐาน (ครูปรียา)", "room": "947"},
    ],
    3: [ # วันพฤหัสบดี
        {"start": "08:30", "end": "09:25", "subject": "คณิตเพิ่มพูน (ครูมานพ)", "room": "947"},
        {"start": "09:25", "end": "10:20", "subject": "คณิตเพิ่มพูน (ครูมานพ)", "room": "947"},
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
GEMINI_MODEL_NAME = "gemini-2.5-flash"

try:
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        # We do not hard-rely on a GenerativeModel class because SDK versions differ.
        # If the SDK exposes a model instantiation we try to create it, else fallback to module-level calls.
        try:
            # Some SDKs may provide a GenerativeModel factory
            gemini_model = getattr(genai, "GenerativeModel")(GEMINI_MODEL_NAME)
            app.logger.info("Gemini model instantiated via GenerativeModel.")
        except Exception:
            # Fallback: we'll call genai.generate_text / genai.chat.create later directly
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
    # Common shapes: response.text, response["text"], response["candidates"][0]["content"], response.output[0].content, etc.
    try:
        if response is None:
            return ""
        if hasattr(response, "text"):
            return str(response.text).strip()
        if isinstance(response, dict):
            # common fields
            if "text" in response and response["text"]:
                return str(response["text"]).strip()
            if "candidates" in response and response["candidates"]:
                first = response["candidates"][0]
                if isinstance(first, dict) and "content" in first:
                    return str(first["content"]).strip()
                return str(first).strip()
        # Some SDKs return objects with .output or .candidates fields
        if hasattr(response, "result"):
            return str(getattr(response, "result")).strip()
        if hasattr(response, "candidates"):
            c = getattr(response, "candidates")
            if c:
                first = c[0]
                if hasattr(first, "content"):
                    return str(getattr(first, "content")).strip()
                return str(first).strip()
        # Last resort
        return str(response).strip()
    except Exception as e:
        app.logger.debug(f"Error parsing Gemini response: {e}", exc_info=True)
        return str(response)

def get_gemini_response(user_message: str) -> str:
    """Gets a response from the Gemini AI model and post-processes it to enforce bot persona."""
    # Fixed identity message (clean UTF-8)
    identity_msg = (
        "ผมเป็นบอทผู้ช่วยอเนกประสงค์ของห้อง MTC ม.4/2 "
        "ผมช่วยได้หลายอย่างตามคำสั่งที่ผู้ใช้พิมพ์ และมีระบบ AI ของ Gemini ที่ช่วยตอบคำถามครับ"
    )

    identity_queries = ["คุณคือใคร", "เป็นใคร", "who are you", "คุณชื่ออะไร", "ชื่ออะไร", "ตัวตน"]
    lowered = user_message.lower()
    if any(q in lowered for q in identity_queries):
        return identity_msg

    if not GEMINI_API_KEY:
        return "ขออภัยครับ ระบบ AI ของส่วนนี้ยังไม่สมบูรณ์"

    try:
        # Try using instantiated model if available
        response = None
        if gemini_model is not None:
            # defensive: some instantiations may provide generate_content or generate
            if hasattr(gemini_model, "generate_content"):
                response = gemini_model.generate_content(user_message)
            elif hasattr(gemini_model, "generate"):
                response = gemini_model.generate(user_message)
            else:
                # fallback to module-level calls below
                response = None

        if response is None:
            # Try common module-level APIs (SDKs vary)
            try:
                # genai.generate_text is a possibility
                if hasattr(genai, "generate_text"):
                    response = genai.generate_text(model=GEMINI_MODEL_NAME, input=user_message)
                elif hasattr(genai, "chat"):
                    # some SDKs have genai.chat.create or genai.chat.generate
                    chat_create = getattr(genai, "chat").create if hasattr(genai.chat, "create") else getattr(genai.chat, "generate", None)
                    if chat_create:
                        response = chat_create(model=GEMINI_MODEL_NAME, messages=[{"role": "user", "content": user_message}])
                    else:
                        response = None
                else:
                    # last resort: try a generic call
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

        # --- Post-processing to enforce persona and remove Google ownership ---
        reply_text = re.sub(r'\b[Gg]oogle\b', 'Gemini', reply_text)
        reply_text = reply_text.replace('กูเกิล', 'Gemini')

        if re.search(r'(แบบจำลอง|ฝึกโดย|ฝึกอบรม|trained by|model)', reply_text, flags=re.IGNORECASE):
            lines = reply_text.splitlines()
            filtered_lines = [ln for ln in lines if not re.search(r'(แบบจำลอง|ฝึกโดย|ฝึกอบรม|trained by|model)', ln, flags=re.IGNORECASE)]
            remaining = "\n".join(filtered_lines).strip()
            reply_text = identity_msg
            if remaining:
                reply_text = reply_text + "\n\n" + remaining

        # Ensure we don't exceed LINE limit
        if len(reply_text) > LINE_SAFE_TRUNCATE:
            reply_text = reply_text[:LINE_SAFE_TRUNCATE] + "... (ระบบตัดข้อความที่ยาวเกิน 5,000 คำโดยอัตโนมัติ)"

        return reply_text
    except Exception as e:
        app.logger.error(f"Gemini API Error: {e}", exc_info=True)
        return "ขออภัยครับ ตอนนี้ผมมีปัญหาในการเชื่อมต่อกับ AI ลองใหม่อีกครั้งนะ"

def reply_to_line(reply_token: str, messages: list):
    """Sends a reply message to the LINE user."""
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
    """Returns a TextMessage with the worksheet link."""
    return TextMessage(text=f'นี่คือตารางเช็คงานห้องเรานะครับ\n{WORKSHEET_LINK}')

def get_school_link_message():
    """Returns a TextMessage with the school link."""
    return TextMessage(text=f'นี่คือลิงก์เว็บโรงเรียนนะครับ\n{SCHOOL_LINK}')

def get_timetable_image_message():
    """Returns an ImageMessage with the class timetable."""
    return ImageMessage(original_content_url=TIMETABLE_IMG, preview_image_url=TIMETABLE_IMG)

def get_grade_link_message():
    """Returns a TextMessage with the grade checking link."""
    return TextMessage(text=f'นี่คือลิงก์เว็บดูเกรดนะครับ\n{GRADE_LINK}')

def get_next_class_message():
    """Returns a TextMessage with the info for the next class."""
    return TextMessage(text=get_next_class_info())

def get_absence_form_message():
    """Returns a TextMessage with the absence form link."""
    return TextMessage(text=f'นี่คือแบบฟอร์มลากิจ-ลาป่วยนะครับ\n{ABSENCE_LINK}')

def get_bio_link_message():
    """Returns a TextMessage with the biology link."""
    return TextMessage(text=f'นี่คือเฉลยชีวะ บทที่ 4-7 นะครับ\n{Bio_LINK}')

def get_help_message():
    """Returns a TextMessage with all commands."""
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

# --- START: MODIFIED MUSIC FUNCTION ---
def get_music_link_message(user_message: str):
    """Finds a YouTube link for a song request using the AI."""
    app.logger.info(f"Handling music request: {user_message}")
    
    # --- 1. Clean the user message ---
    # ลบคำสั่งหลัก ("เปิดเพลง", "หาเพลง", "ขอเพลง") ออกจากข้อความ
    music_keywords = ["เปิดเพลง", "หาเพลง", "ขอเพลง"]
    song_title = user_message
    for keyword in music_keywords:
        if song_title.startswith(keyword):
            song_title = song_title[len(keyword):].strip() # ตัดคำสั่งทิ้ง
            break # เจอแล้ว หยุดเลย
    
    # ป้องกันกรณีที่ผู้ใช้พิมพ์ "เปิดเพลง" เฉยๆ
    if not song_title:
        return TextMessage(text="กรุณาระบุชื่อเพลงด้วยครับ เช่น 'เปิดเพลง [ชื่อเพลง]'")

    # --- 2. Improve the AI prompt ---
    # ขอให้ AI หาลิงก์ที่ "น่าเชื่อถือ" หรือ "เป็นทางการ"
    search_prompt = (
        f"คุณคือผู้ช่วยค้นหาเพลง กรุณาค้นหาลิงก์ YouTube ที่เป็นทางการ (Official) หรือเป็นที่นิยมที่สุด (Most Popular) "
        f"สำหรับเพลงนี้: '{song_title}' "
        f"และตอบกลับมาเฉพาะลิงก์ YouTube ที่ถูกต้องลิงก์เดียวเท่านั้น ถ้าหาไม่เจอ ให้ตอบว่า 'ผมหาเพลง {song_title} ไม่เจอครับ'"
    )
    
    # เรียกใช้ฟังก์ชัน AI ที่เรามีอยู่แล้ว
    ai_response = get_gemini_response(search_prompt)
    
    # --- 3. Validate the response ---
    if "youtube.com" in ai_response or "youtu.be" in ai_response:
        # ตัดข้อความอื่นๆ ที่ AI อาจจะแถมมา ให้เหลือแค่ลิงก์
        url_match = re.search(r'(https?://(?:www\.)?(?:youtube\.com|youtu\.be)[^\s]+)', ai_response)
        if url_match:
            ai_response = url_match.group(0)
            # เพิ่มการตัดอักขระแปลกปลอมที่อาจจะติดมากับลิงก์ (เช่น ')
            ai_response = ai_response.strip(")'\"") 
        
        return TextMessage(text=f"จัดไปครับ! 🎵\n{ai_response}")
    elif "หาไม่เจอ" in ai_response:
        return TextMessage(text=ai_response)
    else:
        return TextMessage(text=f"ผมหาลิงก์ให้ไม่ได้ครับ แต่ได้ผลการค้นหามาว่า:\n{ai_response}")
# --- END: MODIFIED MUSIC FUNCTION ---

def get_exam_countdown_message(user_message: str):
    """Creates a countdown message for exams based on user input."""
    # Use explicit keys in EXAM_DATES
    if "กลางภาค" in user_message:
        reply_text = create_countdown_message("กลางภาค", EXAM_DATES["กลางภาค"])
    elif "ปลายภาค" in user_message:
        reply_text = create_countdown_message("ปลายภาค", EXAM_DATES["ปลายภาค"])
    else:  # default when user just types "สอบ" or similar
        midterm = create_countdown_message("กลางภาค", EXAM_DATES["กลางภาค"]) if "กลางภาค" in EXAM_DATES else ""
        final = create_countdown_message("ปลายภาค", EXAM_DATES["ปลายภาค"]) if "ปลายภาค" in EXAM_DATES else ""
        if midterm and final:
            reply_text = f"{midterm}\n\n{final}"
        else:
            reply_text = midterm or final or "ไม่พบวันสอบในระบบครับ"
    return TextMessage(text=reply_text)

# ==========================================================================================
# --- 6. LINE Bot Event Handlers ---
# ==========================================================================================

@handler.add(FollowEvent)
def handle_follow(event):
    """Handles when a user adds the bot as a friend."""
    welcome_message = TextMessage(
        text='สวัสดีคับ! ผมคือ MTC Assistant ผู้ช่วยอเนกประสงค์ของห้อง ม.4/2\n'
             'คุณจะลองพิมพ์คำสั่งต่างๆ หรือจะคุยเล่นกับผมก็ได้นะ!\n\n'
             'พิมพ์ "คำสั่ง" เพื่อดูรายการคำสั่งทั้งหมดนะครับ'
    )
    reply_to_line(event.reply_token, [welcome_message])

# --- โครงสร้าง Command Mapping ที่ปรับปรุงใหม่ ---
# เก็บเป็น List of Tuples ทำให้ง่ายต่อการเพิ่ม/ลดคำสั่ง
# Tuple ประกอบด้วย: ( (คำสั่งที่1, คำสั่งที่2), ฟังก์ชันที่จะทำงาน )
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

    # สำหรับคำสั่งที่ต้องการข้อมูลจาก user_message เราใช้ lambda เพื่อส่งค่าเข้าไป
    (("สอบ",), lambda msg: get_exam_countdown_message(msg)),
]

def _keyword_matches(user_message: str, keyword: str) -> bool:
    """
    Match keyword more carefully:
    - For keywords that contain ASCII letters, use word-boundary regex to avoid false positives.
    - For Thai or other scripts without spaces, fall back to substring match.
    """
    if re.search(r'[A-Za-z]', keyword):
        # escape keyword
        pattern = r'\b' + re.escape(keyword) + r'\b'
        return bool(re.search(pattern, user_message, flags=re.IGNORECASE))
    else:
        return keyword in user_message

def call_action(action, user_message: str):
    """
    Safely call an action that may accept 0 or 1 arguments.
    Prefer calling with user_message if accepted, else call without args.
    """
    # First try calling with one argument
    try:
        return action(user_message)
    except TypeError:
        try:
            return action()
        except TypeError:
            # last resort: try calling with no args, then with arg with more permissive attempt
            return action(user_message)

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """Handles incoming text messages from users."""
    user_text = getattr(event.message, "text", "")
    user_message = user_text.lower().strip()
    reply_message = None

    # --- 1. Process Rule-Based Commands ---
    for keywords, action in COMMANDS:
        if any(_keyword_matches(user_message, keyword) for keyword in keywords):
            try:
                reply_message = call_action(action, user_message)
            except Exception as e:
                app.logger.error(f"Error calling action for keywords {keywords}: {e}", exc_info=True)
                reply_message = TextMessage(text="ขออภัยครับ เกิดข้อผิดพลาดขณะประมวลผลคำสั่งของคุณ")
            break  # found matching command

    # --- 2. AI Fallback ---
    if not reply_message:
        ai_response_text = get_gemini_response(user_message)
        reply_message = TextMessage(text=ai_response_text)

    # --- 3. Send Reply ---
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
    # Add a simple check about configuration for easier debugging
    cfg_ok = "OK" if ACCESS_TOKEN and CHANNEL_SECRET else "CONFIG_MISSING"
    return f"MTC Assistant is running! ({cfg_ok})"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
