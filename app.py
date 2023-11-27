import os
import sys
import secrets
import math
import json
from pathlib import Path

from flask import Flask, render_template, request
from werkzeug.utils import secure_filename

#library to track bytes uploaded to google cloud:
from tqdm import tqdm

# Library about google cloud storage
from google.cloud import storage

app = Flask(__name__)
foo = secrets.token_urlsafe(16)
app.secret_key = foo
print (os.environ.get('GOOGLE_STORAGE_BUCKET_NAME'))
print (os.environ.get('GOOGLE_APPLICATION_CREDENTIALS'))
# Configure Google Cloud Storage
bucket_name = os.environ.get('GOOGLE_STORAGE_BUCKET_NAME')
project_id = os.environ.get('GOOGLE_STORAGE_PROJECT_ID')
bucket_location = os.environ.get('GOOGLE_STORAGE_BUCKET_LOCATION')

def chunked_upload(local_file_path, destination_blob_name, file_uuid):
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)

    chunk_size = 5 * 1024 * 1024  # 5 MB chunk size (adjust as needed)

    # Create a blob object with the desired name
    blob = bucket.blob(f'uploads/{destination_blob_name}')

    # Start a resumable upload session
    with open(local_file_path, "rb") as file:
        blob.chunk_size = chunk_size
        blob.upload_from_file(file)

    print(f"File {local_file_path} uploaded to {destination_blob_name} in {bucket_name} bucket.")

@app.get("/")
def index():
    return render_template("index.html")

@app.post("/upload")
def upload_chunk():
    file = request.files["file"]
    file_uuid = request.form["dzuuid"]
    # Generate a unique filename to avoid overwriting using 8 chars of uuid before filename.
    filename = f"{file_uuid[:8]}_{secure_filename(file.filename)}"
    save_path = Path("uploads", filename)
    current_chunk = int(request.form["dzchunkindex"])

    try:
        with open(save_path, "ab") as f:
            f.seek(int(request.form["dzchunkbyteoffset"]))
            f.write(file.stream.read())
    except OSError:
        return "Error saving file.", 500

    total_chunks = int(request.form["dztotalchunkcount"])

    if current_chunk + 1 == total_chunks:
        # This was the last chunk, the file should be complete and the size we expect
        if os.path.getsize(save_path) != int(request.form["dztotalfilesize"]):
            return "Size mismatch.", 500
        else:
            chunked_upload(save_path, filename, file_uuid)

    return "Chunk upload successful.", 200

if __name__ == '__main__':
    server_port = os.environ.get('PORT', '8080')
    #serve(app, host="0.0.0.0", port=server_port)
    app.run(debug=True, port=server_port, host='0.0.0.0')
