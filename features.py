# -*- coding: utf-8 -*-
"""
MTC Assistant - Features Module
Contains all feature functions: schedule, homework, music, AI, etc.
"""

import datetime
import math
import re
import urllib.parse
from typing import Optional
import google.generativeai as genai

from linebot.v3.messaging import TextMessage, ImageMessage

# Import from config
from config import (
    logger, LOCAL_TZ, SCHEDULE, EXAM_DATES, MESSAGES,
    WORKSHEET_LINK, SCHOOL_LINK, TIMETABLE_IMG, GRADE_LINK,
    ABSENCE_LINK, Bio_LINK, Physic_LINK, LINE_SAFE_TRUNCATE
)

# Global variables (will be set by main.py)
db = None  # Firebase database instance
gemini_model = None  # Gemini AI model instance

# ============================================================================
# DATABASE FUNCTIONS (Firebase/Homework)
# ============================================================================

def set_database(database):
    """Set Firebase database instance"""
    global db
    db = database

def add_homework_to_db(subject: str, detail: str, due_date: str = "ไม่ระบุ") -> str:
    """เพิ่มการบ้านเข้า Firebase"""
    if not db:
        return "⚠️ ระบบฐานข้อมูลยังไม่พร้อม กรุณาติดต่อผู้ดูแลระบบ"
    
    try:
        from firebase_admin import firestore
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
        from firebase_admin import firestore
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

# ============================================================================
# BASIC COMMAND FUNCTIONS
# ============================================================================

def get_worksheet_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์ใบงาน"""
    return TextMessage(text=f"📝 ตารางงานอยู่นี่ครับ {WORKSHEET_LINK}")

def get_school_link_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์เว็บโรงเรียน"""
    return TextMessage(text=f"🏫 เว็บไซต์โรงเรียนครับ {SCHOOL_LINK}")

def get_timetable_image_message(user_message: str = "") -> ImageMessage:
    """ส่งรูปตารางเรียน"""
    return ImageMessage(original_content_url=TIMETABLE_IMG, preview_image_url=TIMETABLE_IMG)

def get_grade_link_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์เช็คเกรด"""
    return TextMessage(text=f"📊 เช็คเกรดได้ที่นี่ครับ {GRADE_LINK}")

def get_absence_form_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์แบบฟอร์มลา"""
    return TextMessage(text=f"📝 ลิงก์แจ้งลาครับ {ABSENCE_LINK}")

def get_bio_link_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์เฉลยชีวะ"""
    return TextMessage(text=f"🧬 เฉลยชีววิทยาครับ {Bio_LINK}")

def get_physic_link_message(user_message: str = "") -> TextMessage:
    """ส่งลิงก์เฉลยฟิสิกส์"""
    return TextMessage(text=f"⚛️ เฉลยฟิสิกส์ครับ {Physic_LINK}")

def get_help_message(user_message: str = "") -> TextMessage:
    """แสดงคำสั่งทั้งหมด"""
    help_text = (
        '📖 รายการคำสั่งทั้งหมด\n\n'
        '📋 คำสั่งพื้นฐาน\n'
        '- งาน / การบ้าน = ดูใบงาน\n'
        '- เว็บโรงเรียน = ลิงก์เว็บโรงเรียน\n'
        '- ตารางเรียน = ดูตารางเรียน\n'
        '- เกรด = เช็คเกรด\n'
        '- คาบต่อไป = ดูว่าเรียนอะไรต่อ\n'
        '- อีกกี่นาที = เช็คเวลาเหลือก่อนคาบถัดไป\n'
        '- ลา = แบบฟอร์มลา\n'
        '- สอบ = นับถอยหลังวันสอบ\n\n'
        '🧪 คำสั่งเฉลย\n'
        '- ชีวะ = เฉลยชีววิทยา\n'
        '- ฟิสิกส์ = เฉลยฟิสิกส์\n\n'
        '🎵 ความบันเทิง\n'
        '- เปิดเพลง [ชื่อเพลง] = หาเพลงจาก YouTube\n\n'
        '💾 คำสั่งการบ้าน (ต้องมี Firebase)\n'
        '- สั่งการบ้าน | วิชา | รายละเอียด | วันส่ง\n'
        '  ตัวอย่าง: สั่งการบ้าน | ฟิสิกส์ | ทำแบบฝึกหัด 4.1 | วันศุกร์\n'
        '- การบ้าน / ดูการบ้าน = ดูการบ้านทั้งหมด\n'
        '- ลบการบ้านทั้งหมด = ล้างข้อมูล\n\n'
        '🤖 AI\n'
        '- พิมพ์ข้อความอื่นๆ = ตอบด้วย AI\n\n'
    )
    return TextMessage(text=help_text)

# ============================================================================
# SCHEDULE FUNCTIONS
# ============================================================================

def get_next_class_message(user_message: str = "") -> TextMessage:
    """แสดงคาบเรียนถัดไป"""
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
                text=f"🔜 คาบต่อไป : {period['subject']}\n"
                     f"📍 ห้อง : {period['room']}\n"
                     f"⏰ เวลา : {period['start']} - {period['end']}"
            )
        
        # ถ้ากำลังอยู่ในคาบนี้
        if start_time <= current_time < end_time:
            return TextMessage(
                text=f"⏳ กำลังเรียน : {period['subject']}\n"
                     f"📍 ห้อง : {period['room']}\n"
                     f"⏰ จนถึง : {period['end']}"
            )
    
    return TextMessage(text=MESSAGES["NO_CLASS_LEFT"])

def get_time_until_next_class_message(user_message: str = "") -> TextMessage:
    """คำนวณเวลาเหลือก่อนคาบถัดไป"""
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
             f"🔜 คาบถัดไป : {target['subject']}\n"
             f"📍 ห้อง : {target['room']}"
    )

# ============================================================================
# EXAM COUNTDOWN
# ============================================================================

def get_exam_countdown_message(user_message: str = "") -> TextMessage:
    """นับถอยหลังวันสอบ (Multi-date support)"""
    now = datetime.datetime.now(LOCAL_TZ).date()
    msg_list = ["⏳ *นับถอยหลังสอบ*\n"]
    found = False
    
    for exam_name, dates in EXAM_DATES.items():
        # Handle list of dates
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
                    f"   เหลือ {days_left} วัน\n"
                    f"   (สอบวันที่ {all_dates_str})"
                )
    
    if not found:
        return TextMessage(text="🎉 ยังไม่มีสอบเร็วๆ นี้ พักผ่อนได้!")
    
    return TextMessage(text="\n\n".join(msg_list))

# ============================================================================
# MUSIC SEARCH
# ============================================================================

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
    """หาเพลงจาก YouTube (สร้างลิงก์ค้นหา)"""
    music_keywords = ["เปิดเพลง", "หาเพลง", "ขอเพลง"]
    song_title = user_message.lower()
    
    # ตัดคำสั่งออก
    for keyword in music_keywords:
        if keyword in song_title:
            song_title = song_title.replace(keyword, "").strip()
            break
    
    if not song_title:
        return TextMessage(text="กรุณาระบุชื่อเพลงด้วยครับ เช่น 'เปิดเพลง never gonna give you up'")
    
    # สร้าง URL ค้นหา YouTube
    encoded_query = urllib.parse.quote(song_title)
    search_url = f"https://www.youtube.com/results?search_query={encoded_query}"
    
    return TextMessage(
        text=f"🎵 ค้นหาเพลง: {song_title}\n"
             f"👉 {search_url}\n\n"
             f"💡 กดลิงก์เพื่อดูผลการค้นหาใน YouTube"
    )

# ============================================================================
# AI FUNCTIONS (Gemini)
# ============================================================================

def set_gemini_model(model):
    """Set Gemini AI model instance"""
    global gemini_model
    gemini_model = model

def _safe_parse_gemini_response(response) -> str:
    """Parse Gemini response safely"""
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
    """Get response from Gemini AI"""
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
