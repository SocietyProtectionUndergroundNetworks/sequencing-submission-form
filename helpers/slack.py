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


def send_message_to_slack_mobile(text):
    url = os.environ.get("SLACK_WEBHOOK_URL_MOBILE")
    if not url:
        return None
    try:
        response = requests.post(url, json={"text": text})
        return response
    except Exception:
        logger.exception("Failed to send mobile Slack notification")
        return None
