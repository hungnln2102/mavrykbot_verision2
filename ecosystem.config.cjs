/**
 * PM2 config for mavrykbot (Telegram bot).
 * Usage: pm2 start ecosystem.config.cjs
 * Paths: thư mục chứa run_bot.py (ví dụ /root/mavrykbot_version2).
 */
module.exports = {
  apps: [
    {
      name: "mavrykbot",
      script: "run_bot.py",
      cwd: "/root/mavrykbot_version2",
      interpreter: "/root/mavrykbot_version2/venv/bin/python",
      autorestart: true,
      max_restarts: 10,
    },
  ],
};
