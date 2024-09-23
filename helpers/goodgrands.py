import requests
import os
import logging

logger = logging.getLogger("my_app_logger")


def get_goodgrands_applications():
    api_key = os.environ.get("GOODGRANDS_API_KEY")
    url = "https://api.cr4ce.com/application"  # Replace with the correct endpoint if needed
    headers = {
        "Accept": "application/vnd.Creative Force.v2.1+json",
        "x-api-key": api_key,
        "x-api-language": "en_GB",
    }
    
    all_applications = []
    while url:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            all_applications.extend(data['data'])  # Append the applications to the list
            url = data.get('next_page_url')  # Get the next page URL
        else:
            logger.info(f"Error: {response.status_code}")
            logger.info(response.text)
            break

    return all_applications if all_applications else None

def get_goodgrands_application(slug):
    api_key = os.environ.get("GOODGRANDS_API_KEY")
    url = "https://api.cr4ce.com/application/" + slug  # Replace with the correct endpoint if needed
    headers = {
        "Accept": "application/vnd.Creative Force.v2.1+json",
        "x-api-key": api_key,
        "x-api-language": "en_GB",
    }
    
    application = []
    response = requests.get(url, headers=headers)
    logger.info(response.text)
    if response.status_code == 200:
        application = response.json()
        logger.info(application)
    else:
        logger.info(f"Error: {response.status_code}")
        logger.info(response.text)

    return application if application else None


def get_goodgrands_users():
    api_key = os.environ.get("GOODGRANDS_API_KEY")
    url = "https://api.cr4ce.com/user"
    headers = {
        "Accept": "application/vnd.Creative Force.v2.1+json",
        "x-api-key": api_key,
        "x-api-language": "en_GB",
    }
    all_users = []
    while url:
        response = requests.get(url, headers=headers)

        if response.status_code == 200:
            data = response.json()
            all_users.extend(data['data'])  # Append the users to the list
            url = data.get('next_page_url')  # Get the next page URL
        else:
            logger.info(f"Error: {response.status_code}")
            logger.info(response.text)
            break

    return all_users if all_users else None
