# -*- coding: utf-8 -*-
import os
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

app = Flask(__name__)
ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

@handler.add(FollowEvent)
def handle_follow(event):
    # โค้ดส่วนนี้เหมือนเดิม
    welcome_message = TextMessage(text='สวัสดี! เรา MTC Assistant เองนะ\nผู้ช่วยอัจฉริยะของห้อง ม.4/2\n\nแตะที่เมนูด้านล่างเพื่อดูข้อมูลต่างๆ ได้เลย!')
    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=event.reply_token, messages=[welcome_message]))

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_message = event.message.text.lower().strip()
    worksheet_link = "https://docs.google.com/spreadsheets/d/1oCG--zkyp-iyJ8iFKaaTrDZji_sds2VzLWNxOOh7-xk/edit?usp=sharing"
    reply_message = None

    # --- อัปเดตเงื่อนไขตรงนี้ ---
    if user_message == "เช็คงานทั้งหมด":
        reply_message = TextMessage(text=f'นี่คือลิงก์สำหรับเช็คงานทั้งหมดของห้องเรานะ:\n{worksheet_link}')
    elif user_message == "เกี่ยวกับบอท":
        reply_message = TextMessage(text='เราคือ MTC Assistant ผู้ช่วยสำหรับห้อง ม.4/2 สร้างโดย Candidate หัวหน้าห้อง เพื่อให้ทุกคนเช็คงานและข้อมูลต่างๆ ได้ง่ายขึ้น!')
    else:
        # ถ้าพิมพ์มานอกเหนือจากเมนู ให้บอทตอบแบบนี้
        reply_message = TextMessage(text='ขออภัย เราไม่เข้าใจคำสั่ง ลองใช้เมนูด้านล่างดูนะ')

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)
        line_bot_api.reply_message_with_http_info(ReplyMessageRequest(reply_token=event.reply_token, messages=[reply_message]))

@app.route("/callback", methods=['POST'])
def callback():
    # โค้ดส่วนนี้เหมือนเดิม
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
