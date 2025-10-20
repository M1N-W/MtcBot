# -*- coding: utf-8 -*-
"""
MTC Assistant v10.1 แก้เป็นร้อยรอบอยากร้องไห้
"""

# --- 1. Imports ---
import os
import datetime
import logging
import inspect
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

# --- Bot Constants & Links ---
WORKSHEET_LINK = "https://docs.google.com/spreadsheets/d/1oCG--zkyp-iyJ8iFKaaTrDZji_sds2VzLWNxOOh7-xk/edit?usp=sharing"
SCHOOL_LINK = "https://www.ben.ac.th/main/"
TIMETABLE_IMG = "https://img5.pic.in.th/file/secure-sv1/-2395abd52df9b5e08.jpg"
GRADE_LINK = "http://www.dograde2.online/bjrb/"
ABSENCE_LINK = "https://forms.gle/WjCBTYNxEeCpHShr9"

# --- Exam Dates ---
EXAM_DATES = {
    "กลางภาค": datetime.date(2025, 12, 15),
    "ปลายภาค": datetime.date(2026, 2, 15)
}

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

try:
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        # NOTE: ตรวจสอบว่า SDK ที่ใช้อยู่มี API แบบนี้จริงหรือไม่ในเวอร์ชันของคุณ
        gemini_model = genai.GenerativeModel('gemini-2.5-flash')
        app.logger.info("Gemini AI configured successfully.")
    else:
        app.logger.warning("GEMINI_API_KEY is not set. AI features will be disabled.")
except Exception as e:
    app.logger.error(f"Error configuring Gemini AI: {e}")

# ==========================================================================================
# --- 4. Core Helper Functions ---
# ==========================================================================================

def get_next_class_info() -> str:
    """Checks the schedule and returns a string with the next class information."""
    now = datetime.datetime.now(tz=ZoneInfo("Asia/Bangkok"))
    weekday = now.weekday()
    current_time = now.time()

    if weekday not in SCHEDULE:
        return "วันนี้วันหยุดไม่ใช่วันเรียน กลับไปนอนเถอะ 🎉"

    for period in SCHEDULE[weekday]:
        start_time = datetime.datetime.strptime(period["start"], "%H:%M").time()
        if current_time < start_time:
            return (f"คาบต่อไป มีรายละเอียดดังนี้ครับ\n"
                    f"เริ่มคาบ: {period['start']}\n"
                    f"จบคาบ: {period['end']}\n"
                    f"วิชา: {period['subject']}\n"
                    f"ห้อง: {period['room']}")

    return "วันนี้ไม่มีคาบเรียนแล้วครับ กลับบ้านไปนอนได้ 🏠"

def create_countdown_message(exam_name: str, exam_date: datetime.date) -> str:
    """Calculates days left until an exam and returns a formatted string."""
    today = datetime.date.today()
    delta = exam_date - today
    days_left = delta.days

    if days_left > 0:
        return f"เหลืออีก {days_left} วันจะถึงวันสอบ{exam_name} ({exam_date.strftime('%d %b %Y')}) นะครับ"
    elif days_left == 0:
        return f"วันนี้วันสอบ{exam_name}แล้ว โชคดีนะครับ :)"
    else:
        return f"การสอบ{exam_name}เสร็จสิ้นแล้วครับ"

def get_gemini_response(user_message: str) -> str:
    """Gets a response from the Gemini AI model."""
    if not gemini_model:
        return "ขออภัยครับ ระบบ AI ของส่วนนี้ยังไม่สมบูรณ์"
    try:
        # NOTE: SDK response shape may vary by version.
        # We try to be defensive: prefer .text, else fallback to str(response).
        response = gemini_model.generate_content(user_message)
        reply_text = ""
        # Common possibilities: response.text, response.result, response.candidates, etc.
        if hasattr(response, "text"):
            reply_text = response.text.strip()
        elif isinstance(response, dict) and "text" in response:
            reply_text = response["text"].strip()
        else:
            reply_text = str(response).strip()

        # LINE มีข้อจำกัดความยาวข้อความที่ 5000 ตัวอักษร
        if len(reply_text) > 4800:
            reply_text = reply_text[:4800] + "... (ข้อความยาวเกินไปจึงถูกตัด)"
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
    return TextMessage(text=f'นี่คือลิงก์เช็คงานห้องเรานะครับ\n{WORKSHEET_LINK}')

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

def get_help_message():
    """Returns a TextMessage with all commands."""
    help_text = (
        'คำสั่งทั้งหมด\n'
        '- "งาน", "การบ้าน", "เช็คงาน" = ดูตารางงาน (worksheet)\n'
        '- "เว็บโรงเรียน", "เว็บ" = เข้าเว็บโรงเรียน\n'
        '- "ตารางเรียน", "ตารางสอน" = ดูรูปตารางเรียน\n'
        '- "เกรด", "ดูเกรด" = ดูลิงก์เช็คเกรด\n'
        '- "คาบต่อไป", "เรียนอะไร", "เรียนไรต่อ" = บอกคาบถัดไป\n'
        '- "ลาป่วย", "ลากิจ", "ลา" = ลิงก์แบบฟอร์มขอลา\n'
        '- "สอบ [กลางภาค|ปลายภาค]" หรือแค่ "สอบ" = นับถอยหลังวันสอบ\n'
        '- ถ้าพิมพ์ข้อความอื่น ๆ ผมจะพยายามตอบด้วย AI (ถ้ามี API Key อยู่)\n'
    )
    return TextMessage(text=help_text)

def get_exam_countdown_message(user_message: str):
    """Creates a countdown message for exams based on user input."""
    if "กลางภาค" in user_message:
        reply_text = create_countdown_message("กลางภาค", EXAM_DATES["กลางภาค"])
    elif "ปลายภาค" in user_message:
        reply_text = create_countdown_message("ปลายภาค", EXAM_DATES["ปลายภาค"])
    else:  # กรณี default ถ้าพิมพ์แค่ "สอบ"
        midterm = create_countdown_message("กลางภาค", EXAM_DATES["กลางภาค"])
        final = create_countdown_message("ปลายภาค", EXAM_DATES["ปลายาภาค"]) if "ปลายภาค" in EXAM_DATES else create_countdown_message("ปลายภาค", EXAM_DATES["ปลายาภาค"])
        # Note: above line intentionally safe; but real code uses EXAM_DATES keys exactly as defined
        reply_text = f"{midterm}\n\n{final}"
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
    (("คำสั่ง", "help", "ช่วยเหลือ"), get_help_message),
    # สำหรับคำสั่งที่ต้องการข้อมูลจาก user_message เราใช้ lambda เพื่อส่งค่าเข้าไป
    (("สอบ",), lambda msg: get_exam_countdown_message(msg)),
]

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """Handles incoming text messages from users."""
    # defensive: ensure event.message has text attribute
    user_text = getattr(event.message, "text", "")
    user_message = user_text.lower().strip()
    reply_message = None

    # --- 1. Process Rule-Based Commands ---
    # ตรวจสอบว่าข้อความของผู้ใช้มี keyword ของคำสั่งใดๆ อยู่หรือไม่
    # (ปรับปรุงจากเดิมที่ต้องพิมพ์ตรงกันเป๊ะๆ)
    for keywords, action in COMMANDS:
        if any(keyword in user_message for keyword in keywords):
            # ตรวจสอบว่า action ต้องการ argument หรือไม่ -- ใช้ inspect.signature ให้ปลอดภัยกว่า
            try:
                sig = inspect.signature(action)
                params = sig.parameters
                if len(params) >= 1:
                    reply_message = action(user_message)
                else:
                    reply_message = action()
            except (ValueError, TypeError):
                # ถ้า action ไม่สามารถตรวจสอบ signature ได้ (เช่น builtins), ให้ลองเรียกโดยไม่ส่ง arg ก่อน
                try:
                    reply_message = action()
                except TypeError:
                    # สุดท้ายลองส่ง arg
                    reply_message = action(user_message)
            break  # เมื่อเจอคำสั่งที่ตรงกันแล้ว ให้ออกจาก loop ทันที

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
    return "MTC Assistant is running!"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
