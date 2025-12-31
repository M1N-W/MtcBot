# -*- coding: utf-8 -*-
"""
MTC Assistant v. 18 (hardened + multi-exam dates + debugging fixes)
- Improved logging
- Health endpoint
- Rate limiting (thread-safe per-user)
- Robust Gemini parsing + fallbacks
- Safer LINE reply handling with retry logic
- Multi-date exam countdown support
- Input validation & protections
- Clear env var checks
- Fixed truncated strings
- Added error handling improvements
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

LOG_LEVEL = logging.DEBUG if os.environ.get("DEBUG", "false").lower() in ("1", "true", "yes") else logging.INFO
logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("mtc_assistant")
logger.setLevel(LOG_LEVEL)
app.logger.handlers = logger.handlers
app.logger.setLevel(LOG_LEVEL)

# ---------------------------
# ENV / Credentials
# ---------------------------
ACCESS_TOKEN = os.environ.get('CHANNEL_ACCESS_TOKEN')  # LINE channel access token
CHANNEL_SECRET = os.environ.get('CHANNEL_SECRET')      # LINE channel secret
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')      # Gemini (optional)

# Safe PORT parsing with error handling
try:
    PORT = int(os.environ.get('PORT', 5001))
except (ValueError, TypeError):
    logger.warning("Invalid PORT value, using default 5001")
    PORT = 5001

FLASK_DEBUG = os.environ. get('FLASK_DEBUG', 'false').lower() == 'true'

if not ACCESS_TOKEN: 
    logger.warning("CHANNEL_ACCESS_TOKEN not set; LINE API calls will fail.")
if not CHANNEL_SECRET: 
    logger.warning("CHANNEL_SECRET not set; signature verification may fail.")
if not GEMINI_API_KEY:
    logger.info("GEMINI_API_KEY not set; AI features disabled.")

# ---------------------------
# Constants & Messages
# ---------------------------
WORKSHEET_LINK = "https://docs.google.com/spreadsheets/d/1SwKs4s8HJt2HxAzj_StIh_nopVMe1kwqg7yW13jOdQ4/edit?usp=sharing"
SCHOOL_LINK = "https://www.ben. ac.th/main/"
TIMETABLE_IMG = "https://img5.pic. in.th/file/secure-sv1/-2395abd52df9b5e08. jpg"
GRADE_LINK = "http://www.dograde2.online/bjrb/"
ABSENCE_LINK = "https://forms. gle/WjCBTYNxEeCpHShr9"
Bio_LINK = "https://drive.google.com/file/d/1zd5NND3612JOym6HSzKZnqAS42TH9gmh/view?usp=sharing"
Physic_LINK = "https://drive.google.com/file/d/15oSPs3jFYpvJRUkFqrCSpETGwOoK0Qpv/view?usp=sharing"

# Error and system messages
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

# --- Multi-date EXAM_DATES (lists of datetime. date) ---
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
# Thread-safe rate limiter
# ---------------------------
RATE_LIMIT_MAX = int(os.environ.get("RATE_LIMIT_MAX", 6))  # messages per window
RATE_LIMIT_WINDOW = int(os.environ. get("RATE_LIMIT_WINDOW", 60))  # seconds
_user_message_history: Dict[str, List[float]] = {}
_rate_limit_lock = threading.Lock()

def is_rate_limited(user_id: str) -> bool:
    """Check if user is rate limited with thread-safe access"""
    now_ts = time.time()
    with _rate_limit_lock: 
        history = _user_message_history. get(user_id, [])
        recent = [t for t in history if now_ts - t < RATE_LIMIT_WINDOW]
        recent. append(now_ts)
        _user_message_history[user_id] = recent
        if len(recent) > RATE_LIMIT_MAX:
            logger.debug("User %s exceeded rate limit (%d/%d)", user_id, len(recent), RATE_LIMIT_MAX)
            return True
    return False

# ---------------------------
# Class Schedule
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
                logger.info("Gemini model instantiated successfully via GenerativeModel.")
            else:
                logger. warning("GenerativeModel not available in genai module")
        except AttributeError as e:
            logger.warning("GenerativeModel not found:  %s", e)
        except Exception as e:
            logger.error("Failed to instantiate Gemini model:  %s", e, exc_info=True)
    else:
        logger.info("GEMINI_API_KEY not provided; AI features disabled.")
except Exception as e:
    logger.error("Error configuring Gemini API: %s", e, exc_info=True)
    gemini_model = None

# ---------------------------
# Helper:  safe parse for Gemini responses
# ---------------------------
def _safe_parse_gemini_response(response) -> str:
    """Safely parse Gemini API response with multiple fallback methods"""
    try:
        if response is None:
            return ""
        
        # Try different response formats
        if hasattr(response, "parts") and response.parts:
            parts = [getattr(part, "text", "") for part in response.parts if getattr(part, "text", None)]
            return "".join(parts).strip()
        
        if hasattr(response, "text") and getattr(response, "text"):
            return str(getattr(response, "text")).strip()
        
        if isinstance(response, dict):
            if "text" in response and response["text"]:
                return str(response["text"]).strip()
            if "candidates" in response and response["candidates"]:
                first = response["candidates"][0]
                if isinstance(first, dict):
                    if "content" in first and isinstance(first["content"], dict):
                        parts = first["content"].get("parts") or []
                        return "".join(p.get("text", "") for p in parts).strip()
                    if "text" in first: 
                        return str(first["text"]).strip()
                return str(first).strip()
        
        if hasattr(response, "result"):
            return str(getattr(response, "result")).strip()
        
        if hasattr(response, "candidates") and getattr(response, "candidates"):
            first = response.candidates[0]
            if hasattr(first, "content") and hasattr(first.content, "parts"):
                return "".join(part.text for part in first.content.parts if hasattr(part, "text")).strip()
            if hasattr(first, "text"):
                return str(getattr(first, "text")).strip()
        
        return str(response).strip()
    except Exception as e:
        logger. debug("Error parsing Gemini response: %s", e, exc_info=True)
        return str(response) if response else ""

# ---------------------------
# Gemini call with fallback and protections
# ---------------------------
def get_gemini_response(user_message:  str) -> str:
    """Get response from Gemini API with multiple fallbacks"""
    if not isinstance(user_message, str):
        logger.warning("Invalid user_message type: %s", type(user_message))
        return MESSAGES["ACTION_ERROR"]

    # Check if asking for identity
    identity_queries = ["คุณคือใคร", "เป็นใคร", "who are you", "คุณชื่ออะไร", "ชื่ออะไร", "ตัวตน"]
    if any(q in user_message.lower() for q in identity_queries):
        return MESSAGES["IDENTITY"]

    if not GEMINI_API_KEY: 
        return MESSAGES["AI_DISABLED"]

    # Prepare context
    now = datetime.datetime.now(tz=LOCAL_TZ)
    current_date_thai = now.strftime("%d %B")
    current_year_thai = now.year + 543
    current_day_thai = now.strftime("%A")
    full_date_context = f"วันนี้คือ{current_day_thai}ที่ {current_date_thai} พ.ศ. {current_year_thai}"
    enhanced_prompt = f"(บริบทปัจจุบัน:  {full_date_context})\n\nคำถามจากผู้ใช้: {user_message}"

    try:
        response = None
        
        # Try instantiated model first
        if gemini_model is not None:
            try:
                response = gemini_model.generate_content(enhanced_prompt)
                logger.debug("Got response from instantiated model")
            except Exception as e: 
                logger.warning("Instantiated model call failed: %s", e, exc_info=True)
                response = None

        # Try module-level functions
        if response is None: 
            try:
                if hasattr(genai, "generate_content"):
                    response = genai.generate_content(model=GEMINI_MODEL_NAME, contents=enhanced_prompt)
                    logger.debug("Got response from genai.generate_content")
                elif hasattr(genai, "generate_text"):
                    response = genai.generate_text(model=GEMINI_MODEL_NAME, prompt=enhanced_prompt)
                    logger.debug("Got response from genai.generate_text")
            except Exception as e:
                logger.error("Gemini module-level call failed: %s", e, exc_info=True)
                response = None

        reply_text = _safe_parse_gemini_response(response)
        if not reply_text:
            return MESSAGES["AI_NO_RESPONSE"]

        # Sanitize response
        reply_text = re.sub(r'\b[Gg]oogle\b', 'Gemini', reply_text)
        reply_text = reply_text.replace('กูเกิล', 'Gemini')

        # Filter out model training information
        if re.search(r'(แบบจำลอง|ฝึกโดย|ฝึกอบรม|trained by|model)', reply_text, flags=re.IGNORECASE):
            lines = reply_text.splitlines()
            filtered_lines = [ln for ln in lines if not re.search(r'(แบบจำลอง|ฝึกโดย|ฝึกอบรม|trained by|model)', ln, flags=re.IGNORECASE)]
            remaining = "\n".join(filtered_lines).strip()
            reply_text = MESSAGES["IDENTITY"]
            if remaining:
                reply_text = reply_text + "\n\n" + remaining

        # Truncate if necessary
        if len(reply_text) > LINE_SAFE_TRUNCATE:
            reply_text = reply_text[: LINE_SAFE_TRUNCATE] + "...  (ข้อความยาวเกิน กำลังตัด)"
        
        return reply_text

    except Exception as e:
        logger.exception("General Gemini API Error")
        return MESSAGES["AI_ERROR"]

# ---------------------------
# Safe reply helper (LINE) with retry logic
# ---------------------------
def reply_to_line(reply_token: str, messages: List, max_retries: int = 3) -> bool:
    """Send messages to LINE with retry logic and error handling"""
    if not messages:
        logger.warning("reply_to_line called with no messages.")
        return False
    
    if not isinstance(messages, list):
        logger.error("Messages must be a list, got %s", type(messages))
        return False
    
    if configuration is None:
        logger.error("LINE configuration not available (missing ACCESS_TOKEN). Cannot send reply.")
        return False
    
    for attempt in range(max_retries):
        try:
            with ApiClient(configuration) as api_client:
                line_bot_api = MessagingApi(api_client)
                response = line_bot_api.reply_message_with_http_info(
                    ReplyMessageRequest(reply_token=reply_token, messages=messages)
                )
                
                status_code = getattr(response, "status_code", None)
                if status_code is None:
                    try:
                        status_code = response[1] if isinstance(response, (list, tuple)) and len(response) > 1 else None
                    except Exception:
                        status_code = None
                
                if status_code and not (200 <= int(status_code) < 300):
                    logger. error("Error sending reply to LINE (Status:  %s): %s", status_code, getattr(response, "body", ""))
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    return False
                
                logger.debug("Successfully sent reply to LINE (Status: %s)", status_code)
                return True
        
        except requests.exceptions.RequestException as e:
            logger.warning("Network error on attempt %d/%d: %s", attempt + 1, max_retries, e)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
        except Exception as e:
            logger.exception("Exception while sending reply to LINE (attempt %d/%d)", attempt + 1, max_retries)
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
    
    logger.error("Failed to send reply to LINE after %d attempts", max_retries)
    return False

# ---------------------------
# Helper:  next class info
# ---------------------------
def get_next_class_info() -> str:
    """Get information about the next class"""
    now = datetime.datetime.now(tz=LOCAL_TZ)
    weekday = now.weekday()
    current_time = now.time()

    if weekday not in SCHEDULE:
        return MESSAGES["NO_CLASS_TODAY"]

    for period in SCHEDULE[weekday]:
        start_time = datetime.datetime.strptime(period["start"], "%H:%M").time()
        if current_time < start_time: 
            return (f"คาบต่อไป มีรายละเอียดดังนี้ครับ\n"
                    f"เริ่มคาบ :  {period['start']}\n"
                    f"จบคาบ : {period['end']}\n"
                    f"วิชา : {period['subject']}\n"
                    f"ห้อง : {period['room']}")
    
    return MESSAGES["NO_CLASS_LEFT"]

# ---------------------------
# Multi-date exam countdown helper
# ---------------------------
def create_countdown_message(exam_name: str, exam_dates: List[datetime.date]) -> str:
    """Create countdown message for exam dates"""
    today = datetime.datetime.now(tz=LOCAL_TZ).date()
    
    if not exam_dates:
        return f"ไม่พบข้อมูลวันสอบสำหรับ {exam_name} ครับ"
    
    if isinstance(exam_dates, datetime.date):
        dates = [exam_dates]
    else:
        dates = list(exam_dates)
    
    dates_sorted = sorted(dates)
    upcoming = [d for d in dates_sorted if d >= today]
    
    if upcoming:
        next_date = upcoming[0]
        delta = (next_date - today).days
        if delta > 0:
            return f"เหลืออีก {delta} วันจะถึงวันสอบ {exam_name} ({next_date.strftime('%d %b %Y')})"
        elif delta == 0:
            return f"วันนี้คือวันสอบ {exam_name} ({next_date.strftime('%d %b %Y')}) ขอให้โชคดีครับ"
    
    last_date = dates_sorted[-1]
    return f"การสอบ{exam_name}ได้สิ้นสุดลงแล้ว (ครั้งสุดท้ายในชุดนี้:  {last_date.strftime('%d %b %Y')})"

def get_exam_countdown_message(user_message: str) -> TextMessage:
    """Get exam countdown message based on user query"""
    if not isinstance(user_message, str):
        logger.warning("Invalid user_message type in get_exam_countdown_message:  %s", type(user_message))
        return TextMessage(text=MESSAGES["ACTION_ERROR"])
    
    um = user_message.lower()
    responses = []
    
    if "กลางภาค" in um:
        responses. append(create_countdown_message("กลางภาค", EXAM_DATES. get("กลางภาค", [])))
    
    if "ปลายภาค" in um:
        responses.append(create_countdown_message("ปลายภาค", EXAM_DATES. get("ปลายภาค", [])))
    
    if responses:
        return TextMessage(text="\n\n".join(responses))
    
    # Return summary if no specific exam type mentioned
    for name, dates in EXAM_DATES.items():
        responses.append(f"{name}: {create_countdown_message(name, dates)}")
    
    return TextMessage(text="\n\n".join(responses))

# ---------------------------
# Action / Command functions
# ---------------------------
def get_worksheet_message() -> TextMessage:
    return TextMessage(text=f'นี่คือตารางเช็คงานห้องเรานะครับ\n{WORKSHEET_LINK}')

def get_school_link_message() -> TextMessage:
    return TextMessage(text=f'นี่คือลิงก์เว็บโรงเรียนนะครับ\n{SCHOOL_LINK}')

def get_timetable_image_message() -> ImageMessage:
    return ImageMessage(original_content_url=TIMETABLE_IMG, preview_image_url=TIMETABLE_IMG)

def get_grade_link_message() -> TextMessage:
    return TextMessage(text=f'นี่คือลิงก์เว็บดูเกรดนะครับ\n{GRADE_LINK}')

def get_next_class_message() -> TextMessage:
    return TextMessage(text=get_next_class_info())

def get_absence_form_message() -> TextMessage:
    return TextMessage(text=f'นี่คือแบบฟอร์มลากิจ-ลาป่วยนะครับ\n{ABSENCE_LINK}')

def get_bio_link_message() -> TextMessage:
    return TextMessage(text=f'นี่คือเฉลยชีวะ บทที่ 4-7 นะครับ\n{Bio_LINK}')

def get_physic_link_message() -> TextMessage:
    return TextMessage(text=f'นี่คือเฉลยฟิสิกส์นะครับ\n{Physic_LINK}')

def get_help_message() -> TextMessage:
    help_text = (
        'คำสั่งทั้งหมด\n'
        '- งาน = ดูตารางงาน (worksheet)\n'
        '- เว็บ = เข้าเว็บโรงเรียน\n'
        '- ตารางสอน = ตารางสอนเทอม 2 ห้อง 4/2\n'
        '- เกรด = เข้าเว็บเช็คเกรด\n'
        '- คาบต่อไป/เรียนไรต่อ = เช็คคาบถัดไปแบบเรียลไทม์\n'
        '- อีกกี่นาที/เหลือเวลา/เช็คเวลา = เช็คเวลาคาบถัดไป\n'
        '- ลาป่วย/ลากิจ/ลา = แบบฟอร์มลากิจ-ลาป่วย\n'
        '- สอบ = นับถอยหลังวันสอบ\n'
        '- ชีวะ = เฉลยชีวะ\n'
        '- ฟิสิกส์ = เฉลยฟิสิกส์\n'
        '- ถ้าพิมพ์ข้อความอื่น ๆ ผมจะตอบด้วยเอไอ'
    )
    return TextMessage(text=help_text)

# ---------------------------
# Keyword matching with pattern caching
# ---------------------------
@functools.lru_cache(maxsize=256)
def _compile_keyword_pattern(keyword: str) -> re.Pattern:
    """Cache compiled regex patterns for keywords"""
    return re.compile(
        rf'(?<! [\w\u0E00-\u0E7F]){re.escape(keyword)}(?![\w\u0E00-\u0E7F])',
        flags=re.IGNORECASE
    )

def _keyword_matches(user_message: str, keyword: str) -> bool:
    """Check if keyword matches in user message"""
    try:
        if not isinstance(user_message, str) or not isinstance(keyword, str):
            logger.warning("Invalid types in _keyword_matches: msg=%s, kw=%s", type(user_message), type(keyword))
            return False
        
        um = user_message.lower()
        pattern = _compile_keyword_pattern(keyword. lower())
        return bool(pattern.search(um))
    except re.error:
        logger.warning("Regex error for keyword '%s'.  Falling back to substring match.", keyword)
        return keyword. lower() in user_message.lower()
    except Exception as e:
        logger.error("Error in _keyword_matches:  %s", e, exc_info=True)
        return False

def call_action(action, user_message: str = ""):
    """Execute an action with proper error handling"""
    action_name = getattr(action, "__name__", str(action))
    try:
        logger.debug("Executing action: %s", action_name)
        return action(user_message)
    except TypeError: 
        try:
            return action()
        except TypeError as e:
            logger.error("Action %s failed both 0 and 1 arg calls: %s", action_name, e)
            raise
        except Exception as e:
            logger.error("Action %s (0-arg) failed: %s", action_name, e, exc_info=True)
            raise
    except Exception as e: 
        logger.error("Unexpected error in action %s: %s", action_name, e, exc_info=True)
        raise

# ---------------------------
# Time-until-next-class helper (robust)
# ---------------------------
def get_time_until_next_class_message(user_message: str = "") -> TextMessage:
    """Get time remaining until next class"""
    now = datetime.datetime.now(tz=LOCAL_TZ)
    weekday = now.weekday()
    current_time = now.time()

    if weekday not in SCHEDULE:
        return TextMessage(text=MESSAGES["NO_CLASS_TODAY"])

    periods = SCHEDULE[weekday]
    current_index = None
    
    # Find current class period
    for idx, period in enumerate(periods):
        start_t = datetime.datetime.strptime(period["start"], "%H:%M").time()
        end_t = datetime.datetime.strptime(period["end"], "%H:%M").time()
        if start_t <= current_time < end_t:
            current_index = idx
            break

    if current_index is None: 
        # Not in any class, find next class
        for idx, period in enumerate(periods):
            start_t = datetime.datetime. strptime(period["start"], "%H:%M").time()
            if current_time < start_t: 
                target = period
                break
        else:
            return TextMessage(text=MESSAGES["NO_CLASS_LEFT"])
    else:
        # Currently in a class, find next different subject
        current_subject = periods[current_index]["subject"]
        target_idx = None
        for idx in range(current_index + 1, len(periods)):
            if periods[idx]["subject"] != current_subject:
                target_idx = idx
                break
        
        if target_idx is None: 
            return TextMessage(text="วันนี้ไม่มีคาบเรียนที่ต่างจากคาบปัจจุบันอีกแล้วครับ")
        
        target = periods[target_idx]

    target_start_time = datetime.datetime.strptime(target["start"], "%H:%M").time()
    target_dt = datetime.datetime.combine(now.date(), target_start_time).replace(tzinfo=LOCAL_TZ)
    delta_seconds = (target_dt - now).total_seconds()
    minutes_left = 0 if delta_seconds <= 0 else max(0, math.ceil(delta_seconds / 60))

    minutes_text = "น้อยกว่า 1 นาที" if minutes_left == 0 else f"{minutes_left} นาที"
    subject = target. get("subject", "ไม่ระบุวิชา")
    room = target.get("room", "ไม่ระบุห้อง")
    reply = f'เหลือเวลาอีก {minutes_text}\nคาบถัดไปคือ {subject}\nห้อง {room}'
    return TextMessage(text=reply)

# ---------------------------
# Commands & matching
# ---------------------------
COMMANDS = [
    (("งาน", "การบ้าน", "เช็คงาน"), get_worksheet_message),
    (("เว็บโรงเรียน", "เว็บ"), get_school_link_message),
    (("ตารางเรียน", "ตารางสอน"), get_timetable_image_message),
    (("เกรด", "ดูเกรด"), get_grade_link_message),
    (("คาบต่อไป", "เรียนอะไร", "เรียนไรต่อ"), get_next_class_message),
    (("อีกกี่นาที", "เหลือเวลา", "เช็คเวลา"), lambda msg: get_time_until_next_class_message(msg)),
    (("ลาป่วย", "ลากิจ", "ลา"), get_absence_form_message),
    (("ชีวะ", "เฉลยชีวะ"), get_bio_link_message),
    (("ฟิสิกส์", "เฉลยฟิสิกส์"), get_physic_link_message),
    (("คำสั่ง", "help", "ช่วยเหลือ"), get_help_message),
    (("สอบ",), lambda msg: get_exam_countdown_message(msg)),
]

# ---------------------------
# Event handlers
# ---------------------------
@handler. add(FollowEvent) if handler else (lambda f: f)
def handle_follow(event):
    """Handle user following the bot"""
    welcome_message = TextMessage(
        text='สวัสดีคับ! ผมคือ MTC Assistant ผู้ช่วยอเนกประสงค์ของห้อง ม.4/2\n'
             'พิมพ์ "คำสั่ง" เพื่อดูรายการคำสั่งทั้งหมดนะครับ'
    )
    try:
        reply_to_line(event.reply_token, [welcome_message])
        logger.info("Sent follow welcome message")
    except Exception: 
        logger.exception("Failed to send follow reply")

@handler.add(MessageEvent, message=TextMessageContent) if handler else (lambda f: f)
def handle_message(event):
    """Handle incoming messages"""
    user_text = getattr(event. message, "text", "")
    user_message = user_text.strip()
    
    if not user_message:
        reply_to_line(event.reply_token, [TextMessage(text=MESSAGES["INVALID_MESSAGE"])])
        return

    # Determine user id for rate limiting & logging
    user_id = None
    try:
        user_id = event.source.user_id if hasattr(event, "source") and getattr(event.source, "user_id", None) else None
    except Exception:
        user_id = None
    
    if not user_id:
        user_id = f"anon-{request.remote_addr or 'unknown'}"

    logger.info("Message from %s: %s", user_id, user_message[: 100])

    # Check rate limit
    if is_rate_limited(user_id):
        logger.info("Rate limit triggered for user %s", user_id)
        reply_to_line(event.reply_token, [TextMessage(text=MESSAGES["RATE_LIMITED"])])
        return

    user_message_lower = user_message.lower()
    reply_message = None

    # Try to match commands
    for keywords, action in COMMANDS:
        matched = False
        for keyword in sorted(keywords, key=len, reverse=True):
            if _keyword_matches(user_message_lower, keyword. lower()):
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

    # If no command matched, use AI
    if not reply_message: 
        logger.debug("No command matched, using Gemini API for user %s", user_id)
        ai_response_text = get_gemini_response(user_message)
        if len(ai_response_text) > LINE_MAX_TEXT: 
            ai_response_text = ai_response_text[:LINE_SAFE_TRUNCATE] + "...  (ข้อความตัด)"
        reply_message = TextMessage(text=ai_response_text)

    # Send reply
    try:
        if reply_message:
            if not reply_to_line(event.reply_token, [reply_message]):
                logger.error("Failed to send reply to user %s", user_id)
        else:
            logger.warning("No reply generated for message from %s:  %s", user_id, user_message)
    except Exception: 
        logger.exception("Failed to send reply to LINE for user %s", user_id)

# ---------------------------
# Flask webhooks + health
# ---------------------------
@app.route("/callback", methods=['POST'])
def callback():
    """Handle LINE webhook callback"""
    signature = request.headers.get('X-Line-Signature') or request.headers.get('x-line-signature')
    if not signature:
        logger.error("Missing X-Line-Signature header.")
        abort(400)
    
    body = request.get_data(as_text=True)
    logger.debug("Request body: %s", body[: 200])  # Log first 200 chars
    
    if handler is None:
        logger.error("Webhook handler not configured (missing CHANNEL_SECRET).")
        abort(500)
    
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger. error("Invalid signature.  Check CHANNEL_SECRET.")
        abort(400)
    except Exception as e:
        logger.exception("Error handling request:  %s", e)
        abort(500)
    
    return "OK", 200

@app.route("/", methods=['GET'])
def home():
    """Health check and status endpoint"""
    cfg_ok = "OK" if ACCESS_TOKEN and CHANNEL_SECRET else "CONFIG_MISSING"
    gemini_status = "OK" if GEMINI_API_KEY else "MISSING"
    return f"MTC Assistant v18 is running!  LINE Config: {cfg_ok}, Gemini Config: {gemini_status}"

@app.route("/healthz", methods=['GET'])
def healthz():
    """Health check endpoint"""
    return jsonify({
        "status": "ok",
        "time": datetime.datetime.now(tz=LOCAL_TZ).isoformat(),
        "version": "18"
    }), 200

# ---------------------------
# Run
# ---------------------------
if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("Starting MTC Assistant v18 on port %s (debug=%s)", PORT, FLASK_DEBUG)
    logger.info("Configuration: LINE=%s, Gemini=%s", "OK" if ACCESS_TOKEN else "MISSING", "OK" if GEMINI_API_KEY else "MISSING")
    logger.info("=" * 60)
    app.run(host='0.0.0.0', port=PORT, debug=FLASK_DEBUG)
