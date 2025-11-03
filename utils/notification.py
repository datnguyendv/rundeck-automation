from typing import Optional
from dataclasses import dataclass
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from .exceptions import NotificationError
from .logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class NotificationMessage:
    title: str
    link: str
    user: str

    def to_slack_blocks(self) -> list:
        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f":rocket: {self.title}",
                    "emoji": True,
                },
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f":link: *Link:* {self.link}\n"},
                    {
                        "type": "mrkdwn",
                        "text": f":bust_in_silhouette: *Created By:* {self.user}",
                    },
                ],
            },
            {
                "type": "context",
                "elements": [{"type": "mrkdwn", "text": "Rundeck Automation"}],
            },
        ]


class SlackNotifier:
    def __init__(
        self,
        bot_token: Optional[str] = None,
        webhook_url: Optional[str] = None,
        channel_id: Optional[str] = None,
        timeout: int = 10,
        # color: str = ,
        max_retries: int = 3,
    ):
        self.bot_token = bot_token
        self.webhook_url = webhook_url
        self.channel_id = channel_id
        self.timeout = timeout
        self.max_retries = max_retries
        self.color = "#36a64f"

        # Initialize Slack client nếu có bot token
        self.client = WebClient(token=bot_token)

    def send(
        self,
        message: NotificationMessage,
        thread_ts: Optional[str] = None,
    ) -> Optional[dict]:
        if not self.channel_id:
            logger.error("No channel specified and no default channel configured")
            return None

        for attempt in range(1, self.max_retries + 1):
            try:
                logger.info(
                    f"Sending Slack message via API (attempt {attempt}/{self.max_retries})"
                )

                response = self.client.chat_postMessage(
                    channel=self.channel_id,
                    blocks=message.to_slack_blocks(),
                    text=message.title,
                    thread_ts=thread_ts,
                )

                if response["ok"]:
                    logger.info(
                        f":white_check_mark: Slack message sent successfully to {self.channel_id}"
                    )
                    # Return timestamp và channel để có thể reply sau
                    return {
                        "ts": response["ts"],
                        "channel": response["channel"],
                        "thread_ts": response.get("thread_ts", response["ts"]),
                    }
                else:
                    logger.error(f"Slack API returned ok=False: {response}")

            except SlackApiError as e:
                logger.error(
                    f"Slack API error on attempt {attempt}: {e.response['error']}"
                )
                if e.response["error"] in ["channel_not_found", "not_in_channel"]:
                    logger.error(
                        f"Bot không có quyền truy cập channel {self.channel_id}"
                    )
                    break  # Không retry nếu lỗi permission

            except Exception as e:
                logger.error(f"Unexpected error on attempt {attempt}: {e}")

            if attempt < self.max_retries:
                logger.info("Retrying in 2 seconds...")
                import time

                time.sleep(2)

        error_msg = f"Failed to send Slack message after {self.max_retries} attempts"
        logger.error(error_msg)
        raise NotificationError(error_msg)
