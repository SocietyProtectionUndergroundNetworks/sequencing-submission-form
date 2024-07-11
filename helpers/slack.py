import requests
import os
import logging

logger = logging.getLogger("my_app_logger")


def send_message_to_slack(text):
    SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL")
    logger.info(SLACK_WEBHOOK_URL)
    if SLACK_WEBHOOK_URL != "":
        payload = {"text": text}
        response = requests.post(SLACK_WEBHOOK_URL, json=payload)
        return response
    return None
