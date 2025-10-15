# # notification.py
# import requests
# import sys
#
# # === CONFIG ===
# WEBHOOK_URL = ""
#
# def send_to_slack(title: str, link: str, user: str):
#     """
#     Gửi message vào Slack với title, link và user.
#     """
#     payload = {
#         "attachments": [
#             {
#                 "color": "#36a64f",
#                 "title": f":rocket: {title}",
#                 "text": f"🔗 *Link:* <{link}> \n👤 *Created By:* {user}"
#             }
#         ]
#     }
#
#     response = requests.post(WEBHOOK_URL, json=payload)
#     if response.status_code != 200:
#         raise Exception(f"Slack returned {response.status_code}: {response.text}")
#     print("✅ Sent Slack notification successfully!")
#
# if __name__ == "__main__":
#     if len(sys.argv) < 4:
#         print("Usage: python notification.py <title> <link> <user>")
#         sys.exit(1)
#
#     title = sys.argv[1]
#     link = sys.argv[2]
#     user = sys.argv[3]
#     send_to_slack(title, link, user)
#
# notification.py

import requests

WEBHOOK_URL = ""

def send_to_slack(title: str, link: str, user: str):
    payload = {
        "attachments": [
            {
                "color": "#36a64f",
                "title": title,
                "text": f"Link: {link}\nCreated By: {user}",
            }
        ]
    }
    response = requests.post(WEBHOOK_URL, json=payload)
    if response.status_code != 200:
        raise Exception(f"Slack returned {response.status_code}: {response.text}")
    print("Sent Slack notification successfully!")

