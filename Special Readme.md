<div align="center">

# 🤖 MTC Assistant

### LINE Bot ผู้ช่วยอัจฉริยะสำหรับนักเรียน

*ระบบจัดการเวลาเรียน การบ้าน และชีวิตประจำวันด้วย AI*

[![Python](https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.0+-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![LINE](https://img.shields.io/badge/LINE-00C300?style=for-the-badge&logo=line&logoColor=white)](https://github.com/line/line-bot-sdk-python)
[![Firebase](https://img.shields.io/badge/Firebase-FFCA28?style=for-the-badge&logo=firebase&logoColor=black)](https://firebase.google.com/)
[![Gemini AI](https://img.shields.io/badge/Gemini_AI-8E75B2?style=for-the-badge&logo=google&logoColor=white)](https://ai.google.dev/)

![Version](https://img.shields.io/badge/version-20.0-blue?style=flat-square)
![Status](https://img.shields.io/badge/status-production-success?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)

[📖 Documentation](#-documentation) • [✨ Features](#-features) • [🚀 Quick Start](#-quick-start) • [📱 Commands](#-commands)

---

</div>

## 🎯 Overview

**MTC Assistant** คือ LINE Chatbot ที่ออกแบบมาเพื่อช่วยเหลือนักเรียนในการจัดการชีวิตประจำวันในโรงเรียน ตั้งแต่การเช็คตารางเรียน การจัดการการบ้าน ไปจนถึงการนับถอยหลังวันสอบ พร้อมด้วยระบบ AI ที่สามารถตอบคำถามได้อย่างชาญฉลาด

### 💡 Inspiration

เกิดจากความต้องการมี **Personal Assistant** ที่เข้าใจชีวิตนักเรียนจริงๆ ไม่ใช่แค่บอทตอบคำถาม แต่เป็นเพื่อนที่คอยช่วยเหลือจริงๆ ตลอด 24 ชั่วโมง!

### 🎓 Use Cases

- 📚 นักเรียนที่ต้องการจัดการเวลาเรียนได้ดีขึ้น
- 📝 ติดตามการบ้านและงานที่ต้องส่ง
- ⏰ ไม่พลาดคาบเรียนและสอบสำคัญ
- 🤖 มีผู้ช่วยตอบคำถามได้ทุกเมื่อ

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 📅 Real-Time Schedule
- เช็คคาบเรียนปัจจุบัน/ถัดไป
- แสดงเวลา ห้องเรียน และครูผู้สอน
- คำนวณเวลาที่เหลือแบบเรียลไทม์

</td>
<td width="50%">

### ⏳ Smart Countdown
- นับถอยหลังวันสอบ (กลางภาค/ปลายภาค)
- รองรับหลายวันสอบ
- อัพเดทแบบอัตโนมัติ

</td>
</tr>

<tr>
<td width="50%">

### 📝 Homework Management
- เพิ่มการบ้านง่ายๆ
- เก็บข้อมูลใน Firebase
- ดู/ลบการบ้านได้

</td>
<td width="50%">

### 📢 Broadcast System
- ส่งประกาศถึงทุกคน
- เฉพาะ Admin เท่านั้น
- ติดตามสถิติการส่ง

</td>
</tr>

<tr>
<td width="50%">

### 🎵 Music Search
- ค้นหาเพลงใน YouTube
- รองรับภาษาไทย/อังกฤษ
- ได้ link โดยตรง

</td>
<td width="50%">

### 🤖 Gemini AI
- ตอบคำถามทั่วไป
- อธิบายแนวคิดยาก
- Fallback สำหรับคำสั่งที่ไม่รู้จัก

</td>
</tr>
</table>

---

## 🏗️ Architecture

### 📂 Project Structure

```
📦 mtc-assistant/
├── 🚀 main.py              # Entry point & Flask app
├── ⚙️  config.py            # Configuration & constants
├── ✨ features.py          # Feature implementations
├── 🎯 handlers.py          # LINE event handlers
├── 📢 broadcast.py         # Broadcast system
├── 🔑 firebase_key.json    # Firebase credentials (gitignored)
├── 📋 requirements.txt     # Python dependencies
├── 🚫 .gitignore           # Git ignore rules
└── 📖 README.md            # This file
```

### 🗄️ Database Schema

```
Firebase Firestore
├── 📚 homeworks/          # การบ้าน
├── 👥 users/              # ผู้ใช้ (for broadcast)
└── 📢 broadcast_history/  # ประวัติการประกาศ
```

---

## 🛠️ Tech Stack

| Technology | Version | Purpose |
|-----------|---------|---------|
| Python | 3.8+ | Core language |
| Flask | 2.0+ | Web framework |
| Firebase | Admin SDK | Database & Auth |
| LINE Bot SDK | 3.0+ | Chat interface |
| Gemini AI | Latest | AI responses |

---

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- LINE Developer Account
- Firebase Project
- Google AI Studio Account

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/mtc-assistant.git
cd mtc-assistant

# Install dependencies
pip install -r requirements.txt

# Setup environment variables
export CHANNEL_ACCESS_TOKEN="your_token"
export CHANNEL_SECRET="your_secret"
export GEMINI_API_KEY="your_key"

# Run the bot
python main.py
```

---

## 📱 Commands

### 📚 Basic Commands

| Command | Description |
|---------|-------------|
| `งาน` | View worksheets |
| `ตารางเรียน` | View schedule |
| `คาบต่อไป` | Next class |
| `สอบ` | Exam countdown |
| `การบ้าน` | View homework |

### 💾 Homework Commands

```
สั่งการบ้าน | วิชา | รายละเอียด | วันส่ง
```

### 📢 Admin Commands

| Command | Description |
|---------|-------------|
| `ประกาศ [ข้อความ]` | Send announcement |
| `สถิติประกาศ` | View broadcast stats |
| `admin` | Show admin commands |

---

## 🔧 Configuration

### Environment Variables

```bash
CHANNEL_ACCESS_TOKEN=your_line_token
CHANNEL_SECRET=your_line_secret
GEMINI_API_KEY=your_gemini_key
PORT=5001
ADMIN_USER_IDS=U1234567890abcdef
```

---

## 🚢 Deployment

### Deploy to Render

1. Connect GitHub repository
2. Set environment variables
3. Upload `firebase_key.json`
4. Deploy!

```bash
# Build Command
pip install -r requirements.txt

# Start Command
gunicorn main:app
```

---

## 📊 Stats

<div align="center">

![Lines of Code](https://img.shields.io/badge/Lines%20of%20Code-1000+-blue)
![Active Users](https://img.shields.io/badge/Active%20Users-40+-orange)
![Uptime](https://img.shields.io/badge/Uptime-99.9%25-success)

</div>

---

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the Project
2. Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3. Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the Branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👥 Authors

**Developed by MTC ม.4/2 Students**

---

## 🙏 Acknowledgments

- 🎓 เพื่อนๆ ห้อง MTC ม.4/2
- 👨‍🏫 คณะครู
- 🤖 LINE Developers
- 🔥 Google Firebase
- 🧠 Google Gemini

---

## 🗺️ Roadmap

### ✅ Version 20 (Current)
- [x] Modular architecture
- [x] Broadcast system
- [x] AI integration

### 🚧 Future Plans
- [ ] Quick Notes
- [ ] Expense Tracker
- [ ] Study Tracker
- [ ] OCR Support

---

<div align="center">

### 💖 Made with Love by MTC Students

If you find this project helpful, please consider giving it a ⭐!

**[⬆ Back to Top](#-mtc-assistant)**

</div>
