# 🤖 MTC Assistant v20 - Refactored Modular Edition

LINE Bot ผู้ช่วยอเนกประสงค์สำหรับห้อง MTC ม.4/2 ที่ถูก refactor ให้มีโครงสร้างที่ชัดเจนและดูแลรักษาง่าย

## 📁 โครงสร้างโปรเจค

```
mtc_assistant_bot/
├── main.py              # 🚀 Entry point - Flask app & initialization
├── config.py            # ⚙️ Configuration, constants, messages
├── features.py          # ✨ Feature functions (schedule, homework, AI)
├── handlers.py          # 🎯 LINE handlers & command routing
├── firebase_key.json    # 🔑 Firebase credentials (ไม่อัปโหลด git!)
└── README.md           # 📖 เอกสารนี้
```

## 🎯 ความแตกต่างจากเวอร์ชันเดิม

### ❌ เดิม (v20 Original):
- **1 ไฟล์ 862 บรรทัด** - ยากต่อการดูแล
- โค้ดทุกอย่างรวมกัน
- หาโค้ดยาก scroll ไปมา

### ✅ ใหม่ (v20 Refactored):
- **4 ไฟล์** แยกหน้าที่ชัดเจน
- แต่ละไฟล์รับผิดชอบส่วนของตัวเอง
- ง่ายต่อการแก้ไขและขยาย

## 📋 รายละเอียดแต่ละไฟล์

### 1️⃣ **main.py** (~150 บรรทัด)
**หน้าที่:** Entry point หลัก, Flask routes, Initialization

**ประกอบด้วย:**
- Flask app setup
- Firebase initialization
- Gemini AI initialization
- Routes: `/`, `/callback`, `/healthz`, `/stats`
- Startup banner & logging

**วิธีรัน:**
```bash
python main.py
```

---

### 2️⃣ **config.py** (~180 บรรทัด)
**หน้าที่:** Configuration, Constants, Settings

**ประกอบด้วย:**
- Environment variables (ACCESS_TOKEN, CHANNEL_SECRET, etc.)
- Constants (PORT, LINE_MAX_TEXT, etc.)
- Messages dict
- Links (WORKSHEET_LINK, SCHOOL_LINK, etc.)
- Schedule data (SCHEDULE dict)
- Exam dates (EXAM_DATES dict)
- Logging configuration

**การใช้งาน:**
```python
from config import MESSAGES, SCHEDULE, logger
```

---

### 3️⃣ **features.py** (~450 บรรทัด)
**หน้าที่:** Feature functions ทั้งหมด

**ประกอบด้วย:**
- **Database Functions:** `add_homework_to_db()`, `get_homeworks_from_db()`, `clear_homework_db()`
- **Basic Commands:** `get_worksheet_message()`, `get_school_link_message()`, etc.
- **Schedule Functions:** `get_next_class_message()`, `get_time_until_next_class_message()`
- **Exam Countdown:** `get_exam_countdown_message()`
- **Music Search:** `get_music_link_message()`
- **AI Functions:** `get_gemini_response()`, `_safe_parse_gemini_response()`

**การใช้งาน:**
```python
from features import get_next_class_message, get_gemini_response
```

---

### 4️⃣ **handlers.py** (~270 บรรทัด)
**หน้าที่:** LINE event handlers & command routing

**ประกอบด้วย:**
- LINE bot configuration
- Rate limiting (`is_rate_limited()`)
- Command matching & dispatching
- COMMANDS list
- Event handlers: `handle_follow()`, `handle_message()`
- Reply helper: `reply_to_line()`

**การใช้งาน:**
```python
from handlers import handler, handle_message
```

---

## 🚀 การติดตั้งและรัน

### 1. ติดตั้ง Dependencies
```bash
pip install flask line-bot-sdk google-generativeai firebase-admin requests
```

### 2. ตั้งค่า Environment Variables
```bash
export CHANNEL_ACCESS_TOKEN="your_line_token"
export CHANNEL_SECRET="your_channel_secret"
export GEMINI_API_KEY="your_gemini_key"
export PORT=5001
```

หรือสร้างไฟล์ `.env`:
```
CHANNEL_ACCESS_TOKEN=your_line_token
CHANNEL_SECRET=your_channel_secret
GEMINI_API_KEY=your_gemini_key
PORT=5001
FLASK_DEBUG=false
```

### 3. เตรียม Firebase
- วาง `firebase_key.json` ในโฟลเดอร์เดียวกัน
- หรือแก้ `FIREBASE_KEY_PATH` ใน `config.py`

### 4. รันบอท
```bash
python main.py
```

---

## 🔧 การแก้ไขและขยายฟีเจอร์

### เพิ่มคำสั่งใหม่

**1. เพิ่มฟังก์ชันใน `features.py`:**
```python
def get_new_feature_message(user_message: str = "") -> TextMessage:
    """ฟีเจอร์ใหม่ของคุณ"""
    return TextMessage(text="Hello from new feature!")
```

**2. เพิ่มคำสั่งใน `handlers.py`:**
```python
# Import function ใหม่
from features import get_new_feature_message

# เพิ่มใน COMMANDS list
COMMANDS = [
    (("คำสั่งใหม่", "new"), get_new_feature_message),
    # ... commands อื่นๆ
]
```

**3. ทดสอบ:**
```
User: คำสั่งใหม่
Bot: Hello from new feature!
```

---

### แก้ไข Configuration

แก้ไขใน `config.py`:
```python
# เปลี่ยน rate limit
RATE_LIMIT_MAX = 10  # จาก 6

# เพิ่ม link ใหม่
NEW_LINK = "https://example.com"

# เพิ่มข้อความใหม่
MESSAGES["NEW_MESSAGE"] = "ข้อความใหม่"
```

---

### เพิ่มวันสอบ

แก้ไขใน `config.py`:
```python
EXAM_DATES = {
    "กลางภาค": [
        datetime.date(2025, 12, 21),
        datetime.date(2025, 12, 23),
    ],
    "ปลายภาค": [...],
    "สอบใหม่": [  # ← เพิ่มใหม่
        datetime.date(2026, 3, 15),
    ]
}
```

---

## 🐛 การ Debug

### เปิด Debug Mode
```bash
export DEBUG=true
export FLASK_DEBUG=true
python main.py
```

### ดู Logs
```python
# ใน code
from config import logger
logger.debug("Debug message")
logger.info("Info message")
logger.error("Error message")
```

### ตรวจสอบ Health
```bash
curl http://localhost:5001/healthz
```

**Response:**
```json
{
  "status": "ok",
  "version": "20-refactored-modular",
  "timestamp": "2026-01-01T08:00:00+07:00",
  "services": {
    "line": true,
    "gemini": true,
    "firebase": true
  }
}
```

---

## 📊 Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Home page & status |
| `/callback` | POST | LINE webhook |
| `/healthz` | GET | Health check (JSON) |
| `/stats` | GET | Statistics |

---

## ✅ ข้อดีของ Refactored Version

1. **🎨 ดูแลง่าย** - แต่ละไฟล์มีหน้าที่ชัดเจน
2. **🔍 หาโค้ดเร็ว** - รู้ว่าอยู่ไฟล์ไหน
3. **🧪 Test ง่าย** - test แยกส่วนได้
4. **🔄 Reuse ได้** - import ไปใช้ที่อื่นได้
5. **👥 ทำงานร่วมกันได้** - แต่ละคนแก้คนละไฟล์
6. **🚀 ขยายง่าย** - เพิ่มฟีเจอร์ไม่ยุ่งยาก

---

## 🔐 ความปลอดภัย

### ไฟล์ที่ **ไม่ควร** อัปโหลด git:
- `firebase_key.json` ← **สำคัญมาก!**
- `.env`
- `__pycache__/`

### สร้าง `.gitignore`:
```
firebase_key.json
.env
__pycache__/
*.pyc
.DS_Store
```

---

## 📝 คำสั่งที่รองรับ

### พื้นฐาน
- `งาน` / `การบ้าน` - ดูใบงาน
- `เว็บโรงเรียน` - ลิงก์เว็บโรงเรียน
- `ตารางเรียน` - ดูตารางเรียน
- `เกรด` - เช็คเกรด
- `คาบต่อไป` - ดูว่าเรียนอะไรต่อ
- `อีกกี่นาที` - เช็คเวลาเหลือก่อนคาบถัดไป
- `ลา` - แบบฟอร์มลา
- `สอบ` - นับถอยหลังวันสอบ

### เฉลย
- `ชีวะ` - เฉลยชีววิทยา
- `ฟิสิกส์` - เฉลยฟิสิกส์

### บันเทิง
- `เปิดเพลง [ชื่อเพลง]` - หาเพลงจาก YouTube

### การบ้าน (Firebase)
- `สั่งการบ้าน | วิชา | รายละเอียด | วันส่ง`
- `การบ้าน` / `ดูการบ้าน` - ดูการบ้านทั้งหมด
- `ลบการบ้านทั้งหมด` - ล้างข้อมูล

### AI
- พิมพ์ข้อความอื่นๆ = ตอบด้วย Gemini AI

---

## 🎓 สำหรับนักพัฒนา

### Import Structure
```python
# config.py
from config import logger, MESSAGES, SCHEDULE

# features.py
from features import get_next_class_message, get_gemini_response

# handlers.py
from handlers import handler, handle_message

# main.py
# ไม่ควร import จาก main.py (เพราะเป็น entry point)
```

### Testing
```python
# Test feature function
from features import get_next_class_message
result = get_next_class_message()
print(result.text)

# Test with mock data
from config import SCHEDULE
print(SCHEDULE[0])  # วันจันทร์
```

---

## 🤝 Contributing

ถ้าต้องการแก้ไขหรือเพิ่มฟีเจอร์:

1. แก้ไขในไฟล์ที่เหมาะสม (config, features, handlers)
2. ทดสอบให้แน่ใจว่าใช้งานได้
3. Update README.md ถ้ามีการเปลี่ยนแปลงใหญ่
4. Commit with clear message

---

## 📞 Support

หากพบปัญหา:
1. ตรวจสอบ logs
2. ดู `/healthz` endpoint
3. ตรวจสอบ environment variables
4. ลองเปิด DEBUG mode

---

## 📜 License

สร้างสรรค์โดย MTC ม.4/2 สำหรับใช้ภายในห้องเรียน

---

**Happy Coding! 🎉**

Made with ❤️ by MTC Team
Version: 20 (Refactored Modular Edition)
Date: January 1, 2026
