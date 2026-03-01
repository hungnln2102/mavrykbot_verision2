# Chạy Bot + API Website trên máy local

Khi server production tắt, có thể chạy API Website local và cho bot gọi về `http://127.0.0.1:4000`.

## 1. Cấu hình Bot (.env)

Trong `.env` của bot đã set sẵn cho local:

```env
NOTIFY_ORDER_BASE_URL=http://127.0.0.1:4000
NOTIFY_ORDER_API_KEY=<cùng giá trị với server Website>
```

Khi bật lại server production, trên **máy chạy bot production** thêm vào .env (hoặc đổi NOTIFY_ORDER_BASE_URL):

```env
NOTIFY_ORDER_BASE_URL_PRODUCTION=https://api.mavrykpremium.store
```

(Khi NOTIFY_ORDER_BASE_URL là 127.0.0.1/localhost, bot sẽ tự dùng NOTIFY_ORDER_BASE_URL_PRODUCTION nếu có.)

## 2. Cấu hình Server Website

- Trong **Website/my-store/apps/server/.env** phải có:
  - `NOTIFY_ORDER_API_KEY` = **cùng giá trị** với `NOTIFY_ORDER_API_KEY` trong .env của bot.
  - `PORT=4000` (mặc định) hoặc port bạn chạy server.
- Database: server cần kết nối được tới PostgreSQL (bảng `partner.supplier` cho GET /api/orders/suppliers). Có thể dùng DB trên máy local hoặc DB từ xa (ví dụ 110.172.28.206) nếu mở kết nối.

## 3. Chạy

**Terminal 1 – Server Website (API):**

```bash
cd D:\Desktop\Personal\Project\admin_store\Website\my-store
npm run dev:server
```

Đợi log `Server is running on http://localhost:4000`.

**Terminal 2 – Bot:**

```bash
cd D:\Desktop\Personal\Project\admin_store\mavrykstore_bot
python run_bot.py
```

## 4. Kiểm tra nhanh

Sau khi server Website đã chạy:

```bash
cd D:\Desktop\Personal\Project\admin_store\mavrykstore_bot
python -c "from mavrykbot.bootstrap import ensure_env_loaded; ensure_env_loaded(); from mavrykbot.handlers.new_order.api import get_suppliers; ok, s, e = get_suppliers(); print('OK:', ok, 'Count:', len(s))"
```

Nếu `OK: True` và `Count` ≥ 0 thì bot sẽ gọi được API (suppliers có thể rỗng nếu bảng `partner.supplier` chưa có dữ liệu).
