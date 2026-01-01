# 🤖 MTC Assistant v20

LINE Bot ผู้ช่วยอเนกประสงค์สำหรับนักเรียนห้อง MTC ม.4/2  
พัฒนาด้วย Python และเชื่อมต่อกับ LINE Messaging API พร้อมระบบประมวลผลด้วย Gemini AI

[![Python](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0%2B-green.svg)](https://flask.palletsprojects.com/)
[![LINE Bot SDK](https://img.shields.io/badge/LINE%20Bot%20SDK-3.0%2B-00C300.svg)](https://github.com/line/line-bot-sdk-python)

---

## ✨ ฟีเจอร์หลัก (Features)

| ฟีเจอร์ | รายละเอียด |
|---------|-----------|
| 📅 **Real-time Schedule** | เช็คคาบเรียนถัดไปและตารางเรียนรายวัน |
| ⏳ **Exam Countdown** | นับถอยหลังวันสอบกลางภาคและปลายภาค (รองรับหลายวัน) |
| 📝 **School Links** | รวบรวมลิงก์งาน, เว็บโรงเรียน, ระบบเช็คเกรด |
| 📚 **Homework Management** | จัดการการบ้านด้วย Firebase (เพิ่ม/ดู/ลบ) |
| 🎵 **Music Search** | ค้นหาเพลงใน YouTube |
| 🤖 **Gemini AI** | ตอบคำถามทั่วไปด้วย AI |
| 🛡️ **Rate Limiting** | ป้องกัน spam ด้วยระบบจำกัดอัตรา |
| 📊 **Robust Logging** | ระบบ logging แบบละเอียด |

---

## 🏗️ โครงสร้างโปรเจค (Architecture)

```
mtc-assistant/
├── main.py              # 🚀 Entry point - Flask app & initialization
├── config.py            # ⚙️ Configuration, constants, schedule data
├── features.py          # ✨ Feature functions (schedule, homework, AI)
├── handlers.py          # 🎯 LINE handlers & command routing
├── firebase_key.json    # 🔑 Firebase credentials (not in git)
├── requirements.txt     # 📦 Dependencies
├── .gitignore          # 🚫 Git ignore rules
└── README.md           # 📖 This file
```

### 📂 โครงสร้างแบบ Modular

โปรเจคนี้ใช้สถาปัตยกรรมแบบ modular เพื่อความเป็นระเบียบและง่ายต่อการดูแลรักษา:

- **main.py** - Flask application และ initialization
- **config.py** - Configuration, constants, และข้อมูลตารางเรียน
- **features.py** - ฟังก์ชันฟีเจอร์ทั้งหมด (schedule, homework, AI)
- **handlers.py** - LINE event handlers และ command routing

---

## 🛠️ เทคโนโลยีที่ใช้ (Tech Stack)

- **Language:** Python 3.8+
- **Framework:** Flask 2.0+
- **APIs:**
  - LINE Messaging API SDK v3
  - Google Generative AI (Gemini)
  - Firebase Admin SDK
- **Deployment:** Render (รองรับ Gunicorn)

---

## 🚀 การติดตั้งและรัน

### 1️⃣ Clone Repository
```bash
git clone https://github.com/your-username/mtc-assistant.git
cd mtc-assistant
```

### 2️⃣ ติดตั้ง Dependencies
```bash
pip install -r requirements.txt
```

### 3️⃣ ตั้งค่า Environment Variables
สร้างไฟล์ `.env` หรือตั้งค่าใน environment:

```bash
export CHANNEL_ACCESS_TOKEN="your_line_channel_access_token"
export CHANNEL_SECRET="your_line_channel_secret"
export GEMINI_API_KEY="your_gemini_api_key"
export PORT=5001
export FLASK_DEBUG=false
```

### 4️⃣ เตรียม Firebase
- วาง `firebase_key.json` ในโฟลเดอร์หลัก
- ตรวจสอบว่าไฟล์อยู่ใน `.gitignore` (เพื่อความปลอดภัย)

### 5️⃣ รันบอท
```bash
python main.py
```

เปิด browser ที่ `http://localhost:5001` เพื่อดู status

---

## 📱 คำสั่งที่รองรับ

### 📋 คำสั่งพื้นฐาน
- `งาน` / `การบ้าน` - ดูใบงาน
- `เว็บโรงเรียน` - ลิงก์เว็บโรงเรียน
- `ตารางเรียน` - ดูตารางเรียน
- `เกรด` - เช็คเกรด
- `คาบต่อไป` - ดูว่าเรียนอะไรต่อ
- `อีกกี่นาที` - เช็คเวลาเหลือก่อนคาบถัดไป
- `ลา` - แบบฟอร์มลา
- `สอบ` - นับถอยหลังวันสอบ

### 🧪 คำสั่งเฉลย
- `ชีวะ` - เฉลยชีววิทยา
- `ฟิสิกส์` - เฉลยฟิสิกส์

### 🎵 ความบันเทิง
- `เปิดเพลง [ชื่อเพลง]` - หาเพลงจาก YouTube

### 💾 การบ้าน (ต้องมี Firebase)
- `สั่งการบ้าน | วิชา | รายละเอียด | วันส่ง`
- `การบ้าน` / `ดูการบ้าน` - ดูการบ้านทั้งหมด
- `ลบการบ้านทั้งหมด` - ล้างข้อมูล

### 🤖 AI
- พิมพ์ข้อความอื่นๆ - ตอบด้วย Gemini AI

### ℹ️ ความช่วยเหลือ
- `คำสั่ง` / `help` - แสดงรายการคำสั่งทั้งหมด

---

## 🔧 การพัฒนา (Development)

### เพิ่มคำสั่งใหม่

1. เพิ่มฟังก์ชันใน `features.py`:
```python
def get_new_feature_message(user_message: str = "") -> TextMessage:
    """ฟีเจอร์ใหม่ของคุณ"""
    return TextMessage(text="Hello from new feature!")
```

2. เพิ่มคำสั่งใน `handlers.py`:
```python
from features import get_new_feature_message

COMMANDS = [
    (("คำสั่งใหม่", "new"), get_new_feature_message),
    # ... commands อื่นๆ
]
```

### แก้ไข Configuration

แก้ไขใน `config.py`:
```python
# เปลี่ยน rate limit
RATE_LIMIT_MAX = 10

# เพิ่ม link ใหม่
NEW_LINK = "https://example.com"

# เพิ่มข้อความใหม่
MESSAGES["NEW_MESSAGE"] = "ข้อความใหม่"
```

---

## 🐛 การ Debug

### เปิด Debug Mode
```bash
export DEBUG=true
export FLASK_DEBUG=true
python main.py
```

### Health Check Endpoints
```bash
# Status check
curl http://localhost:5001/

# Health check (JSON)
curl http://localhost:5001/healthz

# Statistics
curl http://localhost:5001/stats
```

---

## 🚢 Deployment (Render)

### การตั้งค่าใน Render:

1. **Build Command:**
```bash
pip install -r requirements.txt
```

2. **Start Command:**
```bash
gunicorn main:app
```

3. **Environment Variables:**
```
CHANNEL_ACCESS_TOKEN=your_token
CHANNEL_SECRET=your_secret
GEMINI_API_KEY=your_key
PORT=10000
```

4. **ไฟล์ที่ต้องมี:**
   - `requirements.txt` ✅
   - `firebase_key.json` (upload manually)

---

## 🔐 ความปลอดภัย (Security)

### ไฟล์ที่ไม่ควร commit:
- ❌ `firebase_key.json` - Firebase credentials
- ❌ `.env` - Environment variables
- ❌ `__pycache__/` - Python cache

### ตรวจสอบ .gitignore:
```gitignore
firebase_key.json
.env
__pycache__/
*.pyc
*.pyo
```

---

## 📊 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Home page & status |
| `/callback` | POST | LINE webhook |
| `/healthz` | GET | Health check (JSON) |
| `/stats` | GET | Bot statistics |

---

## 🤝 Contributing

ถ้าต้องการมีส่วนร่วมในการพัฒนา:

1. Fork repository
2. สร้าง feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. เปิด Pull Request

---

## 📝 License

โปรเจคนี้สร้างสรรค์โดยนักเรียนห้อง MTC ม.4/2 สำหรับใช้ภายในห้องเรียน

---

## 📞 Support

หากพบปัญหาหรือต้องการความช่วยเหลือ:
- เปิด Issue ใน GitHub
- ติดต่อผู้พัฒนา

---

## 🎓 เครดิต

**พัฒนาโดย:** นักเรียนห้อง MTC 4/2  
**เวอร์ชัน:** 20 (Refactored Modular Edition)  
**ปีการศึกษา:** 2568 (2025-2026)

---

## 🌟 Changelog

### v20 (Refactored) - January 2026
- ✨ Refactored ให้เป็น modular architecture (4 ไฟล์)
- ✨ ปรับปรุงระบบ documentation
- ✨ เพิ่ม health check endpoints
- ✨ ปรับปรุง error handling

### v19 - December 2025
- ✨ เพิ่ม Firebase integration
- ✨ ระบบจัดการการบ้าน
- 🐛 แก้ไขปัญหา rate limiting

### v18 - November 2025
- ✨ Multi-date exam countdown
- ✨ Improved error handling
- ✨ Enhanced logging system

---

**Made with ❤️ by MTC ม.4/2**

🚀 **Happy Coding!**
