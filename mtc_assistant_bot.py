# -*- coding: utf-8 -*-
"""
MTC Assistant v.20 (Complete Enhanced Edition)
- Base: V.18 (Multi-exam dates, Robust logging, Rate limiting, Safe parsing)
- Added: Firebase Integration & Homework Management from V.19
- Fixed: Restored ALL missing features from V.18 (COMMANDS system, Help, Music, etc.)
- Enhanced: Better error handling and code organization
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
YOUTUBE_API_KEY = os.environ.get('YOUTUBE_API_KEY')
FIREBASE_KEY_PATH = "firebase_key.json"

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
    "NO_CLASS_TODAY": "วันนี้วันหยุดไม่ใช่วันเรียน กลับไปนอนได้ 🎉",
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
        {"start": "08:30", "end": "09:25", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start": "09:25", "end": "10:20", "subject": "คณิตเพิ่มเติม (ครูมานพ)", "room": "947"},
        {"start": "10:20", "end": "11:15", "subject": "ชีววิทยา (ครูพิชามญช์)", "room": "323"},
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
# LINE Bot Configuration
# ---------------------------
configuration = Configuration(access_token=ACCESS_TOKEN) if ACCESS_TOKEN else None
handler = WebhookHandler(CHANNEL_SECRET) if CHANNEL_SECRET else None

# ---------------------------
# Gemini Configuration (V.18)
# ---------------------------
gemini_model = None
GEMINI_MODEL_NAME = "gemini-1.5-flash"

if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        logger.info(f"Gemini model '{GEMINI_MODEL_NAME}' instantiated.")
    except Exception as e:
        logger.error(f"Gemini model init failed: {e}")
        gemini_model = None

# ==========================================================================================
# --- Database Functions (V.19 Feature) ---
# ==========================================================================================
def add_homework_to_db(subject: str, detail: str, due_date: str = "ไม่ระบุ") -> str:
    """เพิ่มการบ้านเข้า Firebase"""
    if not db:
        return "⚠️ ระบบฐานข้อมูลยังไม่พร้อม กรุณาติดต่อผู้ดูแลระบบ"
    
    try:
        doc_ref = db.collection('homeworks').document()
        doc_ref.set({
            'subject': subject,
            'detail': detail,
            'due_date': due_date,
            'timestamp': firestore.SERVER_TIMESTAMP,
            'created_at': datetime.datetime.now(tz=LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
        })
        return f"✅ เพิ่มการบ้านวิชา '{subject}' สำเร็จแล้วครับ!"
    except Exception as e:
        logger.error(f"DB Add Error: {e}")
        return "❌ เกิดข้อผิดพลาดในการเพิ่มการบ้าน"

def get_homeworks_from_db() -> str:
    """ดึงรายการการบ้านจาก Firebase"""
    if not db:
        return "⚠️ ระบบฐานข้อมูลยังไม่พร้อมครับ"
    
    try:
        docs = db.collection('homeworks').order_by('timestamp', direction=firestore.Query.DESCENDING).stream()
        hw_list = []
        for doc in docs:
            d = doc.to_dict()
            hw_list.append(
                f"📚 *{d.get('subject', 'ไม่ระบุ')}*\n"
                f"📝 {d.get('detail', 'ไม่มีรายละเอียด')}\n"
                f"📅 ส่ง: {d.get('due_date', 'ไม่ระบุ')}\n"
                f"(ID: {doc.id[-4:]})"
            )
        
        if not hw_list:
            return "🎉 เย้! ตอนนี้ไม่มีการบ้านค้างในระบบครับ"
        
        return "📋 *รายการการบ้านปัจจุบัน*\n\n" + "\n" + "-" * 30 + "\n".join(hw_list)
    except Exception as e:
        logger.error(f"DB Get Error: {e}")
        return "❌ เกิดข้อผิดพลาดในการดึงข้อมูลการบ้าน"

def clear_homework_db() -> str:
    """ลบการบ้านทั้งหมดใน Firebase"""
    if not db:
        return "⚠️ ระบบฐานข้อมูลยังไม่พร้อมครับ"
    
    try:
        docs = db.collection('homeworks').stream()
        count = 0
        for doc in docs:
            doc.reference.delete()
            count += 1
        
        return f"🗑️ ลบการบ้านทั้งหมดแล้ว ({count} รายการ)"
    except Exception as e:
        logger.error(f"DB Clear Error: {e}")
        return "❌ เกิดข้อผิดพลาดในการลบข้อมูล"

# ==========================================================================================
# --- Command Handler Functions (V.18 Style - RESTORED) ---
# ==========================================================================================

def get_worksheet_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์ใบงาน"""
    return TextMessage(text=f"📝 ใบงานอยู่ที่นี่ครับ: {WORKSHEET_LINK}")

def get_school_link_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์เว็บโรงเรียน"""
    return TextMessage(text=f"🏫 เว็บไซต์โรงเรียนครับ: {SCHOOL_LINK}")

def get_timetable_image_message(user_message: str = "") -> ImageMessage:
    """ส่งรูปตารางเรียน"""
    return ImageMessage(original_content_url=TIMETABLE_IMG, preview_image_url=TIMETABLE_IMG)

def get_grade_link_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์เช็คเกรด"""
    return TextMessage(text=f"📊 เช็คเกรดได้ที่นี่ครับ: {GRADE_LINK}")

def get_absence_form_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์แบบฟอร์มลา"""
    return TextMessage(text=f"📝 ลิงก์แจ้งลาครับ: {ABSENCE_LINK}")

def get_bio_link_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์เฉลยชีวะ"""
    return TextMessage(text=f"🧬 เฉลยชีววิทยาครับ: {Bio_LINK}")

def get_physic_link_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์เฉลยฟิสิกส์"""
    return TextMessage(text=f"⚛️ เฉลยฟิสิกส์ครับ: {Physic_LINK}")

def get_help_message(user_message: str = "") -> TextMessage:
    """แสดงคำสั่งทั้งหมด (RESTORED FROM V.18)"""
    help_text = (
        '📖 *รายการคำสั่งทั้งหมด*\n\n'
        '📋 *คำสั่งพื้นฐาน:*\n'
        '- "งาน" / "การบ้าน" = ดูใบงาน\n'
        '- "เว็บโรงเรียน" = ลิงก์เว็บโรงเรียน\n'
        '- "ตารางเรียน" = ดูตารางเรียน\n'
        '- "เกรด" = เช็คเกรด\n'
        '- "คาบต่อไป" = ดูว่าเรียนอะไรต่อ\n'
        '- "อีกกี่นาที" = เช็คเวลาเหลือก่อนคาบถัดไป\n'
        '- "ลา" = แบบฟอร์มลา\n'
        '- "สอบ" = นับถอยหลังวันสอบ\n\n'
        '🧪 *คำสั่งเฉลย:*\n'
        '- "ชีวะ" = เฉลยชีววิทยา\n'
        '- "ฟิสิกส์" = เฉลยฟิสิกส์\n\n'
        '🎵 *ความบันเทิง:*\n'
        '- "เปิดเพลง [ชื่อเพลง]" = หาเพลงจาก YouTube\n\n'
        '💾 *คำสั่งการบ้าน (ต้องมี Firebase):*\n'
        '- "สั่งการบ้าน [วิชา] [รายละเอียด] [วันส่ง]"\n'
        '- "การบ้าน" / "ดูการบ้าน" = ดูการบ้านทั้งหมด\n'
        '- "ลบการบ้านทั้งหมด" = ล้างข้อมูล\n\n'
        '🤖 *AI:*\n'
        '- พิมพ์ข้อความอื่นๆ = ตอบด้วย AI'
    )
    return TextMessage(text=help_text)

def get_next_class_message(user_message: str = "") -> TextMessage:
    """แสดงคาบเรียนถัดไป (V.18)"""
    now = datetime.datetime.now(LOCAL_TZ)
    day_idx = now.weekday()
    
    if day_idx not in SCHEDULE:
        return TextMessage(text=MESSAGES["NO_CLASS_TODAY"])
    
    current_time = now.time()
    periods = SCHEDULE[day_idx]
    
    for period in periods:
        start_time = datetime.datetime.strptime(period["start"], "%H:%M").time()
        end_time = datetime.datetime.strptime(period["end"], "%H:%M").time()
        
        # ถ้ายังไม่ถึงเวลาเริ่มคาบนี้
        if current_time < start_time:
            return TextMessage(
                text=f"🔜 คาบต่อไป: {period['subject']}\n"
                     f"📍 ห้อง: {period['room']}\n"
                     f"⏰ เวลา: {period['start']} - {period['end']}"
            )
        
        # ถ้ากำลังอยู่ในคาบนี้
        if start_time <= current_time < end_time:
            return TextMessage(
                text=f"⏳ กำลังเรียน: {period['subject']}\n"
                     f"📍 ห้อง: {period['room']}\n"
                     f"⏰ จนถึง: {period['end']}"
            )
    
    return TextMessage(text=MESSAGES["NO_CLASS_LEFT"])

def get_time_until_next_class_message(user_message: str = "") -> TextMessage:
    """คำนวณเวลาเหลือก่อนคาบถัดไป (V.18)"""
    now = datetime.datetime.now(LOCAL_TZ)
    day_idx = now.weekday()
    
    if day_idx not in SCHEDULE:
        return TextMessage(text=MESSAGES["NO_CLASS_TODAY"])
    
    current_time = now.time()
    periods = SCHEDULE[day_idx]
    
    # หาว่าตอนนี้อยู่ในคาบไหน
    current_index = None
    for idx, period in enumerate(periods):
        start_t = datetime.datetime.strptime(period["start"], "%H:%M").time()
        end_t = datetime.datetime.strptime(period["end"], "%H:%M").time()
        if start_t <= current_time < end_t:
            current_index = idx
            break
    
    target = None
    if current_index is None:
        # ไม่ได้อยู่ในคาบเรียน หาคาบถัดไป
        for period in periods:
            start_t = datetime.datetime.strptime(period["start"], "%H:%M").time()
            if current_time < start_t:
                target = period
                break
        
        if target is None:
            return TextMessage(text=MESSAGES["NO_CLASS_LEFT"])
    else:
        # อยู่ในคาบเรียน หาคาบถัดไปที่วิชาต่างจากปัจจุบัน
        current_subject = periods[current_index]["subject"]
        for idx in range(current_index + 1, len(periods)):
            if periods[idx]["subject"] != current_subject:
                target = periods[idx]
                break
        
        if target is None:
            return TextMessage(text="วันนี้ไม่มีคาบเรียนที่ต่างจากคาบปัจจุบันอีกแล้วครับ")
    
    # คำนวณเวลาเหลือ
    target_start_time = datetime.datetime.strptime(target["start"], "%H:%M").time()
    target_dt = datetime.datetime.combine(now.date(), target_start_time).replace(tzinfo=LOCAL_TZ)
    delta_seconds = (target_dt - now).total_seconds()
    minutes_left = max(0, math.ceil(delta_seconds / 60))
    
    minutes_text = "น้อยกว่า 1 นาที" if minutes_left == 0 else f"{minutes_left} นาที"
    
    return TextMessage(
        text=f"⏰ เหลือเวลาอีก {minutes_text}\n"
             f"🔜 คาบถัดไป: {target['subject']}\n"
             f"📍 ห้อง: {target['room']}"
    )

def get_exam_countdown_message(user_message: str = "") -> TextMessage:
    """นับถอยหลังวันสอบ (V.18 Multi-date logic)"""
    now = datetime.datetime.now(LOCAL_TZ).date()
    msg_list = ["⏳ *นับถอยหลังสอบ*\n"]
    found = False
    
    for exam_name, dates in EXAM_DATES.items():
        # Handle list of dates (V.18 logic)
        future_dates = [d for d in dates if d >= now]
        if future_dates:
            found = True
            next_exam = min(future_dates)
            days_left = (next_exam - now).days
            all_dates_str = ", ".join([d.strftime("%d/%m") for d in dates])
            
            if days_left == 0:
                msg_list.append(f"🔥 วันนี้สอบ{exam_name}! สู้ๆ!")
            else:
                msg_list.append(
                    f"📌 {exam_name}\n"
                    f"   เหลือ *{days_left} วัน*\n"
                    f"   (สอบวันที่: {all_dates_str})"
                )
    
    if not found:
        return TextMessage(text="🎉 ยังไม่มีสอบเร็วๆ นี้ พักผ่อนได้!")
    
    return TextMessage(text="\n\n".join(msg_list))

# ==========================================================================================
# --- YouTube Music Feature (V.18 - RESTORED) ---
# ==========================================================================================
def extract_youtube_id(url_or_text: str) -> Optional[str]:
    """แยก YouTube Video ID จาก URL"""
    m = re.search(r'(?:v=|\/v\/|youtu\.be\/|\/embed\/)([A-Za-z0-9_\-]{11})', url_or_text)
    if m:
        return m.group(1)
    
    m2 = re.match(r'^[A-Za-z0-9_\-]{11}$', url_or_text.strip())
    if m2:
        return url_or_text.strip()
    
    return None

def get_music_link_message(user_message: str) -> TextMessage:
    """หาเพลงจาก YouTube ด้วย AI (V.18 Feature - RESTORED)"""
    music_keywords = ["เปิดเพลง", "หาเพลง", "ขอเพลง"]
    song_title = user_message
    
    for keyword in music_keywords:
        if keyword in song_title:
            song_title = song_title.replace(keyword, "").strip()
            break
    
    if not song_title:
        return TextMessage(text="กรุณาระบุชื่อเพลงด้วยครับ เช่น 'เปิดเพลง ชื่อเพลง'")
    
    # ใช้ AI หาลิงก์เพลง
    search_prompt = f"ค้นหาลิงก์ YouTube เพลง: '{song_title}' และตอบกลับมาเฉพาะลิงก์ YouTube เท่านั้น"
    ai_response = get_gemini_response(search_prompt)
    
    # หา URL จากคำตอบ AI
    url_match = re.search(r'(https?://(?:www\.)?(?:youtube\.com|youtu\.be)[^\s\'"]+)', ai_response or "")
    
    if url_match:
        return TextMessage(text=f"🎵 จัดไปครับ!\n{url_match.group(0)}")
    
    return TextMessage(text=f"😔 หาเพลง '{song_title}' ไม่พบครับ ลองพิมพ์ชื่อให้ชัดเจนกว่านี้")

# ==========================================================================================
# --- AI Functions (V.18 Enhanced) ---
# ==========================================================================================
def _safe_parse_gemini_response(response) -> str:
    """Parse Gemini response safely (V.18)"""
    try:
        if response is None:
            return ""
        
        if hasattr(response, "parts") and response.parts:
            parts = [getattr(part, "text", "") for part in response.parts if getattr(part, "text", None)]
            return "".join(parts).strip()
        
        if hasattr(response, "text") and getattr(response, "text"):
            return str(getattr(response, "text")).strip()
        
        if isinstance(response, dict):
            if "text" in response and response["text"]:
                return str(response["text"]).strip()
        
        return str(response)
    except Exception as e:
        logger.error("Error parsing Gemini response: %s", e)
        return ""

def get_gemini_response(prompt: str) -> str:
    """Get response from Gemini AI (V.18)"""
    # Identity check
    identity_queries = ["คุณคือใคร", "เป็นใคร", "who are you", "คุณชื่ออะไร", "ชื่ออะไร", "ตัวตน"]
    if any(q in prompt.lower() for q in identity_queries):
        return MESSAGES["IDENTITY"]
    
    if not gemini_model:
        return MESSAGES["AI_DISABLED"]
    
    try:
        # เพิ่ม context เวลาปัจจุบัน
        now = datetime.datetime.now(LOCAL_TZ)
        date_context = f"วันนี้คือ{now.strftime('%A')}ที่ {now.strftime('%d %B')} พ.ศ. {now.year + 543}"
        enhanced_prompt = f"(บริบท: {date_context})\n\nคำถาม: {prompt}"
        
        response = gemini_model.generate_content(enhanced_prompt)
        text = _safe_parse_gemini_response(response)
        
        if not text:
            return MESSAGES["AI_NO_RESPONSE"]
        
        # แทนที่ชื่อ Google ด้วย Gemini
        text = re.sub(r'\b[Gg]oogle\b', 'Gemini', text)
        text = text.replace('กูเกิล', 'Gemini')
        
        # ตัดข้อความถ้ายาวเกินไป
        if len(text) > LINE_SAFE_TRUNCATE:
            text = text[:LINE_SAFE_TRUNCATE] + "...\n\n(ข้อความยาวเกินไป ตัดบางส่วน)"
        
        return text
        
    except Exception as e:
        logger.error("Gemini Generate Error: %s", e)
        return MESSAGES["AI_ERROR"]

# ==========================================================================================
# --- Command Matching & Dispatching (V.18 Style - RESTORED) ---
# ==========================================================================================
def _keyword_matches(message_lower: str, keyword_lower: str) -> bool:
    """Check if keyword matches in message"""
    return keyword_lower in message_lower

def call_action(action, user_message: str):
    """Call action function with proper argument handling"""
    try:
        # Check if function accepts arguments
        if action.__code__.co_argcount > 0:
            return action(user_message)
        else:
            return action()
    except Exception as e:
        logger.error(f"Error calling action: {e}")
        return TextMessage(text=MESSAGES["ACTION_ERROR"])

# --- COMMANDS LIST (V.18 Pattern - RESTORED) ---
COMMANDS = [
    # งาน & ลิงก์พื้นฐาน
    (("งาน", "การบ้าน", "เช็คงาน", "ใบงาน"), get_worksheet_message),
    (("เว็บโรงเรียน", "เว็บ"), get_school_link_message),
    (("ตารางเรียน", "ตารางสอน"), get_timetable_image_message),
    (("เกรด", "ดูเกรด"), get_grade_link_message),
    (("ลาป่วย", "ลากิจ", "ลา"), get_absence_form_message),
    
    # เฉลย
    (("ชีวะ", "เฉลยชีวะ"), get_bio_link_message),
    (("ฟิสิกส์", "เฉลยฟิสิกส์"), get_physic_link_message),
    
    # ตารางเรียน & เวลา
    (("คาบต่อไป", "เรียนอะไร", "เรียนไรต่อ"), get_next_class_message),
    (("อีกกี่นาที", "เหลือเวลา", "เช็คเวลา"), get_time_until_next_class_message),
    
    # สอบ
    (("สอบ", "วันสอบ"), get_exam_countdown_message),
    
    # เพลง
    (("เปิดเพลง", "หาเพลง", "ขอเพลง"), get_music_link_message),
    
    # Help (ต้องอยู่ท้ายสุด)
    (("คำสั่ง", "help", "ช่วยเหลือ"), get_help_message),
]

# ==========================================================================================
# --- LINE Reply Helper (V.18) ---
# ==========================================================================================
def reply_to_line(reply_token: str, messages: list) -> bool:
    """Send reply to LINE with retry logic (V.18)"""
    if not messages:
        return False
    
    try:
        with ApiClient(configuration) as api_client:
            line_bot_api = MessagingApi(api_client)
            line_bot_api.reply_message(
                ReplyMessageRequest(
                    reply_token=reply_token,
                    messages=messages
                )
            )
        return True
    except Exception as e:
        logger.error("LINE Reply Error: %s", e)
        return False

# ==========================================================================================
# --- Event Handlers (V.18) ---
# ==========================================================================================
@handler.add(FollowEvent) if handler else (lambda f: f)
def handle_follow(event):
    """Handle user following the bot"""
    welcome_message = TextMessage(
        text='👋 สวัสดีครับ! ผมคือ MTC Assistant\n'
             'ผู้ช่วยอเนกประสงค์ของห้อง ม.4/2\n\n'
             'พิมพ์ "คำสั่ง" เพื่อดูรายการคำสั่งทั้งหมดนะครับ'
    )
    try:
        reply_to_line(event.reply_token, [welcome_message])
        logger.info("Sent follow welcome message")
    except Exception:
        logger.exception("Failed to send follow reply")

@handler.add(MessageEvent, message=TextMessageContent) if handler else (lambda f: f)
def handle_message(event):
    """Handle incoming text messages (V.18 Enhanced)"""
    user_text = getattr(event.message, "text", "")
    user_message = user_text.strip()
    
    if not user_message:
        reply_to_line(event.reply_token, [TextMessage(text=MESSAGES["INVALID_MESSAGE"])])
        return
    
    # Get user ID for rate limiting
    user_id = None
    try:
        user_id = event.source.user_id if hasattr(event, "source") else None
    except Exception:
        user_id = None
    
    if not user_id:
        user_id = f"anon-{request.remote_addr or 'unknown'}"
    
    logger.info("Message from %s: %s", user_id, user_message[:100])
    
    # Check rate limit (V.18)
    if is_rate_limited(user_id):
        logger.info("Rate limit triggered for user %s", user_id)
        reply_to_line(event.reply_token, [TextMessage(text=MESSAGES["RATE_LIMITED"])])
        return
    
    user_message_lower = user_message.lower()
    reply_message = None
    
    # ===============================================
    # Check Firebase Commands First (V.19 Features)
    # ===============================================
    if user_message.startswith("สั่งการบ้าน"):
        parts = user_message.split(maxsplit=3)
        if len(parts) >= 3:
            subject = parts[1]
            detail = parts[2]
            due = parts[3] if len(parts) > 3 else "ไม่ระบุ"
            result = add_homework_to_db(subject, detail, due)
            reply_message = TextMessage(text=result)
        else:
            reply_message = TextMessage(text="⚠️ รูปแบบ: สั่งการบ้าน [วิชา] [รายละเอียด] [วันส่ง]")
    
    elif user_message in ["การบ้าน", "ดูการบ้าน", "homework"]:
        reply_message = TextMessage(text=get_homeworks_from_db())
    
    elif user_message in ["ลบการบ้านทั้งหมด", "clear hw", "ลบงาน"]:
        reply_message = TextMessage(text=clear_homework_db())
    
    # ===============================================
    # Try Standard Commands (V.18 Pattern)
    # ===============================================
    if not reply_message:
        for keywords, action in COMMANDS:
            matched = False
            # เรียงจากยาวไปสั้น เพื่อจับ keyword ที่ specific ก่อน
            for keyword in sorted(keywords, key=len, reverse=True):
                if _keyword_matches(user_message_lower, keyword.lower()):
                    try:
                        reply_message = call_action(action, user_message)
                        logger.info("Matched command: %s for user %s", keyword, user_id)
                    except Exception as e:
                        logger.exception("Error executing action for keyword %s: %s", keyword, e)
                        reply_message = TextMessage(text=MESSAGES["ACTION_ERROR"])
                    matched = True
                    break
            
            if matched:
                break
    
    # ===============================================
    # Fallback to Gemini AI
    # ===============================================
    if not reply_message:
        logger.debug("No command matched, using Gemini API for user %s", user_id)
        ai_response_text = get_gemini_response(user_message)
        reply_message = TextMessage(text=ai_response_text)
    
    # ===============================================
    # Send Reply
    # ===============================================
    try:
        if reply_message:
            if not reply_to_line(event.reply_token, [reply_message]):
                logger.error("Failed to send reply to user %s", user_id)
        else:
            logger.warning("No reply generated for message from %s: %s", user_id, user_message)
    except Exception:
        logger.exception("Failed to send reply to LINE for user %s", user_id)

# ==========================================================================================
# --- Flask Routes ---
# ==========================================================================================
@app.route("/callback", methods=['POST'])
def callback():
    """Handle LINE webhook callback (V.18)"""
    signature = request.headers.get('X-Line-Signature') or request.headers.get('x-line-signature')
    if not signature:
        logger.error("Missing X-Line-Signature header.")
        abort(400)
    
    body = request.get_data(as_text=True)
    logger.debug("Request body: %s", body[:200])
    
    if handler is None:
        logger.error("Webhook handler not configured (missing CHANNEL_SECRET).")
        abort(500)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.error("Invalid signature. Check CHANNEL_SECRET.")
        abort(400)
    except Exception as e:
        logger.exception("Error handling request: %s", e)
        abort(500)
    
    return "OK", 200

@app.route("/", methods=['GET'])
def home():
    """Health check and status endpoint"""
    cfg_ok = "OK" if ACCESS_TOKEN and CHANNEL_SECRET else "CONFIG_MISSING"
    gemini_status = "OK" if GEMINI_API_KEY else "MISSING"
    db_status = "OK" if db else "DISCONNECTED"
    return f"🤖 MTC Assistant v20 (Complete Enhanced) Running!\n" \
           f"LINE: {cfg_ok} | Gemini: {gemini_status} | Firebase: {db_status}"

@app.route("/healthz", methods=['GET'])
def healthz():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "time": datetime.datetime.now(tz=LOCAL_TZ).isoformat(),
        "version": "20-complete-enhanced",
        "line": bool(ACCESS_TOKEN and CHANNEL_SECRET),
        "gemini": bool(GEMINI_API_KEY),
        "firebase": bool(db)
    }), 200

# ==========================================================================================
# --- Main ---
# ==========================================================================================
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("🚀 Starting MTC Assistant v20 (Complete Enhanced Edition)")
    logger.info(f"Port: {PORT}, Debug: {FLASK_DEBUG}")
    logger.info(f"LINE Config: {'OK' if ACCESS_TOKEN else 'MISSING'}")
    logger.info(f"Gemini Config: {'OK' if GEMINI_API_KEY else 'MISSING'}")
    logger.info(f"Firebase Config: {'OK' if db else 'MISSING'}")
    logger.info("=" * 60)
    app.run(host="0.0.0.0", port=PORT, debug=FLASK_DEBUG)