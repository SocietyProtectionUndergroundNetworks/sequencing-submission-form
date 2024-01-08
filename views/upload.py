import datetime
import random
import string
import os
import json
import logging
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, jsonify, send_from_directory
from flask import current_app as app  # Import the 'app' instance
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from helpers.csv import validate_csv_column_names
from helpers.bucket_upload import bucket_chunked_upload, get_progress_db
from helpers.fastqc import get_fastqc_progress
from helpers.file_renaming import extract_uploaded_gzip, rename_files, calculate_md5

from models.upload import Upload


# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


upload_bp = Blueprint('upload', __name__)

@upload_bp.route("/")
def index():
    if current_user.is_authenticated:
        return render_template("index.html", name=current_user.name, email=current_user.email)
    else:
        return '<a class="button" href="/login">Google Login</a>'

@upload_bp.route('/form_resume')
@login_required
def upload_form_resume():
    upload = Upload.get_latest_unfinished_process(current_user.id)

    if upload is None:
        # Handle the case where no data is returned
        print("No data found.")
        return render_template("form.html", msg='We could not find an unfinished process to resume')
    else:

        logger.info('upload id ' + str(upload.id))
        matching_files_filesystem = []
        matching_files_dict = []
        nr_files = 0
        if (upload.gz_unziped):

            uploads_folder = upload.uploads_folder
            extract_directory = Path("processing", uploads_folder)

            # count the files ending with fastq.gz
            file_names = os.listdir(extract_directory)
            matching_files_filesystem = [filename for filename in file_names if filename.endswith('.fastq.gz')]
            nr_files = 0
            if (matching_files_filesystem):
                nr_files=len(matching_files_filesystem)

            matching_files_dict = json.loads(upload.files_json)

        return render_template(
                                "form.html",
                                process_id=upload.id,
                                csv_uploaded=upload.csv_uploaded,
                                csv_filename=upload.csv_filename,
                                gz_uploaded=upload.gz_uploaded,
                                gz_filename=upload.gz_filename,
                                gz_sent_to_bucket=upload.gz_sent_to_bucket,
                                gz_unziped=upload.gz_unziped,
                                files_renamed=upload.files_renamed,
                                nr_files=nr_files,
                                matching_files=matching_files_filesystem,
                                matching_files_db=matching_files_dict,
                                fastqc_run=upload.fastqc_run
                                )

@upload_bp.route('/form')
@login_required
def upload_form():
    # app.logger.info('form requested')
    return render_template("form.html")

@upload_bp.route('/uploadcsv', methods=['POST'])
@login_required
def upload_csv():
    # Handle CSV file uploads separately
    file = request.files.get('file')
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    # lets create a directory only for this process.
    uploads_folder = datetime.datetime.now().strftime("%Y%m%d") + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

    # Process the CSV file (e.g., save it or perform specific operations)
    filename = secure_filename(file.filename)

    path = Path("uploads", uploads_folder)
    path.mkdir(parents=True, exist_ok=True)
    save_path = path / filename
    #save_path = Path("uploads", filename)
    file.save(save_path)  # Save the CSV file to a specific location

    structure_compare = validate_csv_column_names(save_path)
    if structure_compare is True:
        process_id = Upload.create(user_id=current_user.id, csv_filename=filename, uploads_folder=uploads_folder)
        bucket_chunked_upload(save_path, uploads_folder, filename, process_id, 'csv_file')
        # app.logger.info('new_id is ' + str(new_id))
        return jsonify({"msg": "CSV file uploaded successfully. Fields match", "process_id": process_id}), 200
    else:
        return jsonify({"error": "CSV file fields don't match expected structure", "mismatch": structure_compare}), 400


@upload_bp.route('/uploadprogress')
@login_required
def api_progress():
    process_id = request.args.get('process_id')
    progress = get_progress_db(process_id, 'gz_raw')
    return {
        "progress": progress
    }

@upload_bp.route('/upload', methods=['POST'])
def handle_upload():
    file = request.files.get('file')
    if file:
        process_id = request.args.get('process_id')
        upload = Upload.get(process_id)
        uploads_folder = upload.uploads_folder

        # Extract Resumable.js headers
        resumable_chunk_number = request.args.get('resumableChunkNumber')
        resumable_total_chunks = request.args.get('resumableTotalChunks')
        resumable_chunk_size = request.args.get('resumableChunkSize')
        resumable_total_size = request.args.get('resumableTotalSize')
        expected_md5 = request.args.get('md5')

        # logger.info('resumable_chunk_number ' + str(resumable_chunk_number))
        # logger.info('resumable_total_chunks ' + str(resumable_total_chunks))
        # logger.info('resumable_chunk_size ' + str(resumable_chunk_size))
        # logger.info('resumable_total_size ' + str(resumable_total_size))

        # Handle file chunks or combine chunks into a complete file
        chunk_number = int(resumable_chunk_number) if resumable_chunk_number else 1
        total_chunks = int(resumable_total_chunks) if resumable_total_chunks else 1

        # Save or process the chunk (for demonstration, just save it)
        save_path = f'uploads/{uploads_folder}/{file.filename}.part{chunk_number}'
        file.save(save_path)

        # Check if all chunks have been uploaded
        if chunk_number == total_chunks:
            # Perform actions for the complete file
            # Combine the chunks, save to final location, etc.
            final_file_path = f'uploads/{uploads_folder}/{file.filename}'
            with open(final_file_path, 'ab') as final_file:
                for i in range(1, total_chunks + 1):
                    chunk_path = f'uploads/{uploads_folder}/{file.filename}.part{i}'
                    with open(chunk_path, 'rb') as chunk_file:
                        final_file.write(chunk_file.read())
                    # Delete individual chunks after combining, if needed
                    os.remove(chunk_path)

            # Perform MD5 hash check
            expected_md5 = request.args.get('md5')  # Get the expected MD5 hash from the request
            actual_md5 = calculate_md5(final_file_path)
            # logger.info('expected_md5 ' + str(expected_md5))
            # logger.info('actual_md5 ' + str(actual_md5))

            # Compare MD5 hashes
            if expected_md5 == actual_md5:
                # MD5 hashes match, file integrity verified
                Upload.mark_field_as_true(process_id, 'gz_uploaded')
                Upload.update_gz_filename(process_id, file.filename)
                return jsonify({'message': 'File upload complete and verified'})

            # MD5 hashes don't match, handle accordingly (e.g., delete the incomplete file, return an error)
            # os.remove(final_file_path)
            return jsonify({'message': 'MD5 hash verification failed'}), 400


        return jsonify({'message': f'Chunk {chunk_number} uploaded'}), 200

    return jsonify({'message': 'No file received'}), 400

@upload_bp.route('/upload', methods=['GET'])
def check_chunk():
    process_id = request.args.get('process_id')
    chunk_number = request.args.get('resumableChunkNumber')

    resumable_filename = request.args.get('resumableFilename')
    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder
    # logger.info('checking if chunk exists. Chunk nr: ' + str(chunk_number))

    chunk_path = f'uploads/{uploads_folder}/{resumable_filename}.part{chunk_number}'

    logger.info('chunk_path: ' + str(chunk_path))
    if os.path.exists(chunk_path):
        # logger.info('chunk exists')
        return '', 200  # Chunk already uploaded, return 200
    # logger.info('chunk doesnt exist ')
    return '', 204  # Chunk not found, return 204

@upload_bp.route('/sendrawtostorage', methods=['POST'])
@login_required
def send_raw_to_storage():
    #app.logger.info('raw to storage starts')

    # in order to continue on the same process, lets get the id from the form
    process_id = request.form["process_id"]

    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder
    path = Path("uploads", uploads_folder)
    filename = upload.gz_filename
    save_path = path / filename
    raw_uploaded = bucket_chunked_upload(save_path, uploads_folder, filename, process_id, 'gz_raw')
    #Upload.mark_field_as_true(process_id, 'gz_sent_to_bucket')
    if (raw_uploaded):
        Upload.mark_field_as_true(process_id, 'gz_sent_to_bucket')
        return jsonify({"msg": "Raw to storage was successfully transfered."}), 200

    return jsonify({"error": "Something went wrong."}), 400

@upload_bp.route('/unzipraw', methods=['POST'])
@login_required
def unzip_raw():
    app.logger.info('unzip file starts')

    # in order to continue on the same process, lets get the id from the form
    process_id = request.form["process_id"]

    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder
    path = Path("uploads", uploads_folder)
    filename = upload.gz_filename
    save_path = path / filename

    extract_directory = Path("processing", uploads_folder)
    gunzip_result = extract_uploaded_gzip(save_path, extract_directory)

    if (gunzip_result):
        Upload.mark_field_as_true(process_id, 'gz_unziped')

        # count the files ending with fastq.gz
        file_names = os.listdir(extract_directory)
        matching_files = [filename for filename in file_names if filename.endswith('.fastq.gz')]
        nr_files = 0
        if (matching_files):
            nr_files=len(matching_files)
            # Convert the list to a dictionary with empty parameters
            matching_files_dict = {filename: {'new_filename': '', 'fastqc': ''} for filename in matching_files}
            Upload.update_files_json(process_id, matching_files_dict)

        return jsonify({"msg": "Raw unzipped successfully.", "nr_files": nr_files, "matching_files":matching_files}), 200

    return jsonify({"error": "Something went wrong."}), 400


@upload_bp.route('/renamefiles', methods=['POST'])
@login_required
def renamefiles():
    app.logger.info('renaming files starts')

    # in order to continue on the same process, lets get the id from the form
    process_id = request.form["process_id"]

    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder
    path = Path("uploads", uploads_folder)
    csv_filepath = path / upload.csv_filename
    filename = upload.gz_filename
    save_path = path / filename

    extract_directory = Path("processing", uploads_folder)
    rename_results, not_found, files_dict = rename_files(csv_filepath, extract_directory, upload.files_json)
    Upload.update_files_json(process_id, files_dict)

    to_render = '<br>'.join(rename_results)

    if rename_results:
        Upload.mark_field_as_true(process_id, 'files_renamed')
        return jsonify({"msg": "Raw unzipped successfully.", "results":rename_results, "not_found":not_found, "files_dict": files_dict}), 200
    return jsonify({"error": "Something went wrong."}), 400


@upload_bp.route('/fastqcfiles', methods=['POST'])
@login_required
def fastqcfiles():
    app.logger.info('fastqc of files starts')

    # in order to continue on the same process, lets get the id from the form
    process_id = request.form["process_id"]

    upload = Upload.get(process_id)
    app.logger.info(upload.extract_directory)
    from tasks import fastqc_multiqc_files_async
    try:
        result = fastqc_multiqc_files_async.delay(str(upload.extract_directory), process_id)
        logger.info(f"Celery multiqc task called successfully! Task ID: {result.id}")
        task_id = result.id
        upload.update_fastqc_process_id(process_id, task_id)
    except Exception as e:
        logger.error("This is an error message from upload.py")
        logger.error(e)


    return 'ok', 200

@upload_bp.route('/fastqcprogress')
@login_required
def fastqc_progress():
    process_id = request.args.get('process_id')
    to_return = get_fastqc_progress(process_id)
    return to_return

@upload_bp.route('/multiqc', methods=['GET'])
@login_required
def show_multiqc_report():
    process_id = request.args.get('process_id')
    multiqc_progress = get_fastqc_progress(process_id)
    logger.info(multiqc_progress)
    if multiqc_progress['multiqc_report_exists']:
        return send_from_directory(multiqc_progress['multiqc_report_path'], 'multiqc_report.html')

    return to_return


@upload_bp.route('/user_uploads', methods=['GET'])
@login_required
def user_uploads():
    user_id = request.args.get('user_id')
    user_uploads = Upload.get_uploads_by_user(user_id)
    return render_template('user_uploads.html', user_uploads=user_uploads)


@upload_bp.route('/test2', methods=['GET'])
def check_process_id1():
    process_id = 4
    to_return = get_fastqc_progress(process_id)
    return to_return
