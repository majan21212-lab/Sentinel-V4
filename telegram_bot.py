import os
import requests
import logging
import asyncio
from datetime import datetime

log = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}/"
        if self.token and self.chat_id:
            log.info("📡 TelegramBot initialized. Ready for Rich Alerts.")
        else:
            log.warning("📡 Telegram configuration missing. Alerts disabled.")

    def send_message(self, text: str, parse_mode="HTML"):
        """Sends a standard text message to the configured chat."""
        if not self.token or not self.chat_id:
            return

        url = f"{self.base_url}sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            return response.json()
        except Exception as e:
            log.error(f"Telegram Send Error: {e}")
            return None

    def send_signal_alert(self, signal: dict):
        """Sends a rich, formatted signal alert with emojis."""
        direction_emoji = "🔵 LONG" if signal["direction"] == "LONG" else "🔴 SHORT"
        
        msg = (
            f"<b>💎 FLEET COMMAND ALERT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Asset:</b> {signal['symbol']}\n"
            f"<b>Action:</b> {direction_emoji}\n"
            f"<b>Pattern:</b> {signal.get('pattern', 'SMC Logic')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>📍 Entry:</b> <code>{signal['entry']:.5f}</code>\n"
            f"<b>🎯 TP1:</b> <code>{signal['tp1']:.5f}</code>\n"
            f"<b>🛡️ SL:</b> <code>{signal['sl']:.5f}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>🔥 Score:</b> {signal.get('score', 0):.1f}%\n"
            f"<b>🧠 Rationale:</b> {signal.get('reason', 'High Confluence Alignment')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🕒 <i>Time: {datetime.now().strftime('%H:%M:%S')}</i>"
        )
        return self.send_message(msg)

    async def poll_commands(self):
        """Background task to poll for commands from authorized users."""
        if not self.token: return
        
        last_update_id = 0
        log.info("📡 Telegram Command Listener Started.")
        
        import state_manager as state
        
        while True:
            try:
                url = f"{self.base_url}getUpdates?offset={last_update_id + 1}&timeout=30"
                response = requests.get(url, timeout=35)
                data = response.json()
                
                if data.get("ok"):
                    for update in data.get("result", []):
                        last_update_id = update["update_id"]
                        message = update.get("message")
                        if not message: continue
                        
                        text = message.get("text", "").lower().strip()
                        chat_id = str(message["chat"]["id"])
                        
                        # Security Check: Only respond to the authorized chat_id
                        if chat_id != self.chat_id:
                            log.warning(f"🚫 Unauthorized Telegram access attempt from {chat_id}")
                            continue

                        if text in ["start bot", "/start_bot", "/start"]:
                            state.SHARED_DATA["is_bot_active"] = True
                            state.save_shared_state(state.SHARED_DATA)
                            self.send_message("✅ <b>Sentinel Bot Activated</b>\nStrategy scanning and auto-execution is now ONLINE.")
                            log.info("🤖 Bot STARTED via Telegram command.")
                        
                        elif text in ["stop bot", "/stop_bot", "/stop"]:
                            state.SHARED_DATA["is_bot_active"] = False
                            state.save_shared_state(state.SHARED_DATA)
                            self.send_message("🛑 <b>Sentinel Bot Deactivated</b>\nStrategy scanning is now PAUSED.")
                            log.info("🤖 Bot STOPPED via Telegram command.")
                            
                        elif text in ["status", "/status"]:
                            active = state.SHARED_DATA.get("is_bot_active", False)
                            status = "🟢 ONLINE" if active else "🔴 PAUSED"
                            self.send_message(f"📊 <b>Sentinel Status:</b> {status}")

                await asyncio.sleep(1)
            except Exception as e:
                log.error(f"Telegram Polling Error: {e}")
                await asyncio.sleep(5)

# Singleton instance
telegram_bot = TelegramBot()
