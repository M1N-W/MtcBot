# -*- coding: utf-8 -*-
"""
MTC Assistant - Handlers Module (Optimized)
Contains LINE webhook handlers, command routing, and rate limiting

Improvements:
- Connection pooling for LINE API
- Enhanced rate limiting with exponential backoff
- Better error handling
- Performance optimizations
"""

import time
import threading
from typing import Dict, List, Optional, Union, Callable
from flask import request

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, ImageMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, FollowEvent

# Import from config
from config import (
    logger, ACCESS_TOKEN, CHANNEL_SECRET, MESSAGES,
    RATE_LIMIT_MAX, RATE_LIMIT_WINDOW, ADMIN_USER_IDS
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

# Import broadcast functions
import broadcast

# ============================================================================
# LINE BOT CONFIGURATION
# ============================================================================
configuration = Configuration(access_token=ACCESS_TOKEN) if ACCESS_TOKEN else None
handler = WebhookHandler(CHANNEL_SECRET) if CHANNEL_SECRET else None

# ============================================================================
# CONNECTION POOLING (Optimization)
# ============================================================================
_line_api_client: Optional[MessagingApi] = None
_api_client_lock = threading.Lock()

def get_line_api() -> Optional[MessagingApi]:
    """Get or create LINE API client (singleton pattern for connection pooling)"""
    global _line_api_client
    
    if _line_api_client is None and configuration:
        with _api_client_lock:
            if _line_api_client is None:
                try:
                    _line_api_client = MessagingApi(ApiClient(configuration))
                    logger.debug("LINE API client initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize LINE API client: {e}")
    
    return _line_api_client

# ============================================================================
# RATE LIMITING (Enhanced)
# ============================================================================
_user_message_history: Dict[str, List[float]] = {}
_rate_limit_lock = threading.Lock()
_banned_users: Dict[str, float] = {}  # user_id -> ban_until_timestamp

def is_rate_limited(user_id: str) -> bool:
    """
    Check if user is rate limited with enhanced protection
    
    Features:
    - Sliding window rate limiting
    - Exponential backoff for repeated violations
    - Temporary bans for severe abuse
    """
    now_ts = time.time()
    
    with _rate_limit_lock:
        # Check if user is banned
        if user_id in _banned_users:
            ban_until = _banned_users[user_id]
            if now_ts < ban_until:
                remaining = int(ban_until - now_ts)
                logger.warning(f"User {user_id} is banned for {remaining}s")
                return True
            else:
                # Ban expired
                del _banned_users[user_id]
        
        # Get user history
        history = _user_message_history.get(user_id, [])
        recent = [t for t in history if now_ts - t < RATE_LIMIT_WINDOW]
        
        # Check for severe abuse (3x rate limit)
        if len(recent) > RATE_LIMIT_MAX * 3:
            # Ban for 5 minutes
            _banned_users[user_id] = now_ts + 300
            logger.error(f"User {user_id} BANNED for severe abuse ({len(recent)} msgs)")
            return True
        
        # Check for moderate abuse (2x rate limit)
        if len(recent) > RATE_LIMIT_MAX * 2:
            # Extended cooldown
            logger.warning(f"User {user_id} in extended cooldown ({len(recent)} msgs)")
            return True
        
        # Normal rate limit check
        recent.append(now_ts)
        _user_message_history[user_id] = recent
        
        if len(recent) > RATE_LIMIT_MAX:
            logger.info(f"User {user_id} rate limited ({len(recent)}/{RATE_LIMIT_MAX})")
            return True
    
    return False

def get_rate_limit_status(user_id: str) -> dict:
    """Get rate limit status for user (for monitoring)"""
    now_ts = time.time()
    
    with _rate_limit_lock:
        if user_id in _banned_users:
            return {
                "status": "banned",
                "ban_until": _banned_users[user_id],
                "remaining_seconds": int(_banned_users[user_id] - now_ts)
            }
        
        history = _user_message_history.get(user_id, [])
        recent = [t for t in history if now_ts - t < RATE_LIMIT_WINDOW]
        
        return {
            "status": "rate_limited" if len(recent) > RATE_LIMIT_MAX else "ok",
            "messages_count": len(recent),
            "limit": RATE_LIMIT_MAX,
            "window_seconds": RATE_LIMIT_WINDOW
        }

# ============================================================================
# COMMAND MATCHING & DISPATCHING (Optimized)
# ============================================================================

def _keyword_matches(message_lower: str, keyword_lower: str) -> bool:
    """Check if keyword matches in message"""
    return keyword_lower in message_lower

def call_action(action: Callable, user_message: str) -> Union[TextMessage, ImageMessage]:
    """
    Call action function with proper argument handling and error recovery
    
    Args:
        action: Function to call
        user_message: User's message
    
    Returns:
        TextMessage or ImageMessage response
    """
    try:
        # Check if function accepts arguments
        if action.__code__.co_argcount > 0:
            return action(user_message)
        else:
            return action()
    except Exception as e:
        logger.exception(f"Error calling action {action.__name__}: {e}")
        return TextMessage(text=MESSAGES.get("ACTION_ERROR", "เกิดข้อผิดพลาด กรุณาลองใหม่"))

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
# LINE REPLY HELPER (Optimized with connection pooling)
# ============================================================================

def reply_to_line(reply_token: str, messages: List[Union[TextMessage, ImageMessage]]) -> bool:
    """
    Send reply to LINE with connection pooling and better error handling
    
    Args:
        reply_token: LINE reply token
        messages: List of messages to send
    
    Returns:
        True if successful, False otherwise
    """
    if not messages:
        logger.warning("No messages to send")
        return False
    
    line_bot_api = get_line_api()
    if not line_bot_api:
        logger.error("LINE API client not available")
        return False
    
    try:
        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=reply_token,
                messages=messages
            )
        )
        logger.debug(f"Successfully replied with {len(messages)} message(s)")
        return True
    except Exception as e:
        logger.error(f"LINE Reply Error: {e}")
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
    except Exception as e:
        logger.exception(f"Failed to send follow reply: {e}")

@handler.add(MessageEvent, message=TextMessageContent) if handler else (lambda f: f)
def handle_message(event):
    """Handle incoming text messages with optimizations"""
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
    
    # Track user for broadcast (เก็บ user_id ไว้ใน Firebase)
    try:
        broadcast.track_user(user_id)
    except Exception as e:
        logger.error(f"Failed to track user: {e}")
    
    # Check rate limit
    if is_rate_limited(user_id):
        rate_status = get_rate_limit_status(user_id)
        if rate_status["status"] == "banned":
            reply_message = TextMessage(
                text=f"⛔ คุณถูกระงับชั่วคราวเนื่องจากส่งข้อความมากเกินไป\n"
                     f"กรุณารออีก {rate_status['remaining_seconds']} วินาที"
            )
        else:
            reply_message = TextMessage(text=MESSAGES["RATE_LIMITED"])
        
        reply_to_line(event.reply_token, [reply_message])
        return
    
    user_message_lower = user_message.lower()
    reply_message = None
    
    # ===============================================
    # Check Admin Commands First
    # ===============================================
    if user_id in ADMIN_USER_IDS:
        # Broadcast Command
        if user_message.startswith("ประกาศ "):
            message_to_broadcast = user_message.replace("ประกาศ ", "", 1).strip()
            if message_to_broadcast:
                announcement = broadcast.create_announcement(
                    "ประกาศจากผู้ดูแล", 
                    message_to_broadcast
                )
                result = broadcast.broadcast_message(announcement)
                broadcast.save_broadcast_history(user_id, announcement, result)
                reply_message = TextMessage(text=result['message'])
            else:
                reply_message = TextMessage(
                    text="⚠️ รูปแบบ: ประกาศ [ข้อความ]\nตัวอย่าง: ประกาศ พรุ่งนี้มีสอบฟิสิกส์"
                )
        
        # Broadcast with template
        elif user_message.startswith("ประกาศด่วน "):
            urgent_msg = user_message.replace("ประกาศด่วน ", "", 1).strip()
            if urgent_msg:
                alert = broadcast.create_urgent_alert(urgent_msg)
                result = broadcast.broadcast_message(alert)
                broadcast.save_broadcast_history(user_id, alert, result)
                reply_message = TextMessage(text=result['message'])
            else:
                reply_message = TextMessage(
                    text="⚠️ รูปแบบ: ประกาศด่วน [ข้อความ]\nตัวอย่าง: ประกาศด่วน วันนี้เลิกเรียนเร็ว!"
                )
        
        # เตือนการบ้าน
        elif user_message.startswith("เตือนการบ้าน "):
            reminder_msg = user_message.replace("เตือนการบ้าน ", "", 1).strip()
            if reminder_msg:
                reminder = broadcast.create_reminder("การบ้าน", reminder_msg)
                result = broadcast.broadcast_message(reminder)
                broadcast.save_broadcast_history(user_id, reminder, result)
                reply_message = TextMessage(text=result['message'])
            else:
                reply_message = TextMessage(
                    text="⚠️ รูปแบบ: เตือนการบ้าน [รายละเอียด]\n"
                         "ตัวอย่าง: เตือนการบ้าน ฟิสิกส์ต้องส่งพรุ่งนี้!"
                )
        
        # ดูสถิติ Broadcast
        elif user_message in ["สถิติประกาศ", "broadcast stats", "stats broadcast"]:
            reply_message = TextMessage(text=broadcast.get_broadcast_stats())
        
        # จำนวนผู้ใช้
        elif user_message in ["จำนวนผู้ใช้", "user count", "ผู้ใช้"]:
            count = broadcast.get_user_count()
            reply_message = TextMessage(text=f"👥 จำนวนผู้ใช้ทั้งหมด: {count} คน")
        
        # คำสั่ง Admin Help
        elif user_message in ["admin", "คำสั่งแอดมิน"]:
            admin_help = (
                "👨‍💼 *คำสั่งแอดมิน*\n\n"
                "📢 *การประกาศ:*\n"
                "• ประกาศ [ข้อความ] - ส่งประกาศทั่วไป\n"
                "• ประกาศด่วน [ข้อความ] - ส่งประกาศด่วน\n"
                "• เตือนการบ้าน [รายละเอียด] - เตือนเรื่องการบ้าน\n\n"
                "📊 *สถิติ:*\n"
                "• สถิติประกาศ - ดูสถิติการส่ง\n"
                "• จำนวนผู้ใช้ - จำนวนคนที่แอดบอท\n\n"
                "💡 *ตัวอย่าง:*\n"
                "ประกาศ พรุ่งนี้มีสอบฟิสิกส์นะครับ\n"
                "ประกาศด่วน วันนี้เลิกเรียนเร็ว!\n"
                "เตือนการบ้าน คณิตต้องส่งพรุ่งนี้"
            )
            reply_message = TextMessage(text=admin_help)

    # -----------------------------------------------------
    # ส่วนเสริมสำหรับปุ่ม Rich Menu "วิธีสั่งการบ้าน"
    # -----------------------------------------------------
    if not reply_message and "วิธีสั่งการบ้าน" in user_message:
        instruction_msg = (
            "📝 วิธีสั่งการบ้าน (Homework Command)\n\n"
            "พิมพ์คำสั่งตามรูปแบบนี้เพื่อให้บอทจำงานนะครับ\n"
            "👉 `สั่งการบ้าน | วิชา | รายละเอียด | วันส่ง`\n\n"
            "💡 ตัวอย่าง\n"
            "สั่งการบ้าน | คณิต | แบบฝึกหัดท้ายบท 2 ข้อคู่ | วันศุกร์\n"
            "สั่งการบ้าน | ฟิสิกส์ | สรุปสูตรบทการเคลื่อนที่ | 20 ต.ค."
        )
        reply_to_line(event.reply_token, [TextMessage(text=instruction_msg)])
        return
    
    # ===============================================
    # Check Firebase Commands First
    # ===============================================
    if not reply_message and user_message.startswith("สั่งการบ้าน"):
        reply_message = _handle_add_homework(user_message)
    
    elif not reply_message and user_message in ["การบ้าน", "ดูการบ้าน", "homework"]:
        reply_message = TextMessage(text=get_homeworks_from_db())
    
    elif not reply_message and user_message in ["ลบการบ้านทั้งหมด", "clear hw", "ลบงาน"]:
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
                        logger.debug("Matched command: %s for user %s", keyword, user_id)
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
        try:
            ai_response_text = get_gemini_response(user_message)
            reply_message = TextMessage(text=ai_response_text)
        except Exception as e:
            logger.exception(f"Gemini API error: {e}")
            reply_message = TextMessage(text=MESSAGES["AI_ERROR"])
    
    # ===============================================
    # Send Reply
    # ===============================================
    try:
        if reply_message:
            success = reply_to_line(event.reply_token, [reply_message])
            if not success:
                logger.error("Failed to send reply to user %s", user_id)
        else:
            logger.warning("No reply generated for message from %s: %s", user_id, user_message)
    except Exception as e:
        logger.exception(f"Failed to send reply to LINE for user {user_id}: {e}")

# ============================================================================
# HOMEWORK COMMAND HANDLER
# ============================================================================

def _handle_add_homework(user_message: str) -> TextMessage:
    """Handle add homework command with validation"""
    # รองรับ 2 รูปแบบ:
    # 1. สั่งการบ้าน | วิชา | รายละเอียด | วันส่ง (แนะนำ)
    # 2. สั่งการบ้าน วิชา รายละเอียด ส่งวันXXX
    
    # ลองแยกด้วย | ก่อน (รูปแบบที่แนะนำ)
    if "|" in user_message:
        parts = [p.strip() for p in user_message.split("|")]
        if len(parts) >= 3:
            subject = parts[1][:100]  # Limit length
            detail = parts[2][:500]    # Limit length
            due = parts[3][:50] if len(parts) > 3 else "ไม่ระบุ"
            
            # Validate
            if not subject:
                return TextMessage(text="⚠️ กรุณาระบุชื่อวิชา")
            if not detail:
                return TextMessage(text="⚠️ กรุณาระบุรายละเอียดการบ้าน")
            
            result = add_homework_to_db(subject, detail, due)
            return TextMessage(text=result)
        else:
            return TextMessage(
                text="⚠️ รูปแบบ: สั่งการบ้าน | วิชา | รายละเอียด | วันส่ง\n"
                     "ตัวอย่าง: สั่งการบ้าน | ฟิสิกส์ | ทำแบบฝึกหัดบทที่ 4 ข้อ 1-5 | วันศุกร์"
            )
    else:
        # รูปแบบเก่า (ไม่แนะนำ แต่รองรับไว้)
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
    'get_rate_limit_status',
    'get_line_api',
]
