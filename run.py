import os
import requests
from waitress import serve 

from mavrykbot.bootstrap import ensure_env_loaded, ensure_project_root

# --- STEP 1: Setup environment & PYTHONPATH ---
ensure_project_root()
ensure_env_loaded()

# --- BÆ¯á»šC 2: IMPORT CÃC SERVER Cáº¦N CHáº Y ---

# Import server Telegram (cháº¡y Polling)
from mavrykbot.handlers.main import main as run_telegram_bot 

# Import Webhook Receiver Sepay (cháº¡y Flask/Waitress)
from mavrykbot.webhooks.sepay_webhook import app, SEPAY_WEBHOOK_PATH


# =========================================================================
# LOGIC THIáº¾T Láº¬P TELEGRAM WEBHOOK (TÃ¡ch ra khá»i server Sepay)
# =========================================================================

def set_telegram_webhook():
    """Thiáº¿t láº­p URL Webhook chÃ­nh cho Telegram."""
    TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")
    WEBHOOK_URL = (os.getenv("WEBHOOK_URL") or "").strip()
    TELEGRAM_WEBHOOK_SECRET = os.getenv("TELEGRAM_WEBHOOK_SECRET") 

    if not TELEGRAM_BOT_TOKEN or not WEBHOOK_URL:
        print("âŒ BOT_TOKEN hoáº·c WEBHOOK_URL chÆ°a Ä‘Æ°á»£c thiáº¿t láº­p.")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
    
    payload = {"url": WEBHOOK_URL}
    if TELEGRAM_WEBHOOK_SECRET:
        payload["secret_token"] = TELEGRAM_WEBHOOK_SECRET

    try:
        response = requests.post(url, data=payload)
        result = response.json()
        if result.get("ok"):
            print("âœ… Telegram Webhook Ä‘Ã£ Ä‘Æ°á»£c thiáº¿t láº­p thÃ nh cÃ´ng!")
        else:
            print(f"âŒ Lá»—i khi thiáº¿t láº­p Telegram webhook: {result}")
    except Exception as e:
        print(f"âš ï¸ Lá»—i káº¿t ná»‘i Telegram API: {e}")


# --- BÆ¯á»šC 3: ÄIá»€U PHá»I KHá»žI CHáº Y ---

if __name__ == '__main__':
    
    print("=======================================================")
    print("ðŸ¤– KHá»žI Äá»˜NG Cáº¤U HÃŒNH VÃ€ CÃC SERVER")
    print("=======================================================")
    
    # 1. Cáº¤U HÃŒNH TELEGRAM WEBHOOK (TÃ¡c vá»¥ 1 láº§n)
    set_telegram_webhook()
    
    # 2. KHá»žI CHáº Y SEPAY WEBHOOK SERVER (TÃ¡c vá»¥ liÃªn tá»¥c, block code)
    print("\n-------------------------------------------------------")
    print(f"âœ… Báº¯t Ä‘áº§u cháº¡y Sepay Webhook Server (Waitress)")
    print(f"   Láº¯ng nghe táº¡i http://0.0.0.0:5000{SEPAY_WEBHOOK_PATH}")
    print("-------------------------------------------------------")
    
    # Sá»­ dá»¥ng Waitress Ä‘á»ƒ phá»¥c vá»¥ á»©ng dá»¥ng Flask (app)
    serve(app, host='0.0.0.0', port=5000)
    
    # NOTE: Báº¡n cáº§n khá»Ÿi cháº¡y Telegram Bot Polling (main.py) báº±ng má»™t terminal riÃªng.
