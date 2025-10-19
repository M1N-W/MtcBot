# -*- coding: utf-8 -*-

import os
import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, abort
import logging

# --- 1. Import tools for Gemini AI and LINE Bot ---
import google.generativeai as genai
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, ImageMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

# ==========================================================================================
# --- Configuration & Constants ---
# ย้ายค่าต่างๆมารวมกันไว้ด้านบน เพื่อให้ง่ายต่อการแก้ไขในอนาคต
# ==========================================================================================
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# LINE Bot Credentials
ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')

# Gemini API Key
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# Bot Constants & Links
WORKSHEET_LINK = "https://docs.google.com/spreadsheets/d/1oCG--zkyp-iyJ8iFKaaTrDZji_sds2VzLWNxOOh7-xk/edit?usp=sharing"
SCHOOL_LINK = "https://www.ben.ac.th/main/"
TIMETABLE_IMG = "https://img5.pic.in.th/file/secure-sv1/-2395abd52df9b5e08.jpg"
GRADE_LINK = "http://www.dograde2.online/bjrb/"

# Exam Dates
# NOTE: It's better to manage these dates in a config file or database for easier updates.
EXAM_DATES = {
    "กลางภาค": datetime.date(2025, 12, 15),
    "ปลายภาค": datetime.date(2026, 2, 15)
}

# ==========================================================================================
# --- Initialize APIs ---
# ==========================================================================================
configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
model = None

# Configure Gemini AI
try:
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash-preview-09-2025')
        app.logger.info("Gemini AI configured successfully.")
    else:
        app.logger.warning("GEMINI_API_KEY is not set. AI features will be disabled.")
except Exception as e:
    app.logger.error(f"Error configuring Gemini AI: {e}")

# ==========================================================================================
# --- Data & Helper Functions ---
# ==========================================================================================

# NOTE: For better maintainability, consider moving this schedule to a separate JSON file.
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

def get_next_class_info():
    """Checks the schedule and returns information about the next class."""
    now = datetime.datetime.now(tz=ZoneInfo("Asia/Bangkok"))
    weekday = now.weekday()
    current_time = now.time()

    if weekday not in SCHEDULE:
        return "วันนี้วันหยุดไม่ใช่วันเรียน กลับไปนอนไป้ 🎉"

    for period in SCHEDULE[weekday]:
        start_time = datetime.datetime.strptime(period["start"], "%H:%M").time()
        if current_time < start_time:
            return f"คาบต่อไป:\nเริ่มคาบ: {period['start']}\nจบคาบ: {period['end']}\nวิชา: {period['subject']}\nห้อง: {period['room']}"

    return "วันนี้ไม่มีคาบเรียนแล้วครับ กลับบ้านไปนอนได้ 🏠"

def create_countdown_message(exam_name, exam_date):
    """Creates a countdown message for a given exam date."""
    today = datetime.date.today()
    delta = exam_date - today
    days_left = delta.days

    if days_left > 0:
        return f"เหลืออีก {days_left} วันจะถึงวันสอบ{exam_name} ({exam_date.strftime('%d %b %Y')}) นะครับ"
    elif days_left == 0:
        return f"วันนี้วันสอบ{exam_name}แล้ว โชคดีนะครับ :)"
    else:
        return f"การสอบ{exam_name}เสร็จสิ้นแล้วครับ"

def get_gemini_response(user_message):
    """Gets a response from the Gemini AI model."""
    if not model:
        return "ขออภัยครับ ระบบ AI ของส่วนนี้ยังไม่สมบูรณ์"
    try:
        response = model.generate_content(user_message)
        reply_text = response.text.strip() if response.text else "(AI ไม่ได้ตอบกลับ)"
        # Truncate long messages to avoid LINE API errors
        if len(reply_text) > 4800:
            reply_text = reply_text[:4800] + "... (ข้อความยาวเกินไปจึงถูกตัด นะจ๊ะ)"
        return reply_text
    except Exception as e:
        app.logger.error(f"Gemini API Error: {e}")
        return "ขออภัยครับ ตอนนี้ผมมีปัญหาในการเชื่อมต่อกับ AI ลองใหม่อีกครั้งนะ"

# ==========================================================================================
# --- LINE Bot Event Handlers ---
# ==========================================================================================

@handler.add(FollowEvent)
def handle_follow(event):
    """Handles when a user adds the bot as a friend."""
    welcome_message = TextMessage(text='สวัสดีคับ! ผมคือ MTC Assistant ผู้ช่วยอเนกประสงค์ของห้อง ม.4/2\nคุณจะลองพิมพ์คำสั่งต่างๆ หรือจะคุยเล่นกับผมก็ได้นะ!\n\nคำสั่งมีดังนี้ครับ\n-"งาน/การบ้าน" = ดูตารางงานและการบ้านที่ครูสั่ง\n-"เว็บ" = เข้าเว็บโรงเรียน\n-"ตารางสอน" = ตารางสอนห้อง ม.4/2\n-"ดูเกรด" = เข้าเว็บดูเกรด\n-"สอบ" = ดูวันสอบ&บอกว่าอีกกี่วันจะสอบ\n-"เรียนไรต่อ/คาบต่อไป" = เช็คแบบเรียลไทม์ว่าคาบต่อไปเรียนอะไร')
    reply_to_line(event.reply_token, [welcome_message])

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """
    Handles incoming text messages by routing them to command handlers or the AI.
    """
    user_message = event.message.text.lower().strip()
    reply_message = None

    # --- Command Router ---
    # Using a dictionary for commands makes the code cleaner and easier to extend.
    command_actions = {
        ("งาน", "การบ้าน", "เช็คงาน"): lambda: TextMessage(text=f'นี่คือลิงก์เช็คงานห้องเรานะครับ\n{WORKSHEET_LINK}'),
        ("เว็บโรงเรียน", "โรงเรียนเบญ", "เว็บ"): lambda: TextMessage(text=f'นี่คือลิงก์เว็บโรงเรียนนะครับ\n{SCHOOL_LINK}'),
        ("ตารางเรียน", "ตารางสอน"): lambda: ImageMessage(original_content_url=TIMETABLE_IMG, preview_image_url=TIMETABLE_IMG),
        ("เกรด", "ดูเกรด"): lambda: TextMessage(text=f'นี่คือลิงก์เว็บดูเกรดนะครับ\n{GRADE_LINK}'),
        ("คาบต่อไป", "เรียนอะไร", "เรียนไรต่อ"): lambda: TextMessage(text=get_next_class_info()),
    }

    # Find and execute the command action
    for keywords, action in command_actions.items():
        if user_message in keywords:
            reply_message = action()
            break
    
    # Special handling for "สอบ" command
    if not reply_message and "สอบ" in user_message or "นับถอยหลังวันสอบ" in user_message:
        if "กลางภาค" in user_message:
            reply_text = create_countdown_message("กลางภาค", EXAM_DATES["กลางภาค"])
        elif "ปลายภาค" in user_message:
            reply_text = create_countdown_message("ปลายภาค", EXAM_DATES["ปลายภาค"])
        else:
            midterm = create_countdown_message("กลางภาค", EXAM_DATES["กลางภาค"])
            final = create_countdown_message("ปลายภาค", EXAM_DATES["ปลายภาค"])
            reply_text = f"{midterm}\n\n{final}"
        reply_message = TextMessage(text=reply_text)

    # --- AI Fallback ---
    # If no command was matched, send the message to Gemini AI.
    if not reply_message:
        ai_response_text = get_gemini_response(user_message)
        reply_message = TextMessage(text=ai_response_text)

    # --- Send Reply ---
    reply_to_line(event.reply_token, [reply_message])

def reply_to_line(reply_token, messages):
    """A helper function to send reply messages to LINE."""
    if not messages:
        return
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(reply_token=reply_token, messages=messages)
            )
    except Exception as e:
        app.logger.error(f"Error sending reply to LINE: {e}")

# ==========================================================================================
# --- Flask Web Server ---
# ==========================================================================================

@app.route("/callback", methods=['POST'])
def callback():
    """Webhook endpoint from LINE."""
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

if __name__ == "__main__":
    # Use Port from Environment Variable or default to 5001
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
