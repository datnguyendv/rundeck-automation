import logging
import requests
from typing import Optional
from dataclasses import dataclass

from .exceptions import NotificationError
from .logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class NotificationMessage:
    title: str
    link: str
    user: str
    color: str = "#36a64f"

    def to_slack_payload(self) -> dict:
        """Convert to Slack attachment format"""
        return {
            "attachments": [
                {
                    "color": self.color,
                    "title": f":rocket: {self.title}",
                    "text": f"🔗 *Link:* <{self.link}>\n👤 *Created By:* {self.user}",
                    "footer": "Rundeck Automation",
                    "ts": None,  # Slack will add timestamp
                }
            ]
        }


class SlackNotifier:
    def __init__(
        self, webhook_url: Optional[str] = None, timeout: int = 10, max_retries: int = 3
    ):
        self.webhook_url = webhook_url
        self.timeout = timeout
        self.max_retries = max_retries

    def send(self, message: NotificationMessage) -> bool:
        if not self.webhook_url:
            logger.warning("Slack webhook URL not configured, skipping notification")
            return False

        payload = message.to_slack_payload()

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"Sending Slack notification (attempt {attempt}/{self.max_retries})"
                )
                response = requests.post(
                    self.webhook_url, json=payload, timeout=self.timeout
                )

                if response.status_code == 200:
                    logger.info("✅ Slack notification sent successfully")
                    return True
                else:
                    logger.error(
                        f"Slack API error: {response.status_code} - {response.text}"
                    )

            except requests.exceptions.Timeout:
                logger.warning(f"Slack request timeout on attempt {attempt}")
            except requests.exceptions.RequestException as e:
                logger.error(f"Slack request failed on attempt {attempt}: {e}")

            if attempt < self.max_retries:
                logger.info("Retrying in 2 seconds...")
                import time

                time.sleep(2)

        error_msg = (
            f"Failed to send Slack notification after {self.max_retries} attempts"
        )
        logger.error(error_msg)
        raise NotificationError(error_msg)

    def send_simple(self, title: str, link: str, user: str) -> bool:
        message = NotificationMessage(title=title, link=link, user=user)
        return self.send(message)


# Backward compatibility function
def send_to_slack(
    title: str, link: str, user: str, webhook_url: Optional[str] = None
) -> bool:
    notifier = SlackNotifier(webhook_url=webhook_url)
    return notifier.send_simple(title, link, user)
