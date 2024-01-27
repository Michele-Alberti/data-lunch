import logging
from google.cloud import storage

log = logging.getLogger(__name__)


def get_gcloud_bucket_list(project: str):
    # Create storage client
    storage_client = storage.Client(project=project)

    # Return bucket
    buckets = list(storage_client.list_buckets())

    return buckets


def upload_to_gcloud(
    source_file_name: str,
    destination_blob_name: str,
    bucket_name: str,
    project: str,
):
    # Create storage client
    storage_client = storage.Client(project=project)

    try:
        # Get bucket
        bucket = storage_client.bucket(bucket_name)
        # Create blob
        blob = bucket.blob(destination_blob_name)
        # Upload
        blob.upload_from_filename(source_file_name)
        log.info(
            f"file '{source_file_name}' uploaded to bucket '{bucket_name}' successfully"
        )
    except Exception as e:
        log.warning("google storage upload exception\n\t" + str(e))


def upload_to_gcloud_from_string(
    source_string: str,
    destination_blob_name: str,
    bucket_name: str,
    project: str,
):
    # Create storage client
    storage_client = storage.Client(project=project)

    try:
        # Get bucket
        bucket = storage_client.bucket(bucket_name)
        # Create blob
        blob = bucket.blob(destination_blob_name)
        # Upload
        blob.upload_from_string(source_string)
        log.info(
            f"file uploaded from string to bucket '{bucket_name}' at '{destination_blob_name}' successfully"
        )
    except Exception as e:
        log.warning("google storage upload exception\n\t" + str(e))


def download_from_gcloud(
    source_blob_name: str,
    destination_file_name: str,
    bucket_name: str,
    project: str,
):
    # Create storage client
    storage_client = storage.Client(project=project)

    try:
        # Get bucket
        bucket = storage_client.bucket(bucket_name)
        # Create blob
        blob = bucket.blob(source_blob_name)
        # Download
        blob.download_to_filename(destination_file_name)
        log.info(
            f"file '{source_blob_name}' downloaded to file '{destination_file_name}' successfully"
        )
    except Exception as e:
        log.warning("google storage download exception\n\t" + str(e))


def download_from_gcloud_as_bytes(
    source_blob_name: str,
    bucket_name: str,
    project: str,
):
    # Create storage client
    storage_client = storage.Client(project=project)

    try:
        # Get bucket
        bucket = storage_client.bucket(bucket_name)
        # Create blob
        blob = bucket.blob(source_blob_name)
        # Download
        bytes_object = blob.download_as_bytes()
        log.info(
            f"file '{source_blob_name}' downloaded to object successfully"
        )
    except Exception as e:
        log.warning("google storage download exception\n\t" + str(e))

    return bytes_object
