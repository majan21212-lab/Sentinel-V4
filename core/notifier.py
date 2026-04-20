import os
import requests
import logging
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self):
        self.token = os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID")
        self.base_url = f"https://api.telegram.org/bot{self.token}"

    def send_message(self, text: str):
        """Sends a text message to the configured Telegram chat."""
        if not self.token or not self.chat_id or self.token == "your_bot_token_here":
            # log.warning("Telegram Notifier: Token or Chat ID not configured. Skipping alert.")
            return

        url = f"{self.base_url}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        
        try:
            response = requests.post(url, json=payload, timeout=10)
            if response.status_code != 200:
                log.error(f"Telegram API Error: {response.text}")
        except Exception as e:
            log.error(f"Failed to send Telegram message: {e}")

    def send_document(self, file_path: str, caption: str = ""):
        """Uploads a file (like a PDF report) to Telegram."""
        if not self.token or not self.chat_id:
            return

        url = f"{self.base_url}/sendDocument"
        try:
            with open(file_path, "rb") as f:
                files = {"document": f}
                data = {"chat_id": self.chat_id, "caption": caption}
                response = requests.post(url, data=data, files=files, timeout=30)
                if response.status_code != 200:
                    log.error(f"Telegram File Upload Error: {response.text}")
        except Exception as e:
            log.error(f"Failed to upload Telegram document: {e}")

# Global instance
notifier = TelegramNotifier()
