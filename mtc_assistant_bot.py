# -*- coding: utf-8 -*-
"""
MTC Assistant v9.6 (Enhanced Logging + Robust AI handling)
LINE Bot ผู้ช่วยสำหรับห้องเรียน ม.4/2 ที่รวมการทำงานแบบกำหนดคำสั่ง (Rule-based)
และตอบคำถามทั่วไปด้วย Generative AI (Gemini)
"""
# (ไฟล์นี้เป็นเวอร์ชันปรับปรุงเฉพาะจุดเพื่อแก้ปัญหา responses ขาดและการตอบซ้ำ)
import os
import datetime
import logging
from zoneinfo import ZoneInfo
from flask import Flask, request, abort

import google.generativeai as genai
import google.api_core.exceptions
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, ImageMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

app = Flask(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not ACCESS_TOKEN or not CHANNEL_SECRET:
    app.logger.error("CHANNEL_ACCESS_TOKEN and CHANNEL_SECRET must be set in environment variables.")
    raise SystemExit("Missing required LINE channel credentials")

WORKSHEET_LINK = "https://docs.google.com/spreadsheets/d/1oCG--zkyp-iyJ8iFKaaTrDZji_sds2VzLWNxOOh7-xk/edit?usp=sharing"
SCHOOL_LINK = "https://www.ben.ac.th/main/"
TIMETABLE_IMG = "https://img5.pic.in.th/file/secure-sv1/-2395abd52df9b5e08.jpg"
GRADE_LINK = "http://www.dograde2.online/bjrb/"
ABSENCE_LINK = "https://forms.gle/WjCBTYNxEeCpHShr9"

EXAM_DATES = {
    "กลางภาค": datetime.date(2025, 12, 15),
    "ปลายภาค": datetime.date(2026, 2, 15)
}

SCHEDULE = {
    0: [ ... ],  # ตัดทอนมาให้เหมือนต้นฉบับ (ไม่เปลี่ยน)
    1: [ ... ],
    2: [ ... ],
    3: [ ... ],
    4: [ ... ],
}

configuration = Configuration(access_token=ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
gemini_model = None

try:
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        system_instruction = (
            "คุณคือผู้ช่วย AI สำหรับนักเรียนมัธยม ให้ตอบสั้น กระชับ สุภาพ และเป็นประโยชน์ "
            "ห้ามเผยข้อมูลที่เป็นความลับหรือข้อมูลส่วนบุคคลของผู้ใช้ หากคำถามขัดต่อนโยบาย ให้ปฏิเสธอย่างสุภาพ"
        )
        generation_config = {
            "temperature": 0.7,
            "top_p": 1,
            "top_k": 40,
            "max_output_tokens": 1024,
        }
        try:
            gemini_model = genai.GenerativeModel(
                'gemini-2.5-flash',
                generation_config=generation_config,
                system_instruction=system_instruction
            )
            app.logger.info("Gemini AI configured successfully.")
        except Exception:
            app.logger.exception("Failed to initialize Gemini model. AI features disabled.")
            gemini_model = None
    else:
        app.logger.warning("GEMINI_API_KEY not set. AI disabled.")
except Exception:
    app.logger.exception("Error configuring Gemini AI; continuing without AI.")
    gemini_model = None

def get_next_class_info() -> str:
    now = datetime.datetime.now(tz=ZoneInfo("Asia/Bangkok"))
    weekday = now.weekday()
    current_time = now.time()
    if weekday not in SCHEDULE:
        return "วันนี้ไม่ใช่วันเรียนครับ 🎉"
    for period in SCHEDULE[weekday]:
        start_time = datetime.datetime.strptime(period["start"], "%H:%M").time()
        if current_time < start_time:
            return (f"คาบต่อไป มีรายละเอียดดังนี้ครับ\n"
                    f"เริ่มคาบ: {period['start']}\n"
                    f"จบคาบ: {period['end']}\n"
                    f"วิชา: {period['subject']}\n"
                    f"ห้อง: {period['room']}")
    return "วันนี้ไม่มีคาบเรียนแล้วครับ กลับบ้านได้เลย 🏠"

def create_countdown_message(exam_name: str, exam_date: datetime.date) -> str:
    today = datetime.date.today()
    delta = exam_date - today
    days_left = delta.days
    if days_left > 0:
        return f"เหลืออีก {days_left} วันจะถึงวันสอบ {exam_name} ({exam_date.strftime('%d %b %Y')}) นะครับ"
    elif days_left == 0:
        return f"วันนี้วันสอบ {exam_name} แล้ว โชคดีนะครับ :)"
    else:
        return f"การสอบ {exam_name} เสร็จสิ้นแล้วครับ"

def get_gemini_response(user_message: str) -> str:
    """
    Robust Gemini response:
    - จำกัดความยาว input
    - พยายามอ่าน stream ให้จบ
    - ถ้า stream ไม่เป็น iterator หรือเกิดปัญหา ให้ fallback ไปเรียกแบบ non-stream (synchronous)
    - ตรวจ prompt_feedback อย่างปลอดภัย
    """
    if not gemini_model:
        return "ขออภัยครับ ระบบ AI ของส่วนนี้ยังไม่สามารถใช้งานได้ในขณะนี้"

    # ป้องกันข้อความยาวเกินและ prompt injection เบื้องต้น
    MAX_USER_MESSAGE = 2000
    if len(user_message) > MAX_USER_MESSAGE:
        user_message = user_message[:MAX_USER_MESSAGE]

    try:
        # พยายามใช้ streaming ก่อน (ถ้าไลบรารีรองรับ)
        try:
            response_stream = gemini_model.generate_content(user_message, stream=True)
        except TypeError:
            # ไลบรารีอาจไม่รองรับ stream parameter ในเวอร์ชันบางตัว -> fallback
            response_stream = None

        full_response = ""

        if response_stream is not None:
            # ถ้า response_stream เป็น iterator ให้วนอ่านจนจบ
            try:
                for chunk in response_stream:
                    text_chunk = getattr(chunk, 'text', None) or getattr(chunk, 'content', None)
                    if text_chunk:
                        full_response += text_chunk
            except TypeError:
                # response_stream ไม่ใช่ iterable — fallback ไปแบบ non-stream
                response_stream = None

            # ถ้ามี prompt_feedback ตรวจสอบอย่างปลอดภัย
            pf = getattr(response_stream, 'prompt_feedback', None) if response_stream is not None else None
            if pf and getattr(pf, 'block_reason', None):
                app.logger.warning("Prompt blocked: %s", getattr(pf, 'block_reason', None))
                return "ขออภัยครับ คำขอของคุณอาจขัดต่อนโยบายความปลอดภัย"
        # ถ้าไม่ได้ใช้ stream หรือเกิดปัญหา ให้เรียกแบบ synchronous/fallback
        if not response_stream:
            response = gemini_model.generate_content(user_message)
            # response อาจมีหลายฟิลด์ ขึ้นกับเวอร์ชัน ไลบรารี
            full_response = getattr(response, 'text', None) or getattr(response, 'content', None) or ""
            pf = getattr(response, 'prompt_feedback', None)
            if pf and getattr(pf, 'block_reason', None):
                app.logger.warning("Prompt blocked (sync): %s", getattr(pf, 'block_reason', None))
                return "ขออภัยครับ คำขอของคุณอาจขัดต่อนโยบายความปลอดภัย"

        reply_text = full_response.strip()
        return reply_text if reply_text else "ขออภัยครับ ผมไม่สามารถให้คำตอบในเรื่องนี้ได้"
    except google.api_core.exceptions.PermissionDenied as e:
        app.logger.error("Gemini API Permission Denied: %s", e)
        return "เกิดข้อผิดพลาดในการยืนยันตัวตนกับ AI ครับ (API Key อาจไม่ถูกต้อง)"
    except google.api_core.exceptions.ResourceExhausted as e:
        app.logger.error("Gemini API Quota Exceeded: %s", e)
        return "ขออภัยครับ ตอนนี้โควต้าการใช้งาน AI เต็มแล้วสำหรับวันนี้"
    except Exception:
        app.logger.exception("Unexpected error in get_gemini_response")
        return "ขออภัยครับ เกิดข้อผิดพลาดที่ไม่คาดคิดในการเชื่อมต่อกับ AI"

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
    except Exception:
        app.logger.exception("Error sending reply to LINE")

# --- Commands (ฟังก์ชันทั้งหมดรองรับ optional msg เพื่อเรียกง่าย) ---
def get_worksheet_message(msg=None): return TextMessage(text=f'นี่คือลิงก์เช็คงานห้องเรานะครับ\n{WORKSHEET_LINK}')
def get_school_link_message(msg=None): return TextMessage(text=f'นี่คือลิงก์เว็บโรงเรียนนะครับ\n{SCHOOL_LINK}')
def get_timetable_image_message(msg=None): return ImageMessage(original_content_url=TIMETABLE_IMG, preview_image_url=TIMETABLE_IMG)
def get_grade_link_message(msg=None): return TextMessage(text=f'นี่คือลิงก์เว็บดูเกรดนะครับ\n{GRADE_LINK}')
def get_next_class_message(msg=None): return TextMessage(text=get_next_class_info())
def get_absence_form_message(msg=None): return TextMessage(text=f'นี่คือแบบฟอร์มลากิจ-ลาป่วยนะครับ\n{ABSENCE_LINK}')
def get_help_message(msg=None):
    help_text = (
        'คำสั่งทั้งหมด (พิมพ์คำสั้น ๆ ก็ได้)\n'
        '- "งาน" / "การบ้าน" / "เช็คงาน"\n'
        '- "เว็บ" / "เว็บโรงเรียน"\n'
        '- "ตารางเรียน" / "ตารางสอน"\n'
        '- "เกรด" / "ดูเกรด"\n'
        '- "คาบต่อไป" / "เรียนอะไร"\n'
        '- "ลาป่วย" / "ลากิจ" / "ลา"\n'
        '- "สอบ" / "สอบ กลางภาค" / "สอบ ปลายภาค"\n'
        'หรือพิมพ์คำถามทั่วไปเพื่อให้ AI ช่วยตอบ'
    )
    return TextMessage(text=help_text)

def get_exam_countdown_message(user_message: str):
    if "กลางภาค" in user_message:
        reply_text = create_countdown_message("กลางภาค", EXAM_DATES["กลางภาค"])
    elif "ปลายภาค" in user_message:
        reply_text = create_countdown_message("ปลายภาค", EXAM_DATES["ปลายภาค"])
    else:
        midterm = create_countdown_message("กลางภาค", EXAM_DATES["กลางภาค"])
        final = create_countdown_message("ปลายภาค", EXAM_DATES["ปลายาภาค"] if "ปลายาภาค" in EXAM_DATES else EXAM_DATES["ปลายาภาค"])
        reply_text = f"{midterm}\n\n{final}"
    return TextMessage(text=reply_text)

COMMANDS = [
    (("งาน", "การบ้าน", "เช็คงาน"), get_worksheet_message),
    (("เว็บโรงเรียน", "เว็บ"), get_school_link_message),
    (("ตารางเรียน", "ตารางสอน"), get_timetable_image_message),
    (("เกรด", "ดูเกรด"), get_grade_link_message),
    (("คาบต่อไป", "เรียนอะไร", "เรียนไรต่อ"), get_next_class_message),
    (("ลาป่วย", "ลากิจ", "ลา"), get_absence_form_message),
    (("คำสั่ง", "help", "ช่วยเหลือ"), get_help_message),
    (("สอบ",), get_exam_countdown_message),
]

@handler.add(FollowEvent)
def handle_follow(event):
    welcome_message = TextMessage(
        text='สวัสดีครับ! ผมคือ MTC Assistant ผู้ช่วยอเนกประสงค์ของห้อง ม.4/2\n'
             'พิมพ์ "คำสั่ง" เพื่อดูรายการคำสั่งทั้งหมดนะครับ'
    )
    reply_to_line(event.reply_token, [welcome_message])

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    """
    ห่อการประมวลผลภายใน handler ด้วย try/except เพื่อป้องกัน exception
    ที่จะ bubble ขึ้นมาทำให้ Flask คืน 500 และ LINE รีทรายส่งอีกครั้ง
    """
    try:
        user_message = (event.message.text or "").lower().strip()
        reply_message = None

        # Rule-based processing
        for keywords, action in COMMANDS:
            if any(keyword in user_message for keyword in keywords):
                try:
                    reply_message = action(user_message)
                except TypeError:
                    reply_message = action()
                break

        # AI fallback
        if not reply_message:
            ai_response_text = get_gemini_response(user_message)
            reply_message = TextMessage(text=ai_response_text)

        if reply_message:
            reply_to_line(event.reply_token, [reply_message])
        else:
            app.logger.warning("No reply generated for: %s", user_message)
    except Exception:
        # จับทุกกรณีและ log เพื่อไม่ให้ exception หลุดไปยัง Flask callback
        app.logger.exception("Unhandled error in handle_message")

@app.route("/callback", methods=['POST'])
def callback():
    """
    Webhook endpoint:
    - หาก signature ผิด -> 400
    - หากเกิดข้อผิดพลาดภายหลังในการประมวลผล event จะไม่ abort(500) อีกต่อไป
      (ลดโอกาส LINE รีทรายส่งซ้ำ)
    """
    signature = request.headers.get('X-Line-Signature')
    if not signature:
        app.logger.error("Missing X-Line-Signature header")
        abort(400)

    body = request.get_data(as_text=True)
    app.logger.info("Request body (truncated): %s", body[:500])

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        app.logger.error("Invalid signature.")
        abort(400)
    except Exception:
        # Log exception but return 200 OK to avoid duplicate delivery from LINE.
        app.logger.exception("Error while handling webhook; returning OK to avoid retries.")
        return 'OK'
    return 'OK'

@app.route("/", methods=['GET'])
def home():
    return "MTC Assistant is running!"

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5001))
    app.run(host='0.0.0.0', port=port)
