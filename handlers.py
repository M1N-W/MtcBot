# -*- coding: utf-8 -*-
"""
MTC Assistant - Handlers Module
Contains LINE webhook handlers, command routing, and rate limiting
"""

import time
import threading
from typing import Dict, List
from flask import request

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

# Import from config
from config import (
    logger, ACCESS_TOKEN, CHANNEL_SECRET, MESSAGES,
    RATE_LIMIT_MAX, RATE_LIMIT_WINDOW
)

# Import from features
from features import (
    get_worksheet_message, get_school_link_message, get_timetable_image_message,
    get_grade_link_message, get_absence_form_message, get_bio_link_message,
    get_physic_link_message, get_help_message, get_next_class_message,
    get_time_until_next_class_message, get_exam_countdown_message,
    get_music_link_message, get_gemini_response,
    add_homework_to_db, get_homeworks_from_db, clear_homework_db
)

# ============================================================================
# LINE BOT CONFIGURATION
# ============================================================================
configuration = Configuration(access_token=ACCESS_TOKEN) if ACCESS_TOKEN else None
handler = WebhookHandler(CHANNEL_SECRET) if CHANNEL_SECRET else None

# ============================================================================
# RATE LIMITING
# ============================================================================
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

# ============================================================================
# COMMAND MATCHING & DISPATCHING
# ============================================================================

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

# COMMANDS LIST - Order matters! (most specific first)
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

# ============================================================================
# LINE REPLY HELPER
# ============================================================================

def reply_to_line(reply_token: str, messages: list) -> bool:
    """Send reply to LINE with error handling"""
    if not messages:
        return False
    
    if not configuration:
        logger.error("LINE configuration not available")
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

# ============================================================================
# EVENT HANDLERS
# ============================================================================

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
    """Handle incoming text messages"""
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
    
    # Check rate limit
    if is_rate_limited(user_id):
        logger.info("Rate limit triggered for user %s", user_id)
        reply_to_line(event.reply_token, [TextMessage(text=MESSAGES["RATE_LIMITED"])])
        return
    
    user_message_lower = user_message.lower()
    reply_message = None
    
    # ===============================================
    # Check Firebase Commands First
    # ===============================================
    if user_message.startswith("สั่งการบ้าน"):
        reply_message = _handle_add_homework(user_message)
    
    elif user_message in ["การบ้าน", "ดูการบ้าน", "homework"]:
        reply_message = TextMessage(text=get_homeworks_from_db())
    
    elif user_message in ["ลบการบ้านทั้งหมด", "clear hw", "ลบงาน"]:
        reply_message = TextMessage(text=clear_homework_db())
    
    # ===============================================
    # Try Standard Commands
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

# ============================================================================
# HOMEWORK COMMAND HANDLER
# ============================================================================

def _handle_add_homework(user_message: str) -> TextMessage:
    """Handle add homework command with multiple formats support"""
    # รองรับ 2 รูปแบบ:
    # 1. สั่งการบ้าน | วิชา | รายละเอียด | วันส่ง (แนะนำ)
    # 2. สั่งการบ้าน วิชา รายละเอียด ส่งวันXXX
    
    # ลองแยกด้วย | ก่อน (รูปแบบที่แนะนำ)
    if "|" in user_message:
        parts = [p.strip() for p in user_message.split("|")]
        if len(parts) >= 3:
            subject = parts[1]      # วิชา
            detail = parts[2]       # รายละเอียด
            due = parts[3] if len(parts) > 3 else "ไม่ระบุ"
            result = add_homework_to_db(subject, detail, due)
            return TextMessage(text=result)
        else:
            return TextMessage(
                text="⚠️ รูปแบบ: สั่งการบ้าน | วิชา | รายละเอียด | วันส่ง\n"
                     "ตัวอย่าง: สั่งการบ้าน | ฟิสิกส์ | ทำแบบฝึกหัดบทที่ 4 ข้อ 1-5 | วันศุกร์"
            )
    else:
        # รูปแบบเก่า (ไม่แนะนำ แต่รองรับไว้)
        parts = user_message.replace("สั่งการบ้าน", "").strip().split(maxsplit=1)
        if len(parts) >= 1:
            # พยายามแยกวิชากับส่วนที่เหลือ
            subject = parts[0]
            remaining = parts[1] if len(parts) > 1 else ""
            
            # ลองหาคำที่บอกวันส่ง
            due_keywords = ["ส่งวัน", "ส่ง ", "due", "deadline"]
            detail = remaining
            due = "ไม่ระบุ"
            
            for keyword in due_keywords:
                if keyword in remaining:
                    split_parts = remaining.split(keyword, 1)
                    detail = split_parts[0].strip()
                    due = split_parts[1].strip() if len(split_parts) > 1 else "ไม่ระบุ"
                    break
            
            if detail:
                result = add_homework_to_db(subject, detail, due)
                return TextMessage(text=result)
            else:
                return TextMessage(
                    text="⚠️ รูปแบบที่แนะนำ: สั่งการบ้าน | วิชา | รายละเอียด | วันส่ง\n"
                         "ตัวอย่าง: สั่งการบ้าน | ฟิสิกส์ | ทำแบบฝึกหัดบทที่ 4 ข้อ 1-5 | วันศุกร์\n\n"
                         "หรือ: สั่งการบ้าน ฟิสิกส์ ทำแบบฝึกหัด ส่งวันศุกร์"
                )
        else:
            return TextMessage(
                text="⚠️ รูปแบบที่แนะนำ: สั่งการบ้าน | วิชา | รายละเอียด | วันส่ง\n"
                     "ตัวอย่าง: สั่งการบ้าน | ฟิสิกส์ | ทำแบบฝึกหัดบทที่ 4 ข้อ 1-5 | วันศุกร์"
            )

# ============================================================================
# EXPORTS
# ============================================================================
__all__ = [
    'handler',
    'configuration',
    'handle_follow',
    'handle_message',
    'reply_to_line',
    'is_rate_limited',
]
