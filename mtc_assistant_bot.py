# -*- coding: utf-8 -*-

# MTC Assistant v8: The AI Revolution! อัปเกรดสู่บอทอัจฉริยะด้วย Gemini AI

import os
import datetime
from zoneinfo import ZoneInfo
from flask import Flask, request, abort

# --- 1. นำเข้าเครื่องมือสำหรับคุยกับ Gemini AI ---
import google.generativeai as genai

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, ImageMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

app = Flask(__name__)
ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
# --- 2. ดึงกุญแจ Gemini API จาก Render ---
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# --- 3. ตั้งค่าการเชื่อมต่อกับ Gemini AI ---
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
else:
    model = None

# --- (โค้ดส่วนฐานข้อมูลตารางเรียนและฟังก์ชันต่างๆ ยังอยู่เหมือนเดิม) ---
SCHEDULE = {
    # ... (ข้อมูลตารางเรียนทั้งหมด) ...
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
    today = datetime.date.today()
    delta = exam_date - today
    days_left = delta.days
    if days_left > 0:
        return f"เหลืออีก {days_left} วันจะถึงวันสอบ{exam_name} ({exam_date.strftime('%d %b %Y')}) นะครับ"
    elif days_left == 0:
        return f"วันนี้วันสอบ{exam_name}แล้ว! โชคดีนะครับ!"
    else:
        return f"การสอบ{exam_name}ได้สิ้นสุดลงแล้วครับ"
@handler.add(FollowEvent)
def handle_follow(event):
    welcome_message = TextMessage(text='สวัสดีคับ! ผมคือ MTC Assistant\nผู้ช่วยอัจฉริยะสำหรับห้อง ม.4/2\n\n- ลองพิมพ์คำสั่งต่างๆ หรือจะคุยเล่นกับผมก็ได้นะ!')
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=event.reply_token, messages=[welcome_message]))
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_message = event.message.text.lower().strip()
    
    worksheet_link = "https://docs.google.com/spreadsheets/d/1oCG--zkyp-iyJ8iFKaaTrDZji_sds2VzLWNxOOh7-xk/edit?usp=sharing"
    school_link = "https://www.ben.ac.th/main/"
    timetable_img = "https://i.imgur.com/2s44t0A.jpeg"
    grade_link = "http://www.dograde2.online/bjrb/"
    FINAL_EXAM_DATE = datetime.date(2025, 12, 15)
    MID_EXAM_DATE = datetime.date(2025, 11, 15)
    
    reply_message = None

    # --- 4. อัปเกรดสมอง: เช็คคำสั่งเฉพาะก่อน ถ้าไม่ใช่ ค่อยส่งไปให้ AI ---
    if user_message in ["งาน", "การบ้าน", "เช็คงาน"]:
        reply_message = TextMessage(text=f'นี่คือลิงก์เช็คงานห้องเรานะครับ:\n{worksheet_link}')
    elif user_message in ["เว็บโรงเรียน", "โรงเรียนเบญ", "เว็บ"]:
        reply_message = TextMessage(text=f'นี่คือลิงก์เว็บโรงเรียนนะครับ:\n{school_link}')
    elif user_message in ["ตารางเรียน", "ตารางสอน"]:
        reply_message = ImageMessage(original_content_url=timetable_img, preview_image_url=timetable_img)
    elif user_message in ["เกรด", "ดูเกรด"]:
        reply_message = TextMessage(text=f'นี่คือลิงก์เว็บดูเกรดนะครับ:\n{grade_link}')
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
        # --- ถ้าไม่ใช่คำสั่งเฉพาะ ให้ส่งไปที่ Gemini AI ---
        if model:
            try:
                # ส่งข้อความของผู้ใช้ไปให้ Gemini AI
                response = model.generate_content(user_message)
                # นำคำตอบที่ได้มาสร้างเป็นข้อความตอบกลับ
                reply_message = TextMessage(text=response.text)
            except Exception as e:
                # หากเกิดข้อผิดพลาด ให้ตอบข้อความนี้แทน
                print(f"Gemini API Error: {e}")
                reply_message = TextMessage(text="ขออภัยครับ ตอนนี้ผมมีปัญหาในการเชื่อมต่อกับ AI ลองใหม่อีกครั้งนะ")
        else:
            reply_message = TextMessage(text="ขออภัยครับ ระบบ AI ยังไม่ได้ตั้งค่าอย่างสมบูรณ์")
            
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply_message]))
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'
if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
