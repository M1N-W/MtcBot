# -*- coding: utf-8 -*-

# MTC Assistant v7: อัปเกรดสู่ความเป็นอัจฉริยะ! เพิ่มฟังก์ชันแจ้งเตือนคาบเรียน

import os
import datetime
from zoneinfo import ZoneInfo # --- 1. นำเข้าเครื่องมือจัดการโซนเวลา ---
from flask import Flask, request, abort

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, ImageMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

app = Flask(__name__)
ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# --- 2. สร้างฐานข้อมูลตารางเรียน ม.4/2 ---
# (อ้างอิงจากรูปภาพที่นายเคยส่งให้)
SCHEDULE = {
    0: [ # วันจันทร์
        {"start": "08:30", "end": "09:25", "subject": "ว30202 ครูอรัญ", "room": "331"},
        {"start": "09:25", "end": "10:20", "subject": "ว30202 ครูอรัญ", "room": "331"},
        {"start": "10:20", "end": "11:15", "subject": "ค30222 ครูวิทยาภรณ์", "room": "311"},
        {"start": "11:15", "end": "12:10", "subject": "แนะแนว ครูศศิพร", "room": "947"},
        {"start": "13:05", "end": "14:00", "subject": "ศ31102 ครูรุ่งนลิน", "room": "575"},
        {"start": "14:00", "end": "14:55", "subject": "ง31204 ครูจิรชยา", "room": "947"},
        {"start": "14:55", "end": "15:50", "subject": "พ31204 ครูมานพ", "room": "947"},
        {"start": "15:50", "end": "16:45", "subject": "พ31204 ครูมานพ", "room": "947"},
    ],
    1: [ # วันอังคาร
        {"start": "08:30", "end": "09:25", "subject": "ว30222 ครูวิทยาภรณ์", "room": "311"},
        {"start": "09:25", "end": "10:20", "subject": "ว30222 ครูวิทยาภรณ์", "room": "311"},
        {"start": "10:20", "end": "11:15", "subject": "ว30202 ครูอรัญ", "room": "333"},
        {"start": "11:15", "end": "12:10", "subject": "ว30202 ครูอรัญ", "room": "333"},
        {"start": "13:05", "end": "14:00", "subject": "ค31202 ครูมานพ", "room": "947"},
        {"start": "14:00", "end": "14:55", "subject": "ส31103 ครูบังอร", "room": "947"},
        {"start": "14:55", "end": "15:50", "subject": "ท31102 ครูเบญจมาศ", "room": "947"},
        {"start": "15:50", "end": "16:45", "subject": "อ31102 ครูวาสนา", "room": "947"},
    ],
    2: [ # วันพุธ
        {"start": "08:30", "end": "09:25", "subject": "อ31102 ครูวาสนา", "room": "947"},
        {"start": "09:25", "end": "10:20", "subject": "ค31202 ครูมานพ", "room": "947"},
        {"start": "10:20", "end": "11:15", "subject": "ส31104 ครูจารุพร", "room": "947"},
        {"start": "11:15", "end": "12:10", "subject": "ค31102 ครูจริยา", "room": "947"},
        # 12:10 - 14:55 คือ โฮมรูม, หน้าที่, ประชุม, กิจกรรม
    ],
    3: [ # วันพฤหัสบดี
        {"start": "08:30", "end": "09:25", "subject": "ค31202 ครูมานพ", "room": "947"},
        {"start": "09:25", "end": "10:20", "subject": "ค31202 ครูมานพ", "room": "947"},
        {"start": "10:20", "end": "11:15", "subject": "ว30242 ครูพิมลพรรษ", "room": "323"},
        {"start": "11:15", "end": "12:10", "subject": "ท31102 ครูเบญจมาศ", "room": "947"},
        {"start": "13:05", "end": "14:00", "subject": "พ31102 ครูเศรษฐ์", "room": "โดม2"},
        {"start": "14:00", "end": "14:55", "subject": "อ31208 ครูก.ไอรีน", "room": "947"},
        {"start": "14:55", "end": "15:50", "subject": "ค31102 ครูจริยา", "room": "947"},
    ],
    4: [ # วันศุกร์
        {"start": "08:30", "end": "09:25", "subject": "ว30242 ครูพิมลพรรษ", "room": "323"},
        {"start": "09:25", "end": "10:20", "subject": "ว30242 ครูพิมลพรรษ", "room": "323"},
        {"start": "10:20", "end": "11:15", "subject": "อ31102 ครูวาสนา", "room": "947"},
        {"start": "11:15", "end": "12:10", "subject": "ส31103 ครูบังอร", "room": "947"},
        {"start": "13:05", "end": "14:00", "subject": "ว31287 ครูจินดาพร", "room": "221"},
        {"start": "14:00", "end": "14:55", "subject": "ว31287 ครูจินดาพร", "room": "221"},
        {"start": "14:55", "end": "15:50", "subject": "I30202 ครูจริยา", "room": "947"},
        {"start": "15:50", "end": "16:45", "subject": "I30202 ครูจริยา", "room": "947"},
    ]
}

# --- 3. สร้างฟังก์ชันผู้ช่วยอัจฉริยะ ---
def get_next_class_info():
    """ฟังก์ชันนี้จะตรวจสอบเวลาปัจจุบันและบอกคาบเรียนต่อไป"""
    now = datetime.datetime.now(tz=ZoneInfo("Asia/Bangkok"))
    weekday = now.weekday() # วันจันทร์ = 0, อังคาร = 1, ...
    current_time = now.time()

    if weekday not in SCHEDULE: # ถ้าเป็นวันเสาร์-อาทิตย์
        return "วันนี้วันหยุดพักผ่อน ไม่มีเรียนครับ! 🎉"

    day_schedule = SCHEDULE[weekday]
    
    # ค้นหาคาบเรียนต่อไป
    for period in day_schedule:
        start_time = datetime.datetime.strptime(period["start"], "%H:%M").time()
        if current_time < start_time:
            # --- แก้ไขรูปแบบการตอบกลับตรงนี้ ---
            return f"คาบต่อไป:\nเริ่มคาบ: {period['start']}\nจบคาบ: {period['end']}\nวิชา: {period['subject']}\nห้อง: {period['room']}"
    
    # ถ้าไม่เจอคาบต่อไป แสดงว่าหมดคาบเรียนแล้ว
    return "วันนี้ไม่มีคาบเรียนแล้วครับ กลับบ้านได้! 🏠"

# ... (โค้ดส่วน FollowEvent และ create_countdown_message เหมือนเดิม) ...
def create_countdown_message(exam_name, exam_date):
    """ฟังก์ชันนี้จะรับชื่อวันสอบและวันที่มา แล้วส่งข้อความนับถอยหลังกลับไป"""
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
    welcome_message = TextMessage(
        text='สวัสดีคับ! ผมคือ MTC Assistant\nผู้ช่วยสำหรับห้อง ม.4/2\n\n- พิมพ์ "งาน"\n- พิมพ์ "เว็บ"\n- พิมพ์ "ตารางเรียน"\n- พิมพ์ "อีกกี่วันสอบ"\n- พิมพ์ "คาบต่อไป"'
    )
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[welcome_message]
            )
        )


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
    
    # --- 4. เพิ่มเงื่อนไขใหม่สำหรับฟังก์ชันอัจฉริยะ! ---
    elif user_message in ["คาบต่อไป", "เรียนอะไร", "เรียนไรต่อ"]:
        reply_text = get_next_class_info()
        reply_message = TextMessage(text=reply_text)
        
    else:
        reply_message = TextMessage(
            text='ผมไม่เข้าใจคำสั่งครับ ลองพิมพ์:\n- "งาน"\n- "เว็บ"\n- "ตารางเรียน"\n- "เกรด"\n- "อีกกี่วันสอบ"\n- "คาบต่อไป"'
        )   
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[reply_message]
            )
        )

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

