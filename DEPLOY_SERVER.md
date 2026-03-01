# Deploy bot lên server Linux (PM2)

Hướng dẫn khi deploy trên server (ví dụ `/root/mavrykbot_verision2`) với Python bị "externally-managed-environment" và chạy bằng PM2.

## 1. Tạo virtual environment (venv)

Trên server **chưa có** thư mục `venv` hoặc `.venv`, cần tạo mới:

```bash
cd /root/mavrykbot_verision2
python3 -m venv venv
```

Nếu báo thiếu module: `apt install python3-venv` (Debian/Ubuntu) rồi chạy lại lệnh trên.

## 2. Kích hoạt venv và cài dependencies

```bash
source venv/bin/activate
pip install -r requirements.txt
```

Sau khi cài xong có thể chạy thử:

```bash
python run_bot.py
```

Ctrl+C để dừng. Nếu chạy được không lỗi "No module named 'telegram'" thì môi trường đã đúng.

## 3. Chạy bằng PM2 (dùng Python trong venv)

PM2 cần **script** là file `.py`, còn **interpreter** là Python trong venv. Chạy từ đúng thư mục:

```bash
cd /root/mavrykbot_verision2
pm2 start run_bot.py --name mavrykbot --interpreter /root/mavrykbot_verision2/venv/bin/python
```

- `run_bot.py` = script (phải có trong thư mục hiện tại).
- `--interpreter` = đường dẫn đầy đủ tới `venv/bin/python`.

**Lưu ý:** Không dùng `pm2 start /path/to/venv/bin/python -- run_bot.py` — PM2 sẽ coi path đó là script và báo "Script not found". Đúng là `pm2 start run_bot.py --interpreter /path/to/venv/bin/python`.

## 4. Lệnh PM2 thường dùng

```bash
pm2 list
pm2 logs mavrykbot
pm2 restart mavrykbot
pm2 stop mavrykbot
```

## 5. (Tùy chọn) Lưu cấu hình PM2

Tạo file `ecosystem.config.cjs` trong thư mục bot:

```javascript
module.exports = {
  apps: [{
    name: "mavrykbot",
    script: "run_bot.py",
    cwd: "/root/mavrykbot_verision2",
    interpreter: "/root/mavrykbot_verision2/venv/bin/python",
    autorestart: true,
    max_restarts: 10,
  }],
};
```

Sau đó:

```bash
pm2 start ecosystem.config.cjs
pm2 save
pm2 startup
```
