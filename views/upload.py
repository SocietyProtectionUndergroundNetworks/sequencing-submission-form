import datetime
import random
import string
import os
import re
import json
import logging
import psutil
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, jsonify, send_from_directory, redirect, url_for, send_file
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from helpers.csv import validate_csv, get_csv_data
from helpers.bucket import (
    bucket_chunked_upload,
    get_progress_db_bucket,
    init_send_raw_to_storage,
    get_renamed_files_to_storage_progress,
    init_upload_final_files_to_storage,
    get_bucket_size_excluding_archive,
    check_archive_file
)

from helpers.unzip import get_progress_db_unzip, unzip_raw, unzip_raw_file
from helpers.fastqc import get_fastqc_progress, init_fastqc_multiqc_files, get_multiqc_report
from helpers.file_renaming import calculate_md5, rename_all_files

from models.upload import Upload


# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


upload_bp = Blueprint('upload', __name__)

# Custom approved_required decorator
def approved_required(view_func):
    def decorated_approved_view(*args, **kwargs):
        if not current_user.is_authenticated:
            # Redirect unauthenticated users to the login page
            return redirect(url_for('user.login'))  # Adjust 'login' to your actual login route
        elif not current_user.approved:
            # Redirect non-approved users to some unauthorized page
            return redirect(url_for('user.only_approved'))
        return view_func(*args, **kwargs)
    return decorated_approved_view

# Custom admin_required decorator
def admin_required(view_func):
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            # Redirect unauthenticated users to the login page
            return redirect(url_for('user.login'))  # Adjust 'login' to your actual login route
        elif not current_user.admin:
            # Redirect non-admin users to some unauthorized page
            return redirect(url_for('user.only_admins'))
        return view_func(*args, **kwargs)
    return decorated_view

def recreate_matching_files(process_id):

    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder
    extract_directory = Path("processing", uploads_folder)

    # count the files ending with fastq.gz
    file_names = os.listdir(extract_directory)
    matching_files = [filename for filename in file_names if (filename.endswith('.fastq.gz') or filename.endswith('.fastq'))]
    nr_files = 0
    if (matching_files):
        nr_files=len(matching_files)
        # Convert the list to a dictionary with empty parameters
        matching_files_dict = {filename: {'new_filename': '', 'fastqc': ''} for filename in matching_files}

        # Update for non standard sequencing data. Find out the bucket and folder from here, because we skip the renaming step
        path = Path("uploads", upload.uploads_folder)
        cvs_path = path / upload.csv_filename
        cvs_records = get_csv_data(cvs_path)

        # Iterate over keys in matching_files_dict
        for file_key in matching_files_dict.keys():

            # Find matching row in CSV data
            for row in cvs_records.values():
                sequencer_identifier = row['sequencer_id'].split('_S')[0]
                if file_key.startswith(sequencer_identifier):
                    # Assign project and region to the matching file
                    matching_files_dict[file_key]['bucket'] = row['project']
                    matching_files_dict[file_key]['folder'] = row['region']
                    break  # Break the loop once a match is found
                    logger.info('Found one file_key: ' + file_key + ' for project ' + row['project'])
        logger.info('we will now update the files json')
        Upload.update_files_json(process_id, matching_files_dict)
    return nr_files

@upload_bp.route("/")
def index():
    if current_user.is_authenticated:
        if not current_user.approved:
            # Redirect non-approved users to some unauthorized page
            return redirect(url_for('user.only_approved'))
        upload = Upload.get_latest_unfinished_process(current_user.id)
        gz_filedata = {}

        if upload is None:
            # Handle the case where no data is returned
            print("No data found.")
            if not current_user.admin:
                return render_template("form.html", msg='We could not find an unfinished process to resume', is_admin=current_user.admin)
        else:
            if (upload.csv_uploaded):
                gz_filedata = Upload.get_gz_filedata(upload.id)

        sys_info = {}
        if current_user.admin:
            disk_usage = psutil.disk_usage('/app')
            sys_info['disk_used_percent']=disk_usage.percent

        return render_template("index.html",
                                name=current_user.name,
                                user_id=current_user.id,
                                email=current_user.email,
                                gz_filedata=gz_filedata,
                                sys_info=sys_info)
    else:
        return render_template('public_homepage.html')

@upload_bp.route('/privacy_and_terms', endpoint='privacy_and_terms')
def privacy_and_terms():
    return render_template('privacy_and_terms.html')

@upload_bp.route('/csv_structure', endpoint='csv_structure')
def csv_structure():
    return render_template('csv_structure.html')

@upload_bp.route('/app_instructions', endpoint='app_instructions')
def app_instructions():
    return render_template('app_instructions.html')

@upload_bp.route('/csv_sample', endpoint='csv_sample')
def csv_sample():
    path = Path("static","csv")
    csv_path = path / 'csv_structure.csv'
    filename = 'csv_structure.csv'

    return send_file(csv_path, as_attachment=True)

@upload_bp.route('/download_metadata', endpoint='download_metadata')
@login_required
@approved_required
def download_metadata():
    process_id = request.args.get('process_id',0)

    try:
        process_id = int(process_id)
        if (isinstance(process_id, int) and (process_id !=0)):
            upload = Upload.get(process_id)
            path = Path("uploads", upload.uploads_folder)
            metadata_file_path = path / upload.metadata_filename

            #TODO: check that the user asking for this is either an admin or the owner of the process

            return send_file(metadata_file_path, as_attachment=True)
    except (ValueError, TypeError):
        # Handle the case where process_id is not a valid integer or convertible to an integer
        logger.info('Tried to access download_metadata without a valid process_id')


    return render_template("index.html",
                                name=current_user.name,
                                user_id=current_user.id,
                                email=current_user.email)

@upload_bp.route('/download_csv', endpoint='download_csv')
@login_required
@approved_required
def download_csv():
    process_id = request.args.get('process_id',0)

    try:
        process_id = int(process_id)
        if (isinstance(process_id, int) and (process_id !=0)):
            upload = Upload.get(process_id)
            path = Path("uploads", upload.uploads_folder)
            csv_file_path = path / upload.csv_filename

            #TODO: check that the user asking for this is either an admin or the owner of the process

            return send_file(csv_file_path, as_attachment=True)
    except (ValueError, TypeError):
        # Handle the case where process_id is not a valid integer or convertible to an integer
        logger.info('Tried to access download_csv without a valid process_id')

    return render_template("index.html",
                                name=current_user.name,
                                user_id=current_user.id,
                                email=current_user.email)

@upload_bp.route('/form_resume', endpoint='upload_form_resume')
@login_required
@approved_required
def upload_form_resume():
    default_process_id = 0
    process_id = request.args.get('process_id', default_process_id)
    uploads_folder = ''
    form_reporting = []

    try:
        process_id = int(process_id)
    except (ValueError, TypeError):
        # Handle the case where process_id is not a valid integer or convertible to an integer
        process_id = default_process_id

    if (isinstance(process_id, int) and (process_id !=0)):
        upload = Upload.get(process_id)

    else:
        upload = Upload.get_latest_unfinished_process(current_user.id)
        process_id = upload.id

    if upload is None:
        # Handle the case where no data is returned
        print("No data found.")
        return render_template("form.html", msg='We could not find an unfinished process to resume', is_admin=current_user.admin)
    else:

        logger.info(process_id)

        #TODO: check if the current user is admin or owner of this upload. Else redirect them.
        if (current_user.admin) or (current_user.id == upload.user_id) :
            matching_files_filesystem = []
            matching_files_dict = []
            gz_filedata = {}
            nr_files = 0
            uploads_folder = upload.uploads_folder
            cvs_records = []

            if (upload.csv_uploaded):
                gz_filedata = Upload.get_gz_filedata(upload.id)

                any_unzipped = False

                path = Path("uploads", upload.uploads_folder)
                save_path = path / upload.csv_filename
                cvs_records = get_csv_data(save_path)

                if gz_filedata:
                    for filename, file_data in gz_filedata.items():
                        gz_file_path = os.path.join(path, filename)

                        # Check for inconsistencies.
                        # inconsistency 1: If the final .gz file exists, when it says that it is uncomplete
                        if (file_data['percent_uploaded'] < 100):
                            if os.path.exists(gz_file_path):
                                logger.info('The file ' + filename + ' exists when it shouldnt. Deleting it ')
                                os.remove(gz_file_path)
                                form_reporting.append('The file ' + filename + ' exists when it shouldnt. Deleting it ')

                        # inconsistency 2: If the progress says 100, but the file does not exist!
                        if (file_data['percent_uploaded'] == 100):
                            if not os.path.exists(gz_file_path):
                                logger.info('The file ' + filename + ' doesnt exist when it should. Deleting the gz_record and the parts ')
                                logger.info(file_data)

                                one_filedata = {
                                    'form_filename'         : file_data['form_filename'],
                                    'form_filesize'         : file_data['form_filesize'],
                                    'form_filechunks'       : file_data['form_filechunks'],
                                    'form_fileidentifier'   : file_data['form_fileidentifier'],
                                    'chunk_number_uploaded' : 0,
                                    'percent_uploaded'      : 0,
                                    'expected_md5'          : file_data['expected_md5']
                                }
                                form_reporting.append('The file ' + filename + ' doesnt exist when it should. Deleting the gz_record and the parts ')
                                Upload.update_gz_filedata(process_id, one_filedata)
                                files = os.listdir(path)
                                for file in files:
                                    # Check if the file starts with the filename and ends with '.partX' or '.temp'

                                    if file.startswith(filename) and (file.endswith('.temp') or re.match(rf"{filename}\.part\d+", file)):
                                        # Construct the full file path
                                        file_path = os.path.join(path, file)
                                        # Delete the file
                                        os.remove(file_path)


                        if 'gz_sent_to_bucket_progress' in file_data:
                            if file_data['gz_sent_to_bucket_progress'] == 100:
                                any_unzipped = True

                # get it again, because we may have just changed it
                gz_filedata = Upload.get_gz_filedata(upload.id)

                if (any_unzipped):
                    extract_directory = Path("processing", uploads_folder)

                    if os.path.exists(extract_directory):
                        # count the files ending with fastq.gz
                        file_names = os.listdir(extract_directory)
                        matching_files_filesystem = [filename for filename in file_names if filename.endswith('.fastq.gz')]
                        nr_files = 0
                        if (matching_files_filesystem):
                            nr_files=len(matching_files_filesystem)

                        matching_files_dict = upload.get_files_json()

            return render_template(
                                    "form.html",
                                    process_id=upload.id,
                                    csv_uploaded=upload.csv_uploaded,
                                    csv_filename=upload.csv_filename,
                                    metadata_uploaded=(upload.metadata_filename is not None),
                                    metadata_filename=upload.metadata_filename,
                                    gz_filedata=gz_filedata if gz_filedata else {},
                                    files_renamed=upload.files_renamed,
                                    renaming_skipped=upload.renaming_skipped,
                                    nr_files=nr_files,
                                    matching_files=matching_files_filesystem,
                                    matching_files_db=matching_files_dict,
                                    fastqc_run=upload.fastqc_run,
                                    renamed_sent_to_bucket=upload.renamed_sent_to_bucket,
                                    uploads_folder=uploads_folder,
                                    cvs_records=cvs_records,
                                    sequencing_method=upload.sequencing_method,
                                    form_reporting=form_reporting,
                                    is_admin=current_user.admin
                                    )
        else:
            return redirect(url_for('user.only_admins'))


@upload_bp.route('/form', endpoint='upload_form')
@login_required
@approved_required
def upload_form():
    return render_template("form.html",is_admin=current_user.admin)


@upload_bp.route('/clear_file_upload', methods=['POST'], endpoint='clear_file_upload')
@login_required
@approved_required
def clear_file_upload():
    filename = request.form.get('filename')
    process_id = request.form.get('process_id')
    logger.info(filename)
    logger.info(process_id)
    logger.info(int(process_id))
    process_id = int(process_id)
    if (isinstance(process_id, int) and (process_id !=0)):
        logger.info('here 1')
        upload = Upload.get(process_id)
        path = Path("uploads", upload.uploads_folder)
        if (upload.csv_uploaded):
            logger.info('here 2')

            #find out files to be deleted
            file_names = os.listdir(path)
            matching_files_filesystem = [matchingfilename for matchingfilename in file_names if matchingfilename.startswith(filename)]
            for matching_file in matching_files_filesystem:
                file_to_remove = Path("uploads", upload.uploads_folder, matching_file)
                os.remove(file_to_remove)

            logger.info(matching_files_filesystem)

            gz_filedata = Upload.get_gz_filedata(upload.id)
            logger.info(gz_filedata)
            one_filedata = gz_filedata[filename]
            logger.info(one_filedata)
            one_filedata['percent_uploaded'] = 0;
            one_filedata['chunk_number_uploaded'] = 0;

            Upload.update_gz_filedata(process_id, one_filedata)



    return jsonify({"status": 1})


@upload_bp.route('/uploadmetadata', methods=['POST'], endpoint='upload_metadata')
@login_required
@approved_required
def upload_metadata():
    # Handle metadata file upload separately
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

    process_id = Upload.create(user_id=current_user.id, uploads_folder=uploads_folder, metadata_filename=filename)
    bucket_chunked_upload(save_path, "uploads/" + uploads_folder, filename, process_id, 'metadata_file')
    return jsonify({"msg": "Metadata file uploaded successfully.", "process_id": process_id, "upload_folder": uploads_folder}), 200



@upload_bp.route('/uploadcsv', methods=['POST'], endpoint='upload_csv')
@login_required
@approved_required
def upload_csv():
    # Handle CSV file uploads separately
    file = request.files.get('file')
    sequencing_method = request.form.get('sequencing_method')
    logger.info('The sequencing method is')
    logger.info(sequencing_method)
    if not file:
        return jsonify({"error": "No file uploaded"}), 400

    # Process the CSV file (e.g., save it or perform specific operations)
    filename = secure_filename(file.filename)

    process_id = request.form.get('process_id')
    logger.info('The process_id method is ')
    logger.info(process_id)
    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder
    path = Path("uploads", uploads_folder)
    save_path = path / filename
    #save_path = Path("uploads", filename)
    file.save(save_path)  # Save the CSV file to a specific location

    cvs_results = validate_csv(save_path)
    logger.info(cvs_results)

    if cvs_results is True:
        cvs_records = get_csv_data(save_path)
        matching_files_db = upload.get_files_json()
        Upload.update_csv_filename_and_method(process_id, filename, sequencing_method)
        bucket_chunked_upload(save_path, "uploads/" + uploads_folder, filename, process_id, 'csv_file')
        return jsonify({"msg": "CSV file uploaded successfully. Checks passed", "cvs_records": cvs_records, "matching_files_db": matching_files_db}), 200
    else:
        return jsonify({"error": "CSV file problems: ", "results": cvs_results}), 400

@upload_bp.route('/unzipprogress', endpoint='unzip_progress')
@login_required
@approved_required
def unzip_progress():
    process_id = request.args.get('process_id')
    file_id = request.args.get('file_id')
    progress = get_progress_db_unzip(process_id, file_id)
    gz_filedata = Upload.get_gz_filedata(process_id)

    if (progress==100):
        nr_files = recreate_matching_files(process_id)
        upload = Upload.get(process_id)
        files_dict_db = upload.get_files_json()
        return jsonify({"progress": progress, "msg": "Raw unzipped successfully.", "nr_files": nr_files, "files_dict_db":files_dict_db, 'gz_filedata': gz_filedata}), 200
    else:
        upload = Upload.get(process_id)
        files_dict_db = upload.get_files_json()
    return {
        "progress": progress, 'gz_filedata': gz_filedata, "files_dict_db":files_dict_db
    }


@upload_bp.route('/uploadprogress', endpoint='upload_progress')
@login_required
@approved_required
def upload_progress():
    process_id = request.args.get('process_id')
    file_id = request.args.get('file_id')
    progress = get_progress_db_bucket(process_id, 'gz_raw', file_id)
    gz_filedata = Upload.get_gz_filedata(process_id)
    return {
        "progress": progress, 'gz_filedata': gz_filedata
    }

@upload_bp.route('/upload', methods=['POST'], endpoint='handle_upload')
@login_required
@approved_required
def handle_upload():
    file = request.files.get('file')
    if file:
        process_id = request.args.get('process_id')
        logger.info('process_is is ')
        logger.info(process_id)
        #fields to know which file we are uploading
        form_filename       = request.args.get('filename')
        form_filesize       = request.args.get('filesize')
        form_filechunks     = request.args.get('filechunks')
        form_fileidentifier = request.args.get('fileindex')


        upload = Upload.get(process_id)
        uploads_folder = upload.uploads_folder
        gz_filedata = Upload.get_gz_filedata(upload.id)


        # Extract Resumable.js headers
        resumable_chunk_number = request.args.get('resumableChunkNumber')
        resumable_total_chunks = request.args.get('resumableTotalChunks')
        resumable_chunk_size = request.args.get('resumableChunkSize')
        resumable_total_size = request.args.get('resumableTotalSize')
        expected_md5 = request.args.get('md5')


        # Handle file chunks or combine chunks into a complete file
        chunk_number = int(resumable_chunk_number) if resumable_chunk_number else 1
        total_chunks = int(resumable_total_chunks) if resumable_total_chunks else 1

        # Calculate the percentage completion
        percentage = int((chunk_number / total_chunks) * 100)


        one_filedata = {
            'form_filename'         : form_filename,
            'form_filesize'         : form_filesize,
            'form_filechunks'       : form_filechunks,
            'form_fileidentifier'   : form_fileidentifier,
            'chunk_number_uploaded' : chunk_number,
            'percent_uploaded'      : percentage,
            'expected_md5'          : expected_md5
        }

        Upload.update_gz_filedata(process_id, one_filedata)

        # Save or process the chunk (for demonstration, just save it)
        save_path = f'uploads/{uploads_folder}/{file.filename}.part{chunk_number}'
        file.save(save_path)

        # Check if all chunks have been uploaded
        if chunk_number == total_chunks:
            # Perform actions for the complete file
            # Combine the chunks, save to final location, etc.
            final_file_path = f'uploads/{uploads_folder}/{file.filename}'
            temp_file_path = f'uploads/{uploads_folder}/{file.filename}.temp'
            with open(temp_file_path, 'ab') as temp_file:
                for i in range(1, total_chunks + 1):
                    chunk_path = f'uploads/{uploads_folder}/{file.filename}.part{i}'
                    with open(chunk_path, 'rb') as chunk_file:
                        temp_file.write(chunk_file.read())


            # Perform MD5 hash check
            expected_md5 = request.args.get('md5')  # Get the expected MD5 hash from the request
            actual_md5 = calculate_md5(temp_file_path)

            # Compare MD5 hashes
            if expected_md5 == actual_md5:
                # MD5 hashes match, file integrity verified
                os.rename(temp_file_path, final_file_path)

                # Then, since it is now confirmed, lets delete the parts
                for i in range(1, total_chunks + 1):
                    chunk_path = f'uploads/{uploads_folder}/{file.filename}.part{i}'
                    os.remove(chunk_path)

                result = init_send_raw_to_storage(process_id, file.filename)
                result2 = unzip_raw(process_id, file.filename)
                gz_filedata = Upload.get_gz_filedata(upload.id)
                return jsonify({'message': 'File upload complete and verified', 'gz_filedata': gz_filedata})

            # MD5 hashes don't match, handle accordingly (e.g., delete the incomplete file, return an error)
            # os.remove(final_file_path)
            return jsonify({'message': 'MD5 hash verification failed'}), 400


        return jsonify({'message': f'Chunk {chunk_number} uploaded'}), 200

    return jsonify({'message': 'No file received'}), 400

@upload_bp.route('/upload', methods=['GET'], endpoint='check_chunk')
@login_required
@approved_required
def check_chunk():
    process_id = request.args.get('process_id')
    chunk_number = request.args.get('resumableChunkNumber')

    resumable_filename = request.args.get('resumableFilename')
    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder

    chunk_path = f'uploads/{uploads_folder}/{resumable_filename}.part{chunk_number}'

    if os.path.exists(chunk_path):
        return '', 200  # Chunk already uploaded, return 200
    return '', 204  # Chunk not found, return 204

@upload_bp.route('/renamefiles', methods=['POST'], endpoint='renamefiles')
@login_required
@approved_required
def renamefiles():
    logger.info('renaming files starts')

    # in order to continue on the same process, lets get the id from the form
    process_id = request.form["process_id"]

    skip = request.form["skip"]

    if skip == "true":
        Upload.mark_field_as_true(process_id, 'renaming_skipped')
        result = {"msg": "Renaming files skipped."}
    else:
        result = rename_all_files(process_id)

    return jsonify(result), 200


@upload_bp.route('/fastqcfiles', methods=['POST'], endpoint='fastqcfiles')
@login_required
@approved_required
def fastqcfiles():
    process_id = request.form["process_id"]
    init_fastqc_multiqc_files(process_id)
    return 'ok', 200

@upload_bp.route('/fastqcprogress', endpoint='fastqc_progress')
@login_required
@approved_required
def fastqc_progress():
    process_id = request.args.get('process_id')
    to_return = get_fastqc_progress(process_id)
    return to_return

@upload_bp.route('/multiqc', methods=['GET'], endpoint='show_multiqc_report')
@login_required
@approved_required
def show_multiqc_report():
    process_id = request.args.get('process_id')
    bucket = request.args.get('bucket')
    folder = request.args.get('folder')
    multiqc_report = get_multiqc_report(process_id, bucket, folder)
    if multiqc_report['multiqc_report_exists']:
        return send_from_directory(multiqc_report['multiqc_report_path'], 'multiqc_report.html')

    return ''

@upload_bp.route('/uploadfinalfiles', methods=['POST'], endpoint='upload_final_files_route')
@login_required
@approved_required
def upload_final_files_route():
    process_id = request.form["process_id"]

    # if the files_json is empty, recreate it
    upload = Upload.get(process_id)
    matching_files_dict = upload.get_files_json()
    if (not upload.renaming_skipped):
        if len(matching_files_dict) == 0:
            recreate_matching_files(process_id)

    init_upload_final_files_to_storage(process_id)
    return jsonify({'message': 'Process initiated'})

@upload_bp.route('/user_uploads', methods=['GET'], endpoint='user_uploads')
@login_required
@approved_required
def user_uploads():
    user_id = request.args.get('user_id')
    if (current_user.admin) or (current_user.id == user_id) :
        user_uploads = Upload.get_uploads_by_user(user_id)
        return render_template('user_uploads.html',
                                user_uploads=user_uploads,
                                user_id=user_id,
                                is_admin=current_user.admin,
                                username=current_user.name,
                                user_email=current_user.email)
    else:
        return redirect(url_for('user.only_admins'))

@upload_bp.route('/delete_upload_files', methods=['GET'], endpoint='delete_renamed_files')
@admin_required
@login_required
@approved_required
def delete_upload_files():
    process_id = request.args.get('process_id')
    user_id = request.args.get('user_id')
    upload = Upload.get(process_id)
    upload.delete_files_from_filesystem()
    return redirect(url_for('upload.user_uploads', user_id=user_id))

@upload_bp.route('/delete_upload_process', methods=['GET'], endpoint='delete_upload_process')
@admin_required
@login_required
@approved_required
def delete_upload_process():
    process_id = request.args.get('process_id')
    user_id = request.args.get('user_id')
    Upload.delete_upload_and_files(process_id)
    return redirect(url_for('upload.user_uploads', user_id=user_id))



@upload_bp.route('/movefinaldprogress', methods=['GET'], endpoint='get_final_files_to_storage_progress_route')
@login_required
@approved_required
def get_final_files_to_storage_progress_route():
    process_id = request.args.get('process_id')
    to_return = get_renamed_files_to_storage_progress(process_id)
    return to_return

@upload_bp.route('/sysreport', methods=['GET'], endpoint='show_system_report')
@login_required
@approved_required
def show_system_report():
    if current_user.admin:
        disk_usage = psutil.disk_usage('/app')
        return jsonify({
            'total': disk_usage.total,
            'used': disk_usage.used,
            'free': disk_usage.free,
            'percent': disk_usage.percent
        })
    return {}

@upload_bp.route('/recreate_process_matching_files', endpoint='recreate_process_matching_files')
@login_required
@approved_required
def recreate_process_matching_files():
    process_id = request.args.get('process_id')
    nr_files = recreate_matching_files(process_id)
    return {
        "nr_files": nr_files
    }
