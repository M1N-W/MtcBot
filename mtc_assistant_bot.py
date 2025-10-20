# -*- coding: utf-8 -*-
"""
MTC Assistant v9.6 (Enhanced Logging)
LINE Bot ผู้ช่วยสำหรับห้องเรียน ม.4/2 ที่รวมการทำงานแบบกำหนดคำสั่ง (Rule-based)
และตอบคำถามทั่วไปด้วย Generative AI (Gemini)
"""

# --- 1. Imports ---
import os
import datetime
import logging
from zoneinfo import ZoneInfo
from flask import Flask, request, abort

import google.generativeai as genai
import google.api_core.exceptions # เพิ่ม import นี้เข้ามา
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
        
        system_instruction = (
            "ตอบคำถามของผู้ใช้ในฐานะผู้ช่วย AI ที่เป็นมิตรสำหรับนักเรียนมัธยมปลาย "
            "โดยให้คำตอบที่สุภาพ กระชับ และตรงประเด็น ไม่ต้องแนะนำตัวเองซ้ำในทุกคำตอบ"
        )
        
        generation_config = {
            "temperature": 0.7,
            "top_p": 1,
            "top_k": 1,
            "max_output_tokens": 1024,
        }

        gemini_model = genai.GenerativeModel(
            'gemini-2.5-flash',
            generation_config=generation_config,
            system_instruction=system_instruction
        )
        
        app.logger.info("Gemini AI configured successfully with improved prompting.")
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
        return "วันนี้วันหยุดไม่ใช่วันเรียน กลับไปนอนไป้ 🎉"

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
    """Gets a response from the Gemini AI model with improved error handling."""
    if not gemini_model:
        return "ขออภัยครับ ระบบ AI ของส่วนนี้ยังไม่สมบูรณ์"

    try:
        response_stream = gemini_model.generate_content(user_message, stream=True)
        full_response = ""

        for chunk in response_stream:
            if hasattr(chunk, 'text') and chunk.text:
                full_response += chunk.text

        if hasattr(response_stream, 'prompt_feedback') and response_stream.prompt_feedback.block_reason:
            app.logger.warning(f"Prompt blocked due to: {response_stream.prompt_feedback.block_reason}")
            return "ขออภัยครับ คำขอของคุณอาจขัดต่อนโยบายความปลอดภัย"

        reply_text = full_response.strip()
        return reply_text if reply_text else "ขออภัยครับ ผมไม่สามารถให้คำตอบในเรื่องนี้ได้"

    except google.api_core.exceptions.PermissionDenied as e:
        app.logger.error(f"Gemini API Permission Denied: {e}. Check your API key.")
        return "เกิดข้อผิดพลาดในการยืนยันตัวตนกับ AI ครับ (API Key อาจไม่ถูกต้อง)"
    except google.api_core.exceptions.ResourceExhausted as e:
        app.logger.error(f"Gemini API Quota Exceeded: {e}")
        return "ขออภัยครับ ตอนนี้โควต้าการใช้งาน AI เต็มแล้วสำหรับวันนี้"
    except Exception as e:
        # ใช้ exc_info=True เพื่อให้ log เก็บรายละเอียดของ error ทั้งหมดไว้
        # เพิ่มการ log type(e).__name__ เพื่อให้รู้ชนิดของ error แม้ว่า e จะไม่มีข้อความ
        error_type = type(e).__name__
        app.logger.error(f"An unexpected error occurred ({error_type}) in get_gemini_response", exc_info=True)
        return "ขออภัยครับ เกิดข้อผิดพลาดที่ไม่คาดคิดในการเชื่อมต่อกับ AI"

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
        app.logger.error(f"Error sending reply to LINE: {e}")

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
    return TextMessage(text='คำสั่งทั้งหมด\n- "งาน" = ดูตารางงาน\n- "เว็บ" = เข้าเว็บโรงเรียน\n- "ตารางสอน" = ดูตารางสอนห้อง ม.4/2\n- "เกรด" = เข้าเว็บดูเกรด\n- "สอบ" = นับถอยหลังวันสอบ\n- "เรียนไรต่อ/คาบต่อไป" = เช็คคาบเรียนถัดไปแบบเรียลไทม์\n- "ลา" = รับแบบฟอร์มลากิจ-ลาป่วย\n\nนอกเหนือจากนี้ คุยเล่นหรือถามอะไรผมก็ได้เลย!')

def get_exam_countdown_message(user_message: str):
    """Creates a countdown message for exams based on user input."""
    if "กลางภาค" in user_message:
        reply_text = create_countdown_message("กลางภาค", EXAM_DATES["กลางภาค"])
    elif "ปลายภาค" in user_message:
        reply_text = create_countdown_message("ปลายภาค", EXAM_DATES["ปลายภาค"])
    else:  # กรณี default ถ้าพิมพ์แค่ "สอบ"
        midterm = create_countdown_message("กลางภาค", EXAM_DATES["กลางภาค"])
        final = create_countdown_message("ปลายภาค", EXAM_DATES["ปลายภาค"])
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
COMMANDS = [
    (("งาน", "การบ้าน", "เช็คงาน"), get_worksheet_message),
    (("เว็บโรงเรียน", "เว็บ"), get_school_link_message),
    (("ตารางเรียน", "ตารางสอน"), get_timetable_image_message),
    (("เกรด", "ดูเกรด"), get_grade_link_message),
    (("คาบต่อไป", "เรียนอะไร", "เรียนไรต่อ"), get_next_class_message),
    (("ลาป่วย", "ลากิจ", "ลา"), get_absence_form_message),
    (("คำสั่ง", "help", "ช่วยเหลือ"), get_help_message),
    (("สอบ",), lambda msg: get_exam_countdown_message(msg)),
]

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """Handles incoming text messages from users."""
    user_message = event.message.text.lower().strip()
    reply_message = None

    # --- 1. Process Rule-Based Commands ---
    for keywords, action in COMMANDS:
        if any(keyword in user_message for keyword in keywords):
            if "msg" in action.__code__.co_varnames:
                reply_message = action(user_message)
            else:
                reply_message = action()
            break

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
    signature = request.headers['X-Line-Signature']
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
