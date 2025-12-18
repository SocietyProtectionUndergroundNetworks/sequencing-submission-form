import os
import logging
import base64
import hashlib

# Library about google cloud storage
from google.cloud import storage
from models.db_model import (
    SequencingFilesUploadedTable,
)
from helpers.dbm import session_scope
from google.api_core.exceptions import Forbidden, NotFound

logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


def calculate_md5(file_path):
    md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            md5.update(chunk)
    return md5.hexdigest()


def list_buckets():
    env = os.getenv("ENVIRONMENT").lower()
    dev_mode = os.getenv("DEV_MODE").lower()

    if env == "development" and dev_mode == "true":
        # Dummy buckets for dev mode
        return {
            "dev-bucket-1": "DEV",
            "dev-bucket-2": "DEV",
            "dev-bucket-3": "DEV",
        }
    # Instantiates a client
    storage_client = storage.Client()

    # List the buckets in the project
    buckets = list(storage_client.list_buckets())

    # Create a dictionary with bucket names as keys and their regions as values
    bucket_info = {bucket.name: bucket.location for bucket in buckets}

    return bucket_info


def get_project_resource_role_users(role):
    from google.auth import default
    from googleapiclient import discovery

    # Create IAM client

    project_id = os.environ.get("GOOGLE_STORAGE_PROJECT_ID")
    # Create a credentials object
    credentials, _ = default()

    # Create a service object for interacting with the Cloud
    # Resource Manager API
    service = discovery.build(
        "cloudresourcemanager", "v1", credentials=credentials
    )

    # Retrieve the IAM policy for the project
    policy = service.projects().getIamPolicy(resource=project_id).execute()

    bindings_for_role = [
        binding
        for binding in policy["bindings"]
        if binding["role"].endswith(role)
    ]
    members = bindings_for_role[0]["members"]
    emails = [member.split(":", 1)[1] for member in members]

    return emails


def get_bucket_role_users(bucket_name, role):
    from google.auth import default

    # Authenticate with Google Cloud
    credentials, _ = default()

    # Create a storage client
    storage_client = storage.Client(credentials=credentials)

    # Retrieve the IAM policy for the bucket
    bucket = storage_client.get_bucket(bucket_name)
    policy = bucket.get_iam_policy()

    # Filter bindings to retrieve only the ones associated with roles that
    # end with the specified string
    bindings_for_role = [
        binding
        for binding in policy.bindings
        if binding["role"].endswith(role)
    ]

    # Extract member emails
    emails = []
    for binding in bindings_for_role:
        for member in binding["members"]:
            # Member strings might have prefix, so we need to split to get the
            # email part
            email = member.split(":", 1)[
                -1
            ]  # Split only once to avoid issues with colons in email addresses
            emails.append(email)

    return emails


def delete_bucket_folder(folder_name, bucket_name=None):
    # Configure Google Cloud Storage
    if bucket_name is None:
        bucket_name = os.environ.get("GOOGLE_STORAGE_BUCKET_NAME")

    bucket_name = bucket_name.lower()
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    blobs = bucket.list_blobs(
        prefix=folder_name
    )  # List blobs within the folder

    for blob in blobs:
        blob.delete()

    logger.info(
        f"Folder '{folder_name}' and its contents "
        f"deleted successfully from bucket '{bucket_name}'."
    )


# When we try to import the SequencingFileUploaded class,
# we get a cyclic import
# So we update the db directly
# TODO. See if/how we can get rid of this and update include the class
def update_sequencer_file_progress(sequencer_file_id, progress):
    logger.info(
        "in update_sequencer_file_progress with sequencer_file_id "
        + str(sequencer_file_id)
        + " and progress "
        + str(progress)
    )
    with session_scope() as session:

        # Fetch the existing record
        sequencer_file_db = (
            session.query(SequencingFilesUploadedTable)
            .filter_by(id=sequencer_file_id)
            .first()
        )

        if not sequencer_file_db:
            return None

        sequencer_file_db.bucket_upload_progress = progress


# Quite similar to bucket_upload_folder but accomodating for a different data
# model in version 2 of the application.
# To keep things simple, we are redoing the function with different parameters
# the original function can be removed when version1 will be out of commision
def bucket_upload_folder_v2(folder_path, destination_upload_directory, bucket):
    for root, _, files in os.walk(folder_path):
        for file_name in files:
            file_path = os.path.join(root, file_name)
            destination_blob_name = os.path.relpath(file_path, folder_path)
            bucket_chunked_upload_v2(
                local_file_path=file_path,
                destination_upload_directory=destination_upload_directory,
                destination_blob_name=destination_blob_name,
                sequencer_file_id=None,
                bucket_name=bucket,
                known_md5=None,
            )
            logger.info("Uploaded file " + file_path)


def init_bucket_upload_folder_v2(
    folder_path, destination_upload_directory, bucket
):
    from tasks import bucket_upload_folder_v2_async

    try:
        result = bucket_upload_folder_v2_async.delay(
            folder_path, destination_upload_directory, bucket
        )
        logger.info(
            f"Celery bucket_upload_folder_v2_async task "
            f"called successfully! Task ID: {result.id}"
        )
    except Exception as e:
        logger.error(
            "This is an error message from helpers/bucket.py "
            " while trying to bucket_upload_folder_v2_async"
        )
        logger.error(e)

    return {"msg": "Process initiated"}


# Quite similar to bucket_chunked_upload but accomodating for a different data
# model in version 2 of the application.
# To keep things simple, we are redoing the function with different parameters
# the original function has been removed when version1 went out of commision
def bucket_chunked_upload_v2(
    local_file_path,
    destination_upload_directory,
    destination_blob_name,
    sequencer_file_id,
    bucket_name,
    known_md5,
):

    # Configure Google Cloud Storage
    if bucket_name is None:
        bucket_name = os.environ.get("GOOGLE_STORAGE_BUCKET_NAME")

    bucket_name = bucket_name.lower()

    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    total_size = os.path.getsize(local_file_path)

    # If the file is smaller than 30 MB, upload it directly
    if total_size <= 30 * 1024 * 1024:
        if destination_upload_directory:
            blob = bucket.blob(
                f"{destination_upload_directory}/{destination_blob_name}"
            )
        else:
            blob = bucket.blob(f"{destination_blob_name}")
        blob.upload_from_filename(local_file_path)

        # Verify MD5 checksum
        blob_md5 = blob.md5_hash

        if known_md5:
            # Convert known_md5 from hex to base64
            known_md5_base64 = base64.b64encode(
                bytes.fromhex(known_md5)
            ).decode("utf-8")

            if blob_md5:
                # Compare base64-encoded MD5 checksums
                if known_md5_base64 == blob_md5:
                    if sequencer_file_id:
                        update_sequencer_file_progress(sequencer_file_id, 100)
                else:
                    raise ValueError("MD5 checksum does not match!")

        return True

    # If the file is between 30 MB and 700 MB, do chunks of 30 MB each
    if 30 * 1024 * 1024 < total_size <= 700 * 1024 * 1024:
        chunk_size = 30 * 1024 * 1024

    # If the file is larger than 700 MB, separate it into 32 chunks
    else:
        chunk_size = total_size // 30

    chunk_num = 0
    chunks = []

    with open(local_file_path, "rb") as file:
        while True:
            data = file.read(chunk_size)
            if not data:
                break

            if destination_upload_directory:
                temp_blob = bucket.blob(
                    f"{destination_upload_directory}/"
                    f"{destination_blob_name}.part{chunk_num}"
                )
            else:
                temp_blob = bucket.blob(
                    f"{destination_blob_name}.part{chunk_num}"
                )
            temp_blob.upload_from_string(
                data, content_type="application/octet-stream"
            )
            chunks.append(temp_blob)
            chunk_num += 1

            if sequencer_file_id:
                update_sequencer_file_progress(
                    sequencer_file_id, (file.tell() / total_size) * 100
                )
            print(f"Bytes uploaded: {file.tell()} / {total_size}", flush=True)

        if destination_upload_directory:
            blob = bucket.blob(
                f"{destination_upload_directory}/{destination_blob_name}"
            )
        else:
            blob = bucket.blob(f"{destination_blob_name}")
        blob.compose(chunks)

        for temp_blob in chunks:
            temp_blob.delete()

        if known_md5:
            # Verify MD5 checksum
            blob_md5 = blob.md5_hash
            # Convert known_md5 from hex to base64
            known_md5_base64 = base64.b64encode(
                bytes.fromhex(known_md5)
            ).decode("utf-8")
            if blob_md5:
                if known_md5_base64 == blob_md5:
                    if sequencer_file_id:
                        update_sequencer_file_progress(sequencer_file_id, 100)
                else:
                    raise ValueError("MD5 checksum does not match!")

        return True


def init_bucket_chunked_upload_v2(
    local_file_path,
    destination_upload_directory,
    destination_blob_name,
    sequencer_file_id,
    bucket_name,
    known_md5,
):

    from tasks import bucket_chunked_upload_v2_async

    try:
        result = bucket_chunked_upload_v2_async.delay(
            local_file_path,
            destination_upload_directory,
            destination_blob_name,
            sequencer_file_id,
            bucket_name,
            known_md5,
        )
        logger.info(
            f"Celery bucket_chunked_upload_v2_async"
            f" task called successfully! "
            f"Task ID: {result.id}. sequencer_file_id: {sequencer_file_id}"
        )
        # task_id = result.id
        # upload.update_fastqc_process_id(process_id, task_id)
    except Exception as e:
        logger.error(
            "This is an error message from helpers/bucket.py "
            "while trying to bucket_chunked_upload_v2_async"
        )
        logger.error(e)

    return {"msg": "Process initiated"}


def count_fastq_gz_files_in_buckets():
    # Instantiate a client
    storage_client = storage.Client()

    # List the buckets in the project
    buckets = list(storage_client.list_buckets())

    result = []  # This will hold the results

    # Iterate over each bucket
    for bucket in buckets:
        bucket_name = bucket.name

        logger.info(
            f"Checking bucket: {bucket_name}"
        )  # Log which bucket is being checked

        # List all blobs in the bucket
        all_blobs = storage_client.list_blobs(bucket_name)

        # Dictionary to hold counts by prefix
        counts_by_prefix = {}

        # Iterate over each blob
        for blob in all_blobs:
            # Check if the blob ends with .fastq.gz
            if blob.name.endswith(".fastq.gz"):
                # Extract the prefix (first-level directory)
                prefix = "/".join(
                    blob.name.split("/")[:-1]
                )  # Get everything before the last slash

                # Initialize count for the prefix if not already present
                if prefix not in counts_by_prefix:
                    counts_by_prefix[prefix] = 0

                # Increment the count for this prefix
                counts_by_prefix[prefix] += 1

                logger.info(
                    f"Found blob: {blob.name} in prefix: {prefix}"
                )  # Log each found blob

        # Add results to the final result list
        for prefix, count in counts_by_prefix.items():
            result.append(
                [bucket_name, prefix, count]
            )  # Append bucket, prefix, and count

    logger.info(f"Final results: {result}")  # Log final results
    return result


def check_file_exists_in_bucket(
    local_file_path,
    destination_upload_directory,
    destination_blob_name,
    bucket_name,
):
    # Configure Google Cloud Storage
    if bucket_name is None:
        bucket_name = os.environ.get("GOOGLE_STORAGE_BUCKET_NAME")

    bucket_name = bucket_name.lower()

    try:
        # Initialize the storage client and get the bucket
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)

        # Construct the full blob name
        blob_name = os.path.join(
            destination_upload_directory, destination_blob_name
        )

        # Check if the blob exists in the bucket
        blob = bucket.blob(blob_name)
        return blob.exists()

    except (Forbidden, NotFound):
        # Return False if access is denied or
        # if the bucket/object does not exist
        return False


def download_file_from_bucket(bucket_name, blob_path, local_file_path):
    """
    Downloads a single file from a Google Cloud Storage bucket to a local path.

    Args:
        bucket_name (str): The name of the Google Cloud Storage bucket.
        blob_path (str): The full path of the blob in the bucket (e.g., 'directory/filename.txt').
        local_file_path (str): The full local path where the file should be saved.

    Returns:
        bool: True if the file was successfully downloaded, False otherwise.
    """
    try:
        storage_client = storage.Client()
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.blob(blob_path)

        # Ensure the local directory exists
        os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

        blob.download_to_filename(local_file_path)
        logger.info(
            f"Successfully downloaded '{blob_path}' from bucket '{bucket_name}' to '{local_file_path}'"
        )
        return True
    except Exception as e:
        logger.error(
            f"Error downloading '{blob_path}' from bucket '{bucket_name}' to '{local_file_path}': {e}"
        )
        return False


def init_download_file_from_bucket(bucket_name, blob_path, local_file_path):
    from tasks import download_file_from_bucket_async

    try:
        result = download_file_from_bucket_async.delay(
            bucket_name, blob_path, local_file_path
        )
        logger.info(
            f"Celery download_file_from_bucket_async task "
            f"called successfully! Task ID: {result.id}"
        )
    except Exception as e:
        logger.error(
            "This is an error message from helpers/bucket.py "
            " while trying to bucket_upload_folder_v2_async"
        )
        logger.error(e)

    return {"msg": "Process initiated"}
