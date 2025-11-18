import json
import logging
import hashlib
import hmac
from datetime import datetime
from typing import Dict, Any, Optional
from flask import Flask, request, jsonify
from waitress import serve
from mavrykbot.core.config import load_sepay_config
from mavrykbot.core.database import db
from mavrykbot.core.db_schema import PAYMENT_RECEIPT_TABLE, PaymentReceiptColumns

# --- Khởi tạo Flask App ---
app = Flask(__name__)

# --- Cấu hình Logging ---
logger = logging.getLogger(__name__)

# --- Cấu hình Sepay (Tải một lần) ---
try:
    SEPAY_CFG = load_sepay_config()
except RuntimeError:
    logger.warning("SEPAY config not fully loaded. Webhook verification may fail.")
    SEPAY_CFG = None

SEPAY_WEBHOOK_PATH = "/api/payment/notify" 

# =========================================================================
# LỌC & XÁC MINH CHỮ KÝ (HMAC-SHA256)
# =========================================================================

def verify_sepay_signature(request_body: bytes, signature: Optional[str]) -> bool:
    """Xác minh chữ ký HMAC-SHA256 của Sepay."""
    if not SEPAY_CFG or not SEPAY_CFG.webhook_secret:
        return False
    if not signature:
        return False
        
    expected_signature = hmac.new(
        SEPAY_CFG.webhook_secret.encode('utf-8'),
        request_body,
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)

# =========================================================================
# XỬ LÝ DỮ LIỆU VÀ LƯU VÀO SQL
# =========================================================================

def insert_payment_receipt(transaction_data: Dict[str, Any]) -> None:
    """Trích xuất dữ liệu Sepay và ghi vào PostgreSQL."""
    
    transaction_content = transaction_data.get('transaction_content', '')
    ma_don_hang = transaction_content.split()[-1] 
    
    ngay_thanh_toan_str = transaction_data.get('transaction_date')
    ngay_thanh_toan = datetime.strptime(ngay_thanh_toan_str, "%Y-%m-%d %H:%M:%S").date() 
    
    so_tien_str = transaction_data.get('amount_in', '0').split('.')[0]
    so_tien = int(so_tien_str)

    nguoi_gui = transaction_content.split()[0]
    
    # 5. Insert vào bảng payment_receipt
    sql_query = f"""
        INSERT INTO {PAYMENT_RECEIPT_TABLE} (
            {PaymentReceiptColumns.MA_DON_HANG}, 
            {PaymentReceiptColumns.NGAY_THANH_TOAN}, 
            {PaymentReceiptColumns.SO_TIEN}, 
            {PaymentReceiptColumns.NGUOI_GUI}, 
            {PaymentReceiptColumns.NOI_DUNG_CK}
        ) VALUES (
            %s, %s, %s, %s, %s
        )
    """
    params = (ma_don_hang, ngay_thanh_toan, so_tien, nguoi_gui, transaction_content)
    
    db.execute(sql_query, params)
    logger.info(f"Payment receipt for Order {ma_don_hang} successfully saved.")

# =========================================================================
# ENDPOINTS (ROUTES) CHO CẢ SEPAY VÀ TELEGRAM
# =========================================================================

@app.route(SEPAY_WEBHOOK_PATH, methods=['POST'])
def sepay_webhook_receiver():
    """Endpoint lắng nghe yêu cầu POST từ Sepay."""
    
    raw_body = request.get_data()
    # Sepay sử dụng header X-SEPAY-SIGNATURE
    signature = request.headers.get('X-SEPAY-SIGNATURE') 
    
    if not verify_sepay_signature(raw_body, signature or ''):
        logger.error("Sepay Webhook signature verification failed.")
        return jsonify({"message": "Invalid Signature"}), 403
    
    try:
        data = json.loads(raw_body.decode('utf-8'))
        transaction_data = data.get('transaction') 
        
        if not transaction_data:
            return jsonify({"message": "Missing Transaction Data"}), 400
            
    except json.JSONDecodeError:
        return jsonify({"message": "Invalid JSON"}), 400

    try:
        insert_payment_receipt(transaction_data)
        return jsonify({"message": "OK"}), 200
    except Exception as e:
        logger.error(f"Error processing and saving data: {e}", exc_info=True)
        return jsonify({"message": "Internal Server Error"}), 500


# --- ROUTE MỚI ĐƯỢC THÊM VÀO ĐỂ XỬ LÝ LỖI 404 CỦA TELEGRAM ---
@app.route('/webhook', methods=['POST'])
def telegram_webhook_receiver():
    """Endpoint lắng nghe yêu cầu POST từ Telegram."""
    
    if request.method == 'POST':
        # 1. Lấy dữ liệu tin nhắn (JSON)
        update = request.get_json()
        
        # 2. GỌI LOGIC XỬ LÝ CHÍNH CỦA BOT TẠI ĐÂY
        # NOTE: Bạn cần import hoặc gọi hàm xử lý chính của bot (ví dụ: handle_update(update))
        # Nếu bot của bạn là một phần của hệ thống này, hãy đảm bảo các hàm xử lý được import.
        # Hiện tại, chỉ trả về 200 OK để Telegram ngừng báo lỗi 404.
        
        # Trả về phản hồi thành công ngay lập tức
        return '', 200
    
    # Nếu không phải POST, trả về 404 để tránh truy cập trực tiếp
    return 'Not Found', 404
# --- KẾT THÚC ROUTE MỚI ---


if __name__ == '__main__':
    # File này chỉ chạy SERVER khi được gọi trực tiếp
    print("\n=======================================================")
    print(f"✅ Bắt đầu chạy Sepay Webhook Server (Waitress)")
    print(f"   Lắng nghe tại http://0.0.0.0:5000{SEPAY_WEBHOOK_PATH}")
    print("=======================================================")
    
    serve(app, host='0.0.0.0', port=5000)