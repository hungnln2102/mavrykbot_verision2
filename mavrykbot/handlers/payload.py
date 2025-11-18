import requests
import json
import logging

# Thiết lập logging
logging.basicConfig(level=logging.INFO)

# URL webhook của bạn
WEBHOOK_URL = "https://botapi.mavrykpremium.store/bot/webhook"

# Dữ liệu mẫu (payload) mà dịch vụ thanh toán sẽ gửi.
# BẠN CẦN ĐIỀU CHỈNH CẤU TRÚC NÀY
payload = {
    "transaction_id": "TRANS_123456789",
    "order_id": "LE1711250001",
    "amount": 150000,
    "status": "success",
    "message": "Thanh toán thành công qua VietQR"
}

# Tiêu đề HTTP (headers)
headers = {
    "Content-Type": "application/json"
    # Thêm tiêu đề bảo mật nếu webhook yêu cầu (ví dụ: 'X-Signature': '...')
}

def test_webhook():
    """Gửi yêu cầu POST đến URL webhook để mô phỏng thông báo thanh toán."""
    logging.info(f"Đang gửi yêu cầu POST đến: {WEBHOOK_URL}")
    
    try:
        response = requests.post(
            WEBHOOK_URL, 
            data=json.dumps(payload), 
            headers=headers,
            # Thêm timeout để tránh bị treo
            timeout=10 
        )
        
        # In trạng thái và nội dung phản hồi từ webhook
        logging.info(f"Mã trạng thái HTTP: {response.status_code}")
        logging.info(f"Nội dung phản hồi: {response.text}")
        
        # Kiểm tra thành công (thường là mã 200 hoặc 204)
        if 200 <= response.status_code < 300:
            logging.info("Kiểm tra Webhook thành công!")
        else:
            logging.error("Kiểm tra Webhook thất bại. Máy chủ trả về lỗi.")
            
    except requests.exceptions.RequestException as e:
        logging.error(f"Lỗi kết nối hoặc yêu cầu: {e}")

if __name__ == "__main__":
    test_webhook()