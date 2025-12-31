# -*- coding: utf-8 -*-
"""
MTC Assistant v.18.5 (V.18 Hardened Base + V.19 Database Features)
- Base: V.18 (Multi-exam dates, Robust logging, Rate limiting, Safe parsing)
- Added: Firebase Integration & Homework Management from V.19
- Preserved: All V.18 logic and features without cuts.
"""

import os
import datetime
import logging
import re
import json
import math
import time
import threading
import functools
from typing import Optional, List, Dict, Tuple
from zoneinfo import ZoneInfo

import requests
from flask import Flask, request, abort, jsonify

import google.generativeai as genai
# --- Firebase Imports (From V.19) ---
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
# ------------------------------------

from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, ImageMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

# ---------------------------
# Configuration & Logging
# ---------------------------
app = Flask(__name__)

# Use V.18's robust logging configuration
LOG_LEVEL = logging.DEBUG if os.environ.get("DEBUG", "false").lower() in ("1", "true", "yes") else logging.INFO
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("mtc_assistant")
logger.setLevel(LOG_LEVEL)
app.logger.handlers = logger.handlers
app.logger.setLevel(LOG_LEVEL)

# ---------------------------
# ENV / Credentials
# ---------------------------
ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY') # Added from V.19
FIREBASE_KEY_PATH = "firebase_key.json"             # Added from V.19

# Safe PORT parsing from V.18
try:
    PORT = int(os.environ.get('PORT', 5001))
except (ValueError, TypeError):
    logger.warning("Invalid PORT value, using default 5001")
    PORT = 5001

FLASK_DEBUG = os.environ.get('FLASK_DEBUG', 'false').lower() == 'true'

if not ACCESS_TOKEN:
    logger.warning("CHANNEL_ACCESS_TOKEN not set; LINE API calls will fail.")
if not CHANNEL_SECRET:
    logger.warning("CHANNEL_SECRET not set; signature verification may fail.")
if not GEMINI_API_KEY:
    logger.info("GEMINI_API_KEY not set; AI features disabled.")

# ---------------------------
# Firebase Initialization (From V.19)
# ---------------------------
db = None
try:
    if os.path.exists(FIREBASE_KEY_PATH):
        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_KEY_PATH)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        logger.info("🔥 Firebase Connected Successfully!")
    else:
        logger.warning(f"⚠️ Missing {FIREBASE_KEY_PATH}. Homework DB features will be disabled.")
except Exception as e:
    logger.exception(f"❌ Firebase Init Error: {e}")

# ---------------------------
# Constants & Messages (From V.18)
# ---------------------------
WORKSHEET_LINK = "https://docs.google.com/spreadsheets/d/1SwKs4s8HJt2HxAzj_StIh_nopVMe1kwqg7yW13jOdQ4/edit?usp=sharing"
SCHOOL_LINK = "https://www.ben.ac.th/main/"
TIMETABLE_IMG = "https://img5.pic.in.th/file/secure-sv1/-2395abd52df9b5e08.jpg"
GRADE_LINK = "http://www.dograde2.online/bjrb/"
ABSENCE_LINK = "https://forms.gle/WjCBTYNxEeCpHShr9"
Bio_LINK = "https://drive.google.com/file/d/1zd5NND3612JOym6HSzKZnqAS42TH9gmh/view?usp=sharing"
Physic_LINK = "https://drive.google.com/file/d/15oSPs3jFYpvJRUkFqrCSpETGwOoK0Qpv/view?usp=sharing"

MESSAGES = {
    "IDENTITY":  (
        "ผมเป็นบอทผู้ช่วยอเนกประสงค์ของห้อง MTC ม.4/2 "
        "ผมช่วยได้หลายอย่าง เช่น แจ้งตาราง, ลิงก์เว็บโรงเรียน, หาตารางสอน, "
        "เช็คเกรด, ดูเวลาคาบถัดไป, และตอบคำถามต่าง ๆ ด้วยเอไอ"
    ),
    "AI_DISABLED": "ขออภัยครับ ระบบ AI ยังไม่เปิดใช้งานในขณะนี้",
    "AI_NO_RESPONSE": "ขออภัยครับ ระบบ AI ตอบไม่ได้ในขณะนี้ ลองใหม่อีกครั้ง",
    "AI_ERROR": "ขออภัยครับ ตอนนี้ผมมีปัญหาในการเชื่อมต่อกับ AI ลองใหม่อีกครั้งนะ",
    "RATE_LIMITED": "คุณส่งข้อความเร็วจนเกินไป ลองช้าลงอีกนิดนะครับ",
    "INVALID_MESSAGE": "ขออภัยครับ ผมรับข้อความประเภทนี้ไม่ได้นะ ลองพิมพ์ข้อความ",
    "NO_CLASS_TODAY": "วันนี้วันหยุดไม่ใช่วันเรียน กลับไปนอนไป้ 🎉",
    "NO_CLASS_LEFT": "วันนี้ไม่มีคาบเรียนแล้วครับ กลับบ้านไปนอนได้เลย 🏠",
    "ACTION_ERROR": "ขออภัยครับ เกิดข้อผิดพลาดขณะประมวลผลคำสั่งของคุณ",
}

# --- Multi-date EXAM_DATES (V.18 Logic - PRESERVED) ---
EXAM_DATES = {
    "กลางภาค": [
        datetime.date(2025, 12, 21),
        datetime.date(2025, 12, 23),
        datetime.date(2025, 12, 25),
    ],
    "ปลายภาค": [
        datetime.date(2026, 2, 20),
        datetime.date(2026, 2, 22),
        datetime.date(2026, 2, 24),
    ]
}

LINE_MAX_TEXT = 5000
LINE_SAFE_TRUNCATE = 4800
LOCAL_TZ = ZoneInfo("Asia/Bangkok")

# ---------------------------
# Thread-safe rate limiter (V.18)
# ---------------------------
RATE_LIMIT_MAX = int(os.environ.get("RATE_LIMIT_MAX", 6))
RATE_LIMIT_WINDOW = int(os.environ.get("RATE_LIMIT_WINDOW", 60))
_user_message_history: Dict[str, List[float]] = {}
_rate_limit_lock = threading.Lock()

def is_rate_limited(user_id: str) -> bool:
    """Check if user is rate limited with thread-safe access"""
    now_ts = time.time()
    with _rate_limit_lock:
        history = _user_message_history.get(user_id, [])
        recent = [t for t in history if now_ts - t < RATE_LIMIT_WINDOW]
        recent.append(now_ts)
        _user_message_history[user_id] = recent
        if len(recent) > RATE_LIMIT_MAX:
            logger.debug("User %s exceeded rate limit (%d/%d)", user_id, len(recent), RATE_LIMIT_MAX)
            return True
    return False

# ---------------------------
# Class Schedule (V.18)
# ---------------------------
SCHEDULE = {
    0: [  # วันจันทร์
        {"start": "08:30", "end": "09:25", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "331"},
        {"start": "09:25", "end": "10:20", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "331"},
        {"start": "10:20", "end": "11:15", "subject": "เคมี (ครูพิทยาภรณ์)", "room": "311"},
        {"start": "11:15", "end": "12:10", "subject": "แนะแนว (ครูทศพร)", "room": "947"},
        {"start": "13:05", "end": "14:00", "subject": "นาฏศิลป์ (ครูบังเอิญ)", "room": "575"},
        {"start": "14:00", "end": "14:55", "subject": "การงานอาชีพ (ครูอัญชลี)", "room": "947"},
        {"start": "14:55", "end": "15:50", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start": "15:50", "end": "16:45", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
    ],
    1: [  # วันอังคาร
        {"start": "08:30", "end": "09:25", "subject": "เคมี (ครูพิทยาภรณ์)", "room": "311"},
        {"start": "09:25", "end": "10:20", "subject": "เคมี (ครูพิทยาภรณ์)", "room": "311"},
        {"start": "10:20", "end": "11:15", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "333"},
        {"start": "11:15", "end": "12:10", "subject": "ฟิสิกส์ (ครูธนธัญ)", "room": "333"},
        {"start": "13:05", "end": "14:00", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start": "14:00", "end": "14:55", "subject": "สังคมศึกษา (ครูบังอร)", "room": "947"},
        {"start": "14:55", "end": "15:50", "subject": "ไทย (ครูเบญจมาศ)", "room": "947"},
        {"start": "15:50", "end": "16:45", "subject": "อังกฤษพื้นฐาน (ครูวาสนา)", "room": "947"},
    ],
    2: [  # วันพุธ
        {"start": "08:30", "end": "09:25", "subject": "อังกฤษพื้นฐาน (ครูวาสนา)", "room": "947"},
        {"start": "09:25", "end": "10:20", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start": "10:20", "end": "11:15", "subject": "ประวัติศาสตร์ (ครูณฐพร)", "room": "947"},
        {"start": "11:15", "end": "12:10", "subject": "คณิตพื้นฐาน (ครูปรียา)", "room": "947"},
    ],
    3: [  # วันพฤหัสบดี
        {"start":  "08:30", "end":  "09:25", "subject":  "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start": "09:25", "end": "10:20", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start":  "10:20", "end":  "11:15", "subject":  "ชีววิทยา (ครูพิชามญช์)", "room": "323"},
        {"start": "11:15", "end": "12:10", "subject": "ไทย (ครูเบญจมาศ)", "room": "947"},
        {"start": "13:05", "end": "14:00", "subject": "สุขศึกษา&พละศึกษา (ครูนรเศรษฐ์)", "room": "ห้องเรียน/โดม"},
        {"start": "14:00", "end": "14:55", "subject": "อังกฤษเพิ่มเติม (Teacher Mitch)", "room": "947"},
        {"start": "14:55", "end": "15:50", "subject": "คณิตพื้นฐาน (ครูปรียา)", "room": "947"},
    ],
    4: [  # วันศุกร์
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

# ---------------------------
# Initialize LINE and Gemini
# ---------------------------
configuration = Configuration(access_token=ACCESS_TOKEN) if ACCESS_TOKEN else None
handler = WebhookHandler(CHANNEL_SECRET) if CHANNEL_SECRET else None

gemini_model = None
GEMINI_MODEL_NAME = "gemini-3-flash-preview"

try:
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        try:
            if hasattr(genai, "GenerativeModel"):
                gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
                logger.info("Gemini model instantiated successfully.")
            else:
                logger.warning("GenerativeModel not available in genai module")
        except AttributeError as e:
            logger.warning("GenerativeModel not found: %s", e)
        except Exception as e:
            logger.error("Failed to instantiate Gemini model: %s", e, exc_info=True)
    else:
        logger.info("GEMINI_API_KEY not provided; AI features disabled.")
except Exception as e:
    logger.error("Error configuring Gemini API: %s", e, exc_info=True)
    gemini_model = None

# ---------------------------
# Database Functions (Integrated from V.19)
# ---------------------------
def add_homework_to_db(subject: str, detail: str, due_date: str = "ไม่ระบุ") -> str:
    """Add homework to Firestore"""
    if not db:
        return "⚠️ ระบบฐานข้อมูลยังไม่เปิดใช้งาน (Missing Key)"
    try:
        # ใช้ timestamp เป็น ID เพื่อเรียงลำดับง่ายๆ หรือใช้ auto-id
        doc_ref = db.collection('homeworks').add({
            'subject': subject,
            'detail': detail,
            'due_date': due_date,
            'timestamp': firestore.SERVER_TIMESTAMP
        })
        return f"✅ บันทึกการบ้านวิชา '{subject}' เรียบร้อยแล้ว"
    except Exception as e:
        logger.error(f"DB Error: {e}")
        return "❌ เกิดข้อผิดพลาดในการบันทึกข้อมูล"

def get_homeworks_from_db() -> str:
    """Get all homeworks from Firestore"""
    if not db:
        return "⚠️ ระบบฐานข้อมูลยังไม่เปิดใช้งาน"
    try:
        docs = db.collection('homeworks').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        homeworks = []
        for doc in docs:
            data = doc.to_dict()
            homeworks.append(f"📚 วิชา: {data.get('subject')}\n   📝 รายละเอียด: {data.get('detail')}\n   📅 ส่ง: {data.get('due_date')}")
        
        if not homeworks:
            return "🎉 ไม่มีมีการบ้านค้างครับ (หรือยังไม่ได้บันทึก)"
        return "📋 **รายการการบ้าน**\n\n" + "\n----------------\n".join(homeworks)
    except Exception as e:
        logger.error(f"DB Error: {e}")
        return "❌ ไม่สามารถดึงข้อมูลการบ้านได้"

def clear_homework_db() -> str:
    """Clear all homeworks (Optional: For admin or specific command)"""
    if not db: return "⚠️ DB Error"
    try:
        docs = db.collection('homeworks').stream()
        count = 0
        for doc in docs:
            doc.reference.delete()
            count += 1
        return f"🗑️ ลบรายการการบ้านทั้งหมด ({count} รายการ) แล้ว"
    except Exception as e:
        return f"❌ Error clearing DB: {e}"

# ---------------------------
# Helper: safe parse for Gemini responses
# ---------------------------
def _safe_parse_gemini_response(response) -> str:
    try:
        if response is None: return ""
        if hasattr(response, "parts") and response.parts:
            parts = [getattr(part, "text", "") for part in response.parts if getattr(part, "text", None)]
            return "".join(parts).strip()
        if hasattr(response, "text") and getattr(response, "text"):
            return str(getattr(response, "text")).strip()
        if isinstance(response, dict):
            if "text" in response and response["text"]: return str(response["text"]).strip()
        return str(response)
    except Exception as e:
        logger.error("Error parsing Gemini response: %s", e)
        return ""

def get_gemini_response(prompt: str) -> str:
    if not gemini_model:
        return MESSAGES["AI_DISABLED"]
    try:
        response = gemini_model.generate_content(prompt)
        text = _safe_parse_gemini_response(response)
        return text if text else MESSAGES["AI_NO_RESPONSE"]
    except Exception as e:
        logger.error("Gemini Generate Error: %s", e)
        return MESSAGES["AI_ERROR"]

# ---------------------------
# Core Logic Functions (V.18 Style)
# ---------------------------
def get_schedule_text(day_idx: int = None) -> str:
    if day_idx is None:
        day_idx = datetime.datetime.now(LOCAL_TZ).weekday()
    
    if day_idx not in SCHEDULE:
        return MESSAGES["NO_CLASS_TODAY"]
    
    msg_lines = [f"📅 ตารางเรียนวัน{['จันทร์','อังคาร','พุธ','พฤหัส','ศุกร์'][day_idx]}"]
    for slot in SCHEDULE[day_idx]:
        msg_lines.append(f"⏰ {slot['start']}-{slot['end']} : {slot['subject']} ({slot['room']})")
    return "\n".join(msg_lines)

def get_next_class_info() -> str:
    now = datetime.datetime.now(LOCAL_TZ)
    day_idx = now.weekday()
    current_time_str = now.strftime("%H:%M")

    if day_idx not in SCHEDULE:
        return MESSAGES["NO_CLASS_TODAY"]

    for slot in SCHEDULE[day_idx]:
        if current_time_str < slot['start']:
            return f"🔜 คาบต่อไป: {slot['subject']} ({slot['room']}) เวลา {slot['start']}"
        if slot['start'] <= current_time_str < slot['end']:
            return f"⏳ กำลังเรียน: {slot['subject']} ({slot['room']}) จนถึง {slot['end']}"
    
    return MESSAGES["NO_CLASS_LEFT"]

def get_exam_countdown() -> str:
    now = datetime.datetime.now(LOCAL_TZ).date()
    msg_list = ["⏳ **นับถอยหลังสอบ**"]
    found = False
    
    for exam_name, dates in EXAM_DATES.items():
        # V.18 Logic: Handle list of dates
        future_dates = [d for d in dates if d >= now]
        if future_dates:
            found = True
            next_exam = min(future_dates)
            days_left = (next_exam - now).days
            all_dates_str = ", ".join([d.strftime("%d/%m") for d in dates])
            
            if days_left == 0:
                msg_list.append(f"🔥 วันนี้สอบ {exam_name}! ({all_dates_str}) สู้ๆ!")
            else:
                msg_list.append(f"📌 {exam_name} เหลือ {days_left} วัน (เริ่ม {next_exam.strftime('%d/%m')})")
                msg_list.append(f"   (สอบวันที่: {all_dates_str})")
    
    if not found:
        return "🎉 ยังไม่มีสอบเร็วๆ นี้ พักผ่อนได้!"
    return "\n\n".join(msg_list)

# ---------------------------
# LINE Webhook Handler
# ---------------------------
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    
    if not handler:
        abort(500)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e:
        logger.error("Callback error: %s", e)
        abort(500)
    
    return 'OK'

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    
    # 1. Check Rate Limit (V.18)
    if is_rate_limited(user_id):
        reply_text = MESSAGES["RATE_LIMITED"]
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply_text)]))
        return

    reply_msg = None

    # 2. Logic processing (V.18 logic + V.19 DB commands)
    # --- Homework Commands (V.19 Feature) ---
    if text.startswith("สั่งการบ้าน"):
        # Format: สั่งการบ้าน [วิชา] [รายละเอียด] [ส่งวันที่]
        parts = text.split(maxsplit=3)
        if len(parts) >= 3:
            subj = parts[1]
            det = parts[2]
            due = parts[3] if len(parts) > 3 else "ไม่ระบุ"
            res = add_homework_to_db(subj, det, due)
            reply_msg = TextMessage(text=res)
        else:
            reply_msg = TextMessage(text="⚠️ พิมพ์: สั่งการบ้าน [วิชา] [รายละเอียด] [วันส่ง]")
            
    elif text == "การบ้าน" or text == "ดูการบ้าน":
        reply_msg = TextMessage(text=get_homeworks_from_db())
        
    elif text == "ลบการบ้านทั้งหมด" or text == "clear hw":
        reply_msg = TextMessage(text=clear_homework_db())

    # --- Schedule & Info (V.18 Original) ---
    elif "ตาราง" in text and "เรียน" in text:
        reply_msg = TextMessage(text=get_schedule_text())
    elif "คาบต่อไป" in text or "เรียนอะไรต่อ" in text:
        reply_msg = TextMessage(text=get_next_class_info())
    elif "สอบ" in text and "เมื่อไหร่" in text:
        reply_msg = TextMessage(text=get_exam_countdown())
    elif "เกรด" in text:
        reply_msg = TextMessage(text=f"📊 เช็คเกรดได้ที่นี่ครับ: {GRADE_LINK}")
    elif "ใบลากิจ" in text or "ลา" in text:
         reply_msg = TextMessage(text=f"📝 ลิงก์แจ้งลา: {ABSENCE_LINK}")
    
    # --- Fallback to Gemini AI ---
    else:
        # ตอบกลับปกติด้วย AI
        ai_reply = get_gemini_response(text)
        reply_msg = TextMessage(text=ai_reply)

    # 3. Send Reply
    if reply_msg:
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[reply_msg]
                    )
                )
        except Exception as e:
            logger.error("Error sending reply: %s", e)

# ---------------------------
# Flask Routes (Health Check)
# ---------------------------
@app.route("/", methods=['GET'])
def home():
    """Health check and status endpoint"""
    cfg_ok = "OK" if ACCESS_TOKEN and CHANNEL_SECRET else "CONFIG_MISSING"
    gemini_status = "OK" if GEMINI_API_KEY else "MISSING"
    db_status = "OK" if db else "DISCONNECTED"
    return f"MTC Assistant v18.5 (Hybrid) Running! LINE: {cfg_ok}, Gemini: {gemini_status}, DB: {db_status}"

@app.route("/healthz", methods=['GET'])
def healthz():
    return jsonify({
        "status": "ok",
        "time": datetime.datetime.now(tz=LOCAL_TZ).isoformat(),
        "version": "18.5-hybrid",
        "db": bool(db)
    }), 200

# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Starting MTC Assistant v18.5 (Hybrid)...")
    logger.info(f"Port: {PORT}, Debug: {FLASK_DEBUG}")
    app.run(host="0.0.0.0", port=PORT, debug=FLASK_DEBUG)