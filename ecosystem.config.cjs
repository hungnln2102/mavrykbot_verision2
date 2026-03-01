/**
 * PM2 config for mavrykbot (Telegram bot).
 * Usage: pm2 start ecosystem.config.cjs
 * Paths: adjust cwd and interpreter to your server (e.g. /root/mavrykbot_verision2).
 */
module.exports = {
  apps: [
    {
      name: "mavrykbot",
      script: "run_bot.py",
      cwd: "/root/mavrykbot_verision2",
      interpreter: "/root/mavrykbot_verision2/venv/bin/python",
      autorestart: true,
      max_restarts: 10,
    },
  ],
};
