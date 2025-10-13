# -*- coding: utf-8 -*-

# นี่คือสมองของ "MTC Assistant" ของเรา
# เราจะใช้ไลบรารีของ LINE และ Flask ในการสร้างบอท

import os
from flask import Flask, request, abort

from linebot.v3 import (
    WebhookHandler
)
from linebot.v3.exceptions import (
    InvalidSignatureError
)
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    FollowEvent
)

# สร้าง Web Server ด้วย Flask
app = Flask(__name__)

# ดึงค่า Channel Access Token และ Channel Secret จาก Environment Variables
# เพื่อความปลอดภัย เราจะไม่เขียนค่าพวกนี้ลงไปในโค้ดตรงๆ
# เราจะไปตั้งค่านี้ใน Render แทน (ตามคู่มือ)
ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')

# ตั้งค่าการเชื่อมต่อกับ LINE Messaging API
configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ------------ ส่วนจัดการ Event ต่างๆ ------------

# Event: เมื่อมีคนเพิ่มบอทเป็นเพื่อน
@handler.add(FollowEvent)
def handle_follow(event):
    """
    ฟังก์ชันนี้จะทำงานเมื่อมีผู้ใช้ใหม่เพิ่มบอทเป็นเพื่อน
    จะส่งข้อความต้อนรับกลับไป
    """
    welcome_message = TextMessage(
        text='สวัสดี! เรา MTC Assistant เองนะ\nผู้ช่วยแจ้งข่าวสารและตารางงานของห้อง ม.4/2\n\nพิมพ์ "งาน" หรือ "การบ้าน" เพื่อดูลิงก์ตารางงานทั้งหมดได้เลย!'
    )
    
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[welcome_message]
            )
        )

# Event: เมื่อมีคนส่งข้อความเข้ามา
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """
    ฟังก์ชันนี้จะทำงานเมื่อผู้ใช้ส่งข้อความเป็น Text เข้ามา
    เราจะเช็คว่าข้อความคืออะไร แล้วตอบกลับไปตามที่ตั้งค่าไว้
    """
    user_message = event.message.text.lower().strip() # นำข้อความมาทำเป็นตัวพิมพ์เล็กและตัดช่องว่าง
    
    # *** แก้ไขลิงก์ Google Sheets ของห้องเราตรงนี้! ***
    # ใส่ลิงก์ในเครื่องหมายคำพูด ""
    worksheet_link = "https://docs.google.com/spreadsheets/d/1oCG--zkyp-iyJ8iFKaaTrDZji_sds2VzLWNxOOh7-xk/edit?usp=sharing"
    
    reply_message = None

    # เงื่อนไขการตอบกลับ
    if user_message in ["งาน", "การบ้าน", "เช็คงาน"]:
        reply_message = TextMessage(
            text=f'นี่คือลิงก์สำหรับเช็คงานทั้งหมดของห้องเรานะ:\n{worksheet_link}'
        )
    else:
        # ถ้าพิมพ์อย่างอื่นมา อาจจะให้บอทแนะนำตัวเอง
        reply_message = TextMessage(
            text='พิมพ์ "งาน" หรือ "การบ้าน" เพื่อดูลิงก์ตารางงานทั้งหมดนะ'
        )

    # ส่งข้อความตอบกลับ
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[reply_message]
            )
        )

# ------------ ส่วน Webhook (ประตูรับข้อความจาก LINE) ------------

@app.route("/callback", methods=['POST'])
def callback():
    """
    นี่คือเส้นทางที่ LINE จะส่งข้อมูลมาให้เรา
    โค้ดส่วนนี้ไม่ต้องแก้ไข
    """
    # get X-Line-Signature header value
    signature = request.headers['X-Line-Signature']

    # get request body as text
    body = request.get_data(as_text=True)
    app.logger.info("Request body: " + body)

    # handle webhook body
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.info("Invalid signature. Please check your channel access token/channel secret.")
        abort(400)

    return 'OK'

# ------------ ส่วนสำหรับรัน Server (เมื่ออยู่บน Render) ------------
# โค้ดส่วนนี้ไม่ต้องแก้ไข
if __name__ == "__main__":
    # ใช้ port ที่ Render กำหนดให้ หรือ 5001 ถ้าไม่ได้กำหนด
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)

