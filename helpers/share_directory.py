import logging
import os
import requests
import subprocess
import xml.etree.ElementTree as ET
from requests.auth import HTTPBasicAuth
from urllib.parse import urlparse

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")


def get_nextcloud_url():
    # Extracts the Nextcloud base URL from
    # the FULL_URL environment variable.
    FULL_URL = os.getenv("RCLONE_CONFIG_SEQP_URL")
    if not FULL_URL:
        logger.error("Missing RCLONE_CONFIG_SEQP_URL environment variable.")
        return None
    parsed_url = urlparse(FULL_URL)
    return f"{parsed_url.scheme}://{parsed_url.netloc}"


def check_existing_share(remote_path, username, password):
    """Checks if a public share already exists for a given Nextcloud folder."""
    NEXTCLOUD_URL = get_nextcloud_url()
    if not NEXTCLOUD_URL:
        return None

    url = (
        f"{NEXTCLOUD_URL}/ocs/v2.php/apps/files_sharing/"
        f"api/v1/shares?path={remote_path}&reshares=true"
    )
    headers = {"OCS-APIRequest": "true", "Content-Type": "application/xml"}

    response = requests.get(
        url, headers=headers, auth=HTTPBasicAuth(username, password)
    )

    if response.status_code == 200:
        try:
            # Parse XML response
            root = ET.fromstring(response.text)
            url_element = root.find(".//url")
            if url_element is not None:
                logger.info(f"Existing share found: {url_element.text}")
                return url_element.text
            else:
                logger.info("Folder exists but no share URL found.")
                return None
        except ET.ParseError as e:
            logger.error(f"Error parsing XML: {e}")
            return None
    elif response.status_code == 404:
        logger.error(f"Folder does not exist: {remote_path}")
        return None
    else:
        logger.error(
            f"Unexpected response: {response.status_code} - {response.text}"
        )
        return None


def create_share(remote_path, label):
    # Creates a public share for a given Nextcloud
    # folder and returns the share URL.
    NEXTCLOUD_URL = get_nextcloud_url()
    if not NEXTCLOUD_URL:
        return None

    USERNAME = os.getenv("RCLONE_CONFIG_SEQP_USER")
    PASSWORD = os.getenv("RCLONE_SEQP_PASS")

    if not USERNAME or not PASSWORD:
        logger.error("Missing Nextcloud username or password.")
        return None

    # First, check if a share already exists
    existing_url = check_existing_share(remote_path, USERNAME, PASSWORD)
    if existing_url:
        return existing_url  # Return existing share URL

    # No existing share, create a new one
    url = f"{NEXTCLOUD_URL}/ocs/v2.php/apps/files_sharing/api/v1/shares"
    headers = {
        "OCS-APIRequest": "true",
        "Content-Type": "application/x-www-form-urlencoded",
    }
    data = {
        "path": remote_path,
        "shareType": 3,  # Public link share
        "permissions": 1,  # Read-only
        "label": label,
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
                logger.info(f"New share created: {url_element.text}")
                return url_element.text
            else:
                logger.error("Share URL not found in response.")
                return None
        except ET.ParseError as e:
            logger.error(f"Error parsing XML: {e}")
            return None
    else:
        logger.error(
            f"Failed to create share: {response.status_code} - {response.text}"
        )
        return None


def sync_folder(local_path, remote_path):
    # Runs the rclone sync command to sync a
    # folder to the remote destination.
    command = [
        "rclone",
        "sync",
        "-P",
        "--copy-links",
        local_path,
        f"seqp:{remote_path}",
    ]

    try:
        logger.info(f"Running command: {' '.join(command)}")
        result = subprocess.run(
            command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        if result.returncode == 0:
            logger.info(f"Sync successful: {result.stdout}")
            return True
        else:
            logger.error(f"Sync failed: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"Error running rclone command: {e}")
        return False


def sync_project(process_id):
    from models.sequencing_upload import SequencingUpload

    # check if we have ITS2, ITS1, SSU_DADA analysis ready.
    process_data = SequencingUpload.get(process_id)

    remote_path = str(process_data["uploads_folder"]) + "/share"
    local_path = "/app/seq_processed/" + remote_path

    sync_folder(local_path, remote_path)
    SequencingUpload.update_field(process_id, "share_sync_completed", True)
    logger.info("Finished calling sync of the project " + str(process_id))


def init_sync_project(process_id):
    from tasks import sync_project_async

    logger.info("We are starting the sync process")

    result = sync_project_async.delay(process_id)
    logger.info(
        f"Celery sync_project_async task "
        f"called successfully! Task ID: {result.id}"
    )
