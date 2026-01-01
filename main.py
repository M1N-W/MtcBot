# -*- coding: utf-8 -*-
"""
MTC Assistant v.20 (Refactored Modular Edition)
Main entry point with Flask routes and initialization

Structure:
- config.py: Configuration, constants, messages
- features.py: Feature functions (schedule, homework, AI, etc.)
- handlers.py: LINE handlers and command routing
- main.py: Flask app and initialization (this file)
"""

import os
import datetime
from flask import Flask, request, abort, jsonify

# Firebase imports
import firebase_admin
from firebase_admin import credentials, firestore

# Gemini imports
import google.generativeai as genai

# LINE imports
from linebot.v3.exceptions import InvalidSignatureError

# Import from our modules
from config import (
    logger, setup_logging, validate_config,
    PORT, FLASK_DEBUG, ACCESS_TOKEN, CHANNEL_SECRET, GEMINI_API_KEY,
    FIREBASE_KEY_PATH, GEMINI_MODEL_NAME, LOCAL_TZ
)

from handlers import handler

import features  # Import features module to set global variables

# ============================================================================
# FLASK APP INITIALIZATION
# ============================================================================
app = Flask(__name__)

# Setup logging
setup_logging()
app.logger.handlers = logger.handlers
app.logger.setLevel(logger.level)

# Validate configuration
validate_config()

# ============================================================================
# FIREBASE INITIALIZATION
# ============================================================================
db = None
try:
    if os.path.exists(FIREBASE_KEY_PATH):
        if not firebase_admin._apps:
            cred = credentials.Certificate(FIREBASE_KEY_PATH)
            firebase_admin.initialize_app(cred)
        db = firestore.client()
        features.set_database(db)  # Set database in features module
        logger.info("🔥 Firebase Connected Successfully!")
    else:
        logger.warning(f"⚠️ Missing {FIREBASE_KEY_PATH}. Homework DB features will be disabled.")
except Exception as e:
    logger.exception(f"❌ Firebase Init Error: {e}")

# ============================================================================
# GEMINI AI INITIALIZATION
# ============================================================================
gemini_model = None
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        features.set_gemini_model(gemini_model)  # Set model in features module
        logger.info(f"🤖 Gemini model '{GEMINI_MODEL_NAME}' instantiated.")
    except Exception as e:
        logger.error(f"❌ Gemini model init failed: {e}")
        gemini_model = None

# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route("/callback", methods=['POST'])
def callback():
    """Handle LINE webhook callback"""
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
    
    return (
        f"🤖 MTC Assistant v20 (Refactored Modular Edition)\n\n"
        f"Status:\n"
        f"  LINE: {cfg_ok}\n"
        f"  Gemini AI: {gemini_status}\n"
        f"  Firebase: {db_status}\n\n"
        f"Endpoints:\n"
        f"  /callback - LINE webhook\n"
        f"  /healthz - Health check (JSON)\n"
    )

@app.route("/healthz", methods=['GET'])
def healthz():
    """Health check endpoint (JSON)"""
    return jsonify({
        "status": "ok",
        "version": "20-refactored-modular",
        "timestamp": datetime.datetime.now(tz=LOCAL_TZ).isoformat(),
        "services": {
            "line": bool(ACCESS_TOKEN and CHANNEL_SECRET),
            "gemini": bool(GEMINI_API_KEY and gemini_model),
            "firebase": bool(db)
        }
    }), 200

@app.route("/stats", methods=['GET'])
def stats():
    """Show bot statistics"""
    from handlers import _user_message_history
    
    total_users = len(_user_message_history)
    total_messages = sum(len(msgs) for msgs in _user_message_history.values())
    
    return jsonify({
        "total_users": total_users,
        "total_messages": total_messages,
        "rate_limit_tracked_users": total_users
    }), 200

# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found(error):
    """Handle 404 errors"""
    return jsonify({
        "error": "Not Found",
        "message": "The requested endpoint does not exist"
    }), 404

@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    logger.error(f"Internal server error: {error}")
    return jsonify({
        "error": "Internal Server Error",
        "message": "An unexpected error occurred"
    }), 500

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def print_startup_banner():
    """Print startup banner with configuration info"""
    banner = """
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║           🤖 MTC Assistant v20 (Refactored)              ║
║                                                           ║
║  Modular Edition - Clean & Maintainable Architecture     ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
"""
    logger.info(banner)
    logger.info("Configuration:")
    logger.info(f"  • Port: {PORT}")
    logger.info(f"  • Debug Mode: {FLASK_DEBUG}")
    logger.info(f"  • LINE Bot: {'✅ Configured' if ACCESS_TOKEN and CHANNEL_SECRET else '❌ Not configured'}")
    logger.info(f"  • Gemini AI: {'✅ Ready' if gemini_model else '❌ Disabled'}")
    logger.info(f"  • Firebase: {'✅ Connected' if db else '❌ Disconnected'}")
    logger.info("")
    logger.info("Module Structure:")
    logger.info("  📁 config.py    - Configuration & Constants")
    logger.info("  📁 features.py  - Feature Functions")
    logger.info("  📁 handlers.py  - LINE Handlers & Routing")
    logger.info("  📁 main.py      - Flask App (this file)")
    logger.info("")
    logger.info("🚀 Server starting...")
    logger.info("=" * 60)

if __name__ == "__main__":
    print_startup_banner()
    
    # Run Flask app
    app.run(
        host="0.0.0.0",
        port=PORT,
        debug=FLASK_DEBUG
    )
