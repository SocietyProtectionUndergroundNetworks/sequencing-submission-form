import os
import logging
import datetime
import zipfile
import re
import shutil
import base64
import hashlib

# Library about google cloud storage
from google.cloud import storage
from models.bucket import Bucket
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


def get_bucket_size_excluding_archive(bucket_name):
    # Initialize Google Cloud Storage client
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # Get list of all blobs in the bucket
    blob_list = bucket.list_blobs()

    # Calculate total size excluding blobs in the "archive" folder
    total_size = sum(
        blob.size for blob in blob_list if not blob.name.startswith("archive/")
    )
    return total_size


def download_bucket_contents(bucket_name):
    # Initialize Google Cloud Storage client
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # Get list of files in the bucket
    blob_list = bucket.list_blobs()

    # Calculate total number of files for progress tracking
    total_files = sum(1 for _ in blob_list)

    # Initialize progress counters
    downloaded_files = 0
    zip_progress = 0

    destination_folder = os.path.join("temp", bucket_name)
    os.makedirs(destination_folder, exist_ok=True)

    # Create a zip file
    current_datetime = datetime.datetime.now().strftime("%Y%m%d-%H%M")
    zip_filename = f"{current_datetime}-{bucket_name}.zip"
    zip_filepath = os.path.join("temp", zip_filename)

    with zipfile.ZipFile(zip_filepath, "w") as zipf:
        # Iterate through files in the bucket
        for blob in bucket.list_blobs():
            # Exclude files in the "archive" folder
            if (not blob.name.startswith("archive/")) and (
                not blob.name.endswith("/")
            ):
                # Update progress for downloaded files
                downloaded_files += 1
                download_progress = (
                    downloaded_files / total_files * 60
                )  # 60% allocated for downloading

                Bucket.update_progress(bucket_name, download_progress)

                # Create directory if it does not exist
                local_path = os.path.join(
                    destination_folder, os.path.dirname(blob.name)
                )
                os.makedirs(local_path, exist_ok=True)
                # Download file to local computer
                new_file_path = os.path.join(destination_folder, blob.name)
                blob.download_to_filename(new_file_path)
                # Add file to zip archive
                zipf.write(
                    os.path.join(destination_folder, blob.name),
                    arcname=blob.name,
                )

        # Update progress for zipping
        zip_progress = 10  # 10% allocated for zipping

        # Update database with zip progress
        Bucket.update_progress(bucket_name, 60 + zip_progress)

    # Upload zip file to the "archive" folder
    archive_blob = bucket.blob(f"archive/{zip_filename}")
    archive_blob.upload_from_filename(zip_filepath)

    # Update progress for uploading
    Bucket.update_progress(bucket_name, 100)
    Bucket.update_archive_filename(bucket_name, zip_filename)

    # Delete the local zip file after uploading
    os.remove(zip_filepath)

    # Delete all files from the destination folder
    shutil.rmtree(destination_folder)


def check_archive_file(bucket_name):
    # Initialize Google Cloud Storage client
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # Get list of blob names in the "archive" directory
    blob_names = [blob.name for blob in bucket.list_blobs(prefix="archive/")]

    # Check if any blob matches the expected filename format
    for blob_name in blob_names:
        match = re.match(r"^archive/(\d{8}-\d{4}-[\w-]+\.zip)$", blob_name)
        if match:
            return match.group(1)

    # If no matching file found, return False
    return False


def make_file_accessible(bucket_name, file_name):
    # Initialize a client
    storage_client = storage.Client()

    # Get the bucket and file objects
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(file_name)

    # Generate the signed URL
    url = blob.generate_signed_url(
        version="v4",
        expiration=datetime.timedelta(hours=1),  # Expiration time for the URL
        method="GET",  # HTTP method allowed (e.g., GET, PUT, POST, etc.)
    )
    return url


def delete_buckets_archive_files():
    # Initialize Google Cloud Storage client
    storage_client = storage.Client()

    # List the buckets in the project
    buckets = list(storage_client.list_buckets())

    # Create a dictionary with bucket names as keys and their regions as values
    # bucket_info = {bucket.name: bucket.location for bucket in buckets}
    current_datetime = datetime.datetime.now(datetime.timezone.utc)

    for bucket in buckets:

        # bucket = client.bucket(bucket_name)
        # logger.info("-Bucket we are checking: " + bucket.name)

        # Iterate through blobs in the "archive" folder
        for blob in bucket.list_blobs(prefix="archive/"):

            creation_time = blob.time_created
            logger.info(creation_time)

            # Calculate age of the blob in hours
            age_seconds = (current_datetime - creation_time).total_seconds()
            # If the blob is older than 1 days, delete it
            logger.info("--age_seconds is ")
            logger.info(age_seconds)
            if age_seconds > 86400:
                blob.delete()

                db_bucket = Bucket.get(bucket.name)
                logger.info("---Blob name: " + blob.name)
                logger.info(
                    "---db_bucket archive_file : " + db_bucket.archive_file
                )
                if blob.name.endswith(db_bucket.archive_file):
                    logger.info("----It ends with it!")
                    Bucket.update_archive_filename(bucket.name, None)
                    Bucket.update_progress(bucket.name, None)

                logger.info(
                    f"Deleted blob '{blob.name}' from the 'archive' folder."
                )


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
# the original function can be removed when version1 will be out of commision
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
