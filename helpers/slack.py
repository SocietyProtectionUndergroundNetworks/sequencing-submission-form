import requests
import os


def send_message_to_slack(text):
    SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
    payload = {"text": text}
    response = requests.post(SLACK_WEBHOOK_URL, json=payload)
    return response
