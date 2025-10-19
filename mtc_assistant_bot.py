# -*- coding: utf-8 -*-

import os
import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, abort

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
# การย้ายค่าที่ตั้งไว้ต่างๆ มารวมกันไว้ด้านบน ทำให้ง่ายต่อการแก้ไขในอนาคต
# ==========================================================================================
app = Flask(__name__)

# LINE Bot Credentials
ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')

# Gemini API Key
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# Bot Constants
WORKSHEET_LINK = "https://docs.google.com/spreadsheets/d/1oCG--zkyp-iyJ8iFKaaTrDZji_sds2VzLWNxOOh7-xk/edit?usp=sharing"
SCHOOL_LINK = "https://www.ben.ac.th/main/"
TIMETABLE_IMG = "https://i.imgur.com/2s44t0A.jpeg"
GRADE_LINK = "http://www.dograde2.online/bjrb/"
FINAL_EXAM_DATE = datetime.date(2025, 2, 24) # สมมตินะครับ
MID_EXAM_DATE = datetime.date(2024, 12, 23) # สมมตินะครับ

# ==========================================================================================
# --- Initialize APIs ---
# ==========================================================================================
configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# Configure Gemini AI
try:
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        # เปลี่ยนไปใช้โมเดล gemini-pro ที่มีความเสถียรและพร้อมใช้งานทั่วไป
        model = genai.GenerativeModel('gemini-pro')
    else:
        model = None
        print("Warning: GEMINI_API_KEY is not set. AI features will be disabled.")
except Exception as e:
    model = None
    print(f"Error configuring Gemini AI: {e}")

# ==========================================================================================
# --- Data & Helper Functions ---
# ==========================================================================================

# Class Schedule Data
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
        {"start": "13:05", "end": "14:00", "subject": "สุขศึกษา&พละศึกษา (ครูนรเศรษฐ์)", "room": "โดม2"},
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
        return "วันนี้วันหยุดพักผ่อน ไม่มีเรียนครับ! 🎉"

    day_schedule = SCHEDULE[weekday]

    for period in day_schedule:
        start_time = datetime.datetime.strptime(period["start"], "%H:%M").time()
        if current_time < start_time:
            return f"คาบต่อไป:\nเริ่มคาบ: {period['start']}\nจบคาบ: {period['end']}\nวิชา: {period['subject']}\nห้อง: {period['room']}"

    return "วันนี้ไม่มีคาบเรียนแล้วครับ กลับบ้านได้! 🏠"

def create_countdown_message(exam_name, exam_date):
    """Creates a countdown message for a given exam date."""
    today = datetime.date.today()
    delta = exam_date - today
    days_left = delta.days

    if days_left > 0:
        return f"เหลืออีก {days_left} วันจะถึงวันสอบ{exam_name} ({exam_date.strftime('%d %b %Y')}) นะครับ"
    elif days_left == 0:
        return f"วันนี้วันสอบ{exam_name}แล้ว! โชคดีนะครับ!"
    else:
        return f"การสอบ{exam_name}ได้สิ้นสุดลงแล้วครับ"

# ==========================================================================================
# --- LINE Bot Event Handlers ---
# ==========================================================================================

@handler.add(FollowEvent)
def handle_follow(event):
    """Handles when a user adds the bot as a friend."""
    welcome_message = TextMessage(text='สวัสดีคับ! ผมคือ MTC Assistant\nผู้ช่วยอัจฉริยะสำหรับห้อง ม.4/2\n\n- ลองพิมพ์คำสั่งต่างๆ หรือจะคุยเล่นกับผมก็ได้นะ!')
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message_with_http_info(
                ReplyMessageRequest(reply_token=event.reply_token, messages=[welcome_message])
            )
    except Exception as e:
        print(f"Error in handle_follow: {e}")

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """
    Handles incoming text messages.
    It first checks for specific commands. If no command matches,
    it passes the message to the Gemini AI for a response.
    """
    user_message = event.message.text.lower().strip()
    reply_message = None

    # --- Command Checking ---
    # ตรวจสอบคำสั่งเฉพาะก่อนส่งไปให้ AI จะทำให้บอทตอบสนองได้เร็วและตรงประเด็นกว่า
    if user_message in ["งาน", "การบ้าน", "เช็คงาน"]:
        reply_message = TextMessage(text=f'นี่คือลิงก์เช็คงานห้องเรานะครับ:\n{WORKSHEET_LINK}')
    elif user_message in ["เว็บโรงเรียน", "โรงเรียนเบญ", "เว็บ"]:
        reply_message = TextMessage(text=f'นี่คือลิงก์เว็บโรงเรียนนะครับ:\n{SCHOOL_LINK}')
    elif user_message in ["ตารางเรียน", "ตารางสอน"]:
        reply_message = ImageMessage(original_content_url=TIMETABLE_IMG, preview_image_url=TIMETABLE_IMG)
    elif user_message in ["เกรด", "ดูเกรด"]:
        reply_message = TextMessage(text=f'นี่คือลิงก์เว็บดูเกรดนะครับ:\n{GRADE_LINK}')
    elif "สอบ" in user_message or "นับถอยหลัง" in user_message:
        if "กลางภาค" in user_message:
            reply_text = create_countdown_message("กลางภาค", MID_EXAM_DATE)
        elif "ปลายภาค" in user_message:
            reply_text = create_countdown_message("ปลายภาค", FINAL_EXAM_DATE)
        else:
            midterm_countdown = create_countdown_message("กลางภาค", MID_EXAM_DATE)
            final_countdown = create_countdown_message("ปลายภาค", FINAL_EXAM_DATE)
            reply_text = f"{midterm_countdown}\n\n{final_countdown}"
        reply_message = TextMessage(text=reply_text)
    elif user_message in ["คาบต่อไป", "เรียนอะไร", "เรียนไรต่อ"]:
        reply_text = get_next_class_info()
        reply_message = TextMessage(text=reply_text)
    else:
        # --- AI Fallback ---
        # ถ้าข้อความที่เข้ามาไม่ตรงกับคำสั่งใดๆ เลย จะส่งไปให้ Gemini AI ตอบ
        if not model:
            reply_message = TextMessage(text="ขออภัยครับ ระบบ AI ยังไม่ได้ตั้งค่าอย่างสมบูรณ์")
        else:
            try:
                response = model.generate_content(user_message)
                reply_text = response.text.strip() if response.text else "(AI ไม่ได้ตอบกลับ)"

                # LINE มีข้อจำกัดความยาวของข้อความที่ 5000 ตัวอักษร
                # เราควรตัดข้อความที่ยาวเกินไปเพื่อป้องกัน Error
                if len(reply_text) > 4800:
                    reply_text = reply_text[:4800] + "... (ข้อความยาวเกินไปจึงถูกตัด)"

                reply_message = TextMessage(text=reply_text)
            except Exception as e:
                print(f"Gemini API Error: {e}")
                reply_message = TextMessage(text="ขออภัยครับ ตอนนี้ผมมีปัญหาในการเชื่อมต่อกับ AI ลองใหม่อีกครั้งนะ")

    # --- Send Reply ---
    # รวมการส่งข้อความตอบกลับไว้ที่เดียว เพื่อลดความซ้ำซ้อนของโค้ด
    if reply_message:
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(reply_token=event.reply_token, messages=[reply_message])
                )
        except Exception as e:
            print(f"Error sending reply: {e}")


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
        app.logger.error(f"Error handling request: {e}")
        abort(500)

    return 'OK'

if __name__ == "__main__":
    # ใช้ Port จาก Environment Variable หรือถ้าไม่มีให้ใช้ 5001
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)

