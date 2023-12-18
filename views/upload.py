import datetime
import random
import string
import os
from pathlib import Path
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, request, jsonify
from flask import current_app as app  # Import the 'app' instance
from flask_login import (
    LoginManager,
    current_user,
    login_required,
    login_user,
    logout_user,
)

from helpers.csv import validate_csv_column_names
from helpers.bucket_upload import chunked_upload, get_progress

from models.upload import Upload

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
    upload = Upload.get_latest_not_sent_to_bucket(current_user.id)
    app.logger.info('upload id ' + str(upload.id))
    show_step_2 = False
    if (upload.csv_uploaded and not upload.gz_uploaded):
        show_step_2 = True
    
    return render_template(
                            "form.html", 
                            process_id=upload.id, 
                            csv_uploaded=upload.csv_uploaded,
                            csv_filename=upload.csv_filename,
                            show_step_2=show_step_2, 
                            gz_uploaded=upload.gz_uploaded, 
                            gz_filename=upload.gz_filename, 
                            gz_sent_to_bucket=upload.gz_sent_to_bucket
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

    structure_matches = validate_csv_column_names(save_path)
    if structure_matches:
        chunked_upload(save_path, uploads_folder, filename, file_uuid='temp_csv')
        new_id = Upload.create(user_id=current_user.id, csv_filename=filename, uploads_folder=uploads_folder)
        # app.logger.info('new_id is ' + str(new_id))
        return jsonify({"msg": "CSV file uploaded successfully. Fields match", "process_id": new_id}), 200
    else:
        return jsonify({"error": "CSV file fields don't match expected structure"}), 400


@upload_bp.route('/uploadprogress')
@login_required
def api_progress():
    file_uuid = request.args.get('file_uuid')
    progress = get_progress(file_uuid)
    return {
        "progress": progress
    }
    
@upload_bp.route('/upload', methods=['POST'])
@login_required
def upload_chunked():
    # app.logger.info('upload starts')
    file = request.files["file"]
    file_uuid = request.form["dzuuid"]
    
    # in order to continue on the same process, lets get the id from the form
    process_id = request.form["process_id"]
    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder
    
    # app.logger.info('process_id is ' + str(process_id))
    # Generate a unique filename to avoid overwriting using 8 chars of uuid before filename.
    filename = secure_filename(file.filename)
    
    path = Path("uploads", uploads_folder)  
    save_path = path / filename    
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
            print('upload finished')
            Upload.mark_field_as_true(process_id, 'gz_uploaded')
            Upload.update_gz_filename(process_id, filename)
            
            # chunked_upload(save_path, uploads_folder, filename, file_uuid)
            #Upload.mark_field_as_true(process_id, 'gz_sent_to_bucket')

            #extract_directory = Path("processing", file_uuid)
            #gunzip_result = extract_gzip(save_path, file_uuid, extract_directory)
            #app.logger.info(gunzip_result)

    return jsonify({"msg": "Chunk upload successful."}), 200
    
@upload_bp.route('/sendrawtostorage', methods=['POST'])
@login_required
def send_raw_to_storage():
    #app.logger.info('raw to storage starts')
    
    # in order to continue on the same process, lets get the id from the form
    process_id = request.form["process_id"]
    file_uuid   = request.form["file_uuid"]
    #app.logger.info('process_id is ' + str(process_id))
    #app.logger.info('file_uuid is ' + str(file_uuid))

    upload = Upload.get(process_id)
    uploads_folder = upload.uploads_folder
    path = Path("uploads", uploads_folder)
    filename = upload.gz_filename
    save_path = path / filename   
    raw_uploaded = chunked_upload(save_path, uploads_folder, filename, file_uuid)
    #Upload.mark_field_as_true(process_id, 'gz_sent_to_bucket')
    if (raw_uploaded):    
        return jsonify({"msg": "Raw to storage was successfully transfered."}), 200
    
    return jsonify({"error": "Something went wrong."}), 400