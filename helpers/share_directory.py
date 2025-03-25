import logging
import os
import requests
import xml.etree.ElementTree as ET
from requests.auth import HTTPBasicAuth
from urllib.parse import urlparse

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


def share_folder(remote_path):
    # Load credentials from environment variables
    FULL_URL = os.getenv("RCLONE_CONFIG_SEQP_URL")
    USERNAME = os.getenv("RCLONE_CONFIG_SEQP_USER")
    PASSWORD = os.getenv("RCLONE_CONFIG_SEQP_PASS")

    if not FULL_URL or not USERNAME or not PASSWORD:
        logger.error(
            "Missing environment variables for Nextcloud credentials."
        )
        return None

    # Extract only the domain part of the FULL_URL
    parsed_url = urlparse(FULL_URL)
    NEXTCLOUD_URL = f"{parsed_url.scheme}://{parsed_url.netloc}"

    """Creates a public share for a given """
    """Nextcloud folder and returns the share URL."""
    url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares"
    headers = {
        "OCS-APIRequest": "true",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "path": remote_path,
        "shareType": 3,  # Public link share
        "permissions": 1,  # Read-only
    }

    response = requests.post(
        url, headers=headers, data=data, auth=HTTPBasicAuth(USERNAME, PASSWORD)
    )

    if response.status_code == 200:
        try:
            # Parse XML response
            root = ET.fromstring(response.text)
            url_element = root.find(".//url")
            if url_element is not None:
                return url_element.text
            else:
                logger.info("Share URL not found in response.")
                return None
        except ET.ParseError as e:
            logger.error(f"Error parsing XML: {e}")
            return None
    else:
        logger.error(
            f"Failed to create share: {response.status_code} - {response.text}"
        )
        return None
