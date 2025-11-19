from __future__ import annotations

import os
from waitress import serve

# Load env + project root
from mavrykbot.bootstrap import ensure_env_loaded, ensure_project_root

ensure_project_root()
ensure_env_loaded()

# Import Flask app & Sepay path
from mavrykbot.webhooks.sepay_webhook import app, SEPAY_WEBHOOK_PATH

if __name__ == "__main__":
    host = os.getenv("SEPAY_HOST", "0.0.0.0")
    port = int(os.getenv("SEPAY_PORT", "5000"))

    print("=======================================================")
    print("Launching Unified Webhook Server (Sepay + Telegram)")
    print(f"Listening on http://{host}:{port}{SEPAY_WEBHOOK_PATH}")
    print("=======================================================")

    # Run the unified Flask server (Telegram & Sepay)
    serve(app, host=host, port=port)
