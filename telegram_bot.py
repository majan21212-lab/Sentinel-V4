import os
import requests
import logging
from datetime import datetime

log = logging.getLogger(__name__)

class TelegramBot:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}/"
        log.info("📡 TelegramBot initialized. Ready for Rich Alerts.")

    def send_message(self, text: str, parse_mode="HTML"):
        """Sends a standard text message to the configured chat."""
        if not self.token or not self.chat_id:
            log.warning("Telegram configuration missing. Skipping message.")
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
            f"<b>💎 JEWEL ELITE SIGNAL</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Asset:</b> {signal['symbol']}\n"
            f"<b>Action:</b> {direction_emoji}\n"
            f"<b>Pattern:</b> {signal.get('pattern', 'SMC Logic')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>📍 Entry:</b> <code>{signal['entry']:.5f}</code>\n"
            f"<b>🎯 TP1:</b> <code>{signal['tp1']:.5f}</code>\n"
            f"<b>🛡️ SL:</b> <code>{signal['sl']:.5f}</code>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>🔥 Score:</b> {signal['score']:.1f}%\n"
            f"<b>🧠 Rationale:</b> {signal.get('reason', 'High Confluence Alignment')}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🕒 <i>Time: {datetime.now().strftime('%H:%M:%S')}</i>"
        )
        return self.send_message(msg)

    def send_security_alert(self, alert_type: str, details: str):
        """Sends critical security and risk alerts."""
        emoji = "🛡️"
        if "NEWS" in alert_type.upper(): emoji = "📅"
        if "SHIELD" in alert_type.upper() or "HALT" in alert_type.upper(): emoji = "🚨"
        
        msg = (
            f"{emoji} <b>SENTINEL SECURITY ALERT</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Type:</b> {alert_type}\n"
            f"<b>Details:</b> {details}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"🕒 <i>Status: ACTIVE GUARD</i>"
        )
        return self.send_message(msg)

# Singleton instance
telegram_bot = TelegramBot()
