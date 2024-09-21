import requests
import os
import logging

logger = logging.getLogger("my_app_logger")


def get_applications():
    # Replace with your actual API key
    api_key = os.environ.get("GOODGRANDS_API_KEY")
    url = "https://api.cr4ce.com/application"

    # Set up headers for the request
    headers = {
        "Accept": "application/vnd.Creative Force.v2.1+json",  # JSON response
        "x-api-key": api_key,
        "x-api-language": "en_GB",
    }

    # Make a GET request to the API
    response = requests.get(url, headers=headers)

    # Check the response
    if response.status_code == 200:
        logger.info("Success!")
        logger.info(response.json())  # Print the returned data
        return response
    else:
        logger.info(f"Error: {response.status_code}")
        logger.info(response.text)

    return None


def get_goodgrands_users():
    # Replace with your actual API key
    api_key = os.environ.get("GOODGRANDS_API_KEY")
    url = "https://api.cr4ce.com/user"

    # Set up headers for the request
    headers = {
        "Accept": "application/vnd.Creative Force.v2.1+json",  # JSON response
        "x-api-key": api_key,
        "x-api-language": "en_GB",
    }

    # Make a GET request to the API
    response = requests.get(url, headers=headers)

    # Check the response
    if response.status_code == 200:
        logger.info("Success!")
        logger.info(response.json())  # Print the returned data
        return response.json()
    else:
        logger.info(f"Error: {response.status_code}")
        logger.info(response.text)

    return None
