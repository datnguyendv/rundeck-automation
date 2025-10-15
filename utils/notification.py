"""
Module gửi notification tới Slack
"""
import os
import requests
from typing import Optional


class SlackNotifier:
    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("SLACK_WEBHOOK_URL", "")
    
    def send(self, title: str, link: str, user: str) -> bool:
        """
        Gửi notification tới Slack
        Returns: True nếu thành công, False nếu thất bại
        """
        if not self.webhook_url:
            print("⚠️ [WARN] Slack webhook URL not configured, skipping notification")
            return False
        
        payload = {
            "attachments": [
                {
                    "color": "#36a64f",
                    "title": f":rocket: {title}",
                    "text": f"🔗 *Link:* <{link}> \n👤 *Created By:* {user}"
                }
            ]
        }
        
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code != 200:
                print(f"❌ Slack returned {response.status_code}: {response.text}")
                return False
            print("✅ Sent Slack notification successfully!")
            return True
        except requests.exceptions.RequestException as e:
            print(f"❌ Failed to send Slack notification: {e}")
            return False


# Backward compatibility - function interface
def send_to_slack(title: str, link: str, user: str) -> bool:
    """Hàm wrapper để dùng trực tiếp"""
    notifier = SlackNotifier()
    return notifier.send(title, link, user)
