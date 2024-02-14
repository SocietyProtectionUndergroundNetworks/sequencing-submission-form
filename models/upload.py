import json
import os
import logging
from collections import OrderedDict
from helpers.dbm import connect_db, get_session
from models.db_model import UploadTable
from sqlalchemy import desc, or_
from pathlib import Path
from fnmatch import fnmatch

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py

class Upload():
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.path = Path("uploads", self.uploads_folder)
        self.extract_directory = Path("processing", self.uploads_folder)

    @classmethod
    def get(self, id):
        db_engine = connect_db()
        session = get_session(db_engine)

        upload_db = session.query(UploadTable).filter_by(id=id).first()

        session.close()

        if not upload_db:
            return None

        # Assuming upload_db is an instance of some SQLAlchemy model
        upload_db_dict = upload_db.__dict__

        # Remove keys starting with '_'
        filtered_dict = {key: value for key, value in upload_db_dict.items() if not key.startswith('_')}

        # Create an instance of YourClass using the dictionary
        upload = Upload(**filtered_dict)

        return upload

    @classmethod
    def get_latest_unfinished_process(cls, user_id):
        db_engine = connect_db()
        session = get_session(db_engine)

        latest_upload = (
            session.query(UploadTable)
            .filter(
                UploadTable.user_id == user_id,
                or_(
                    UploadTable.renamed_sent_to_bucket == False,
                    UploadTable.renamed_sent_to_bucket.is_(None)
                )
            )
            .order_by(desc(UploadTable.updated_at))  # Get the latest based on updated_at
            .first()
        )

        session.close()

        return latest_upload

    @classmethod
    def create(self, user_id, csv_filename, uploads_folder):
        db_engine = connect_db()
        session = get_session(db_engine)

        new_upload = UploadTable(user_id=user_id, csv_filename=csv_filename, csv_uploaded=True, uploads_folder=uploads_folder)

        session.add(new_upload)
        session.commit()

        # Refresh the object to get the updated ID
        session.refresh(new_upload)

        new_upload_id = new_upload.id

        session.close()

        return new_upload_id

    @classmethod
    def mark_field_as_true(cls, upload_id, field_name):
        db_engine = connect_db()
        session = get_session(db_engine)

        upload = session.query(UploadTable).filter_by(id=upload_id).first()

        if upload and hasattr(upload, field_name):
            setattr(upload, field_name, True)
            session.commit()
            session.close()
            return True
        else:
            session.close()
            return False

    @classmethod
    def update_fastqc_process_id(cls, upload_id, fastqc_process_id):
        db_engine = connect_db()
        session = get_session(db_engine)

        upload = session.query(UploadTable).filter_by(id=upload_id).first()

        if upload:
            upload.fastqc_process_id = fastqc_process_id
            session.commit()
            session.close()
            return True
        else:
            session.close()
            return False

    @classmethod
    def update_gz_filedata(cls, upload_id, gz_filedata):

        logger.info(gz_filedata)

        db_engine = connect_db()
        session = get_session(db_engine)
        upload = session.query(UploadTable).filter_by(id=upload_id).first()
        # one_file_json_data = json.dumps(one_filedata)
        filename = gz_filedata['form_filename']

        if upload:
            existing_gz_filedata_db = upload.gz_filedata
            if (existing_gz_filedata_db):
                new_gz_filedata = json.loads(existing_gz_filedata_db)
            else:
                new_gz_filedata = {}
            new_gz_filedata[filename] = gz_filedata

            upload.gz_filedata = json.dumps(new_gz_filedata)
            session.commit()
            session.close()
            return True
        else:
            session.close()
            return False


    @classmethod
    def get_gz_filedata(cls, upload_id):
        db_engine = connect_db()
        session = get_session(db_engine)

        upload = session.query(UploadTable).filter_by(id=upload_id).first()

        gz_filedata = {}

        if upload.gz_filedata:
            gz_filedata = json.loads(upload.gz_filedata)

        return gz_filedata

    @classmethod
    def update_gz_sent_to_bucket_progress(cls, upload_id, progress, filename):
        db_engine = connect_db()
        session = get_session(db_engine)
        upload = session.query(UploadTable).filter_by(id=upload_id).first()

        if upload:
            if upload.gz_filedata:
                gz_filedata = json.loads(upload.gz_filedata)
                if filename in gz_filedata:
                    gz_filedata[filename]['gz_sent_to_bucket_progress']=progress
                    upload.gz_filedata = json.dumps(gz_filedata)

            session.commit()
            session.close()
            return True
        else:
            session.close()
            return False

    @classmethod
    def update_gz_unziped_progress(cls, upload_id, progress, filename):
        db_engine = connect_db()
        session = get_session(db_engine)
        upload = session.query(UploadTable).filter_by(id=upload_id).first()

        if upload:
            if upload.gz_filedata:
                gz_filedata = json.loads(upload.gz_filedata)
                if filename in gz_filedata:
                    gz_filedata[filename]['gz_unziped_progress']=progress
                    upload.gz_filedata = json.dumps(gz_filedata)

            session.commit()
            session.close()
            return True
        else:
            session.close()
            return False

    @classmethod
    def update_fastqc_files_progress(cls, upload_id, progress):
        db_engine = connect_db()
        session = get_session(db_engine)

        upload = session.query(UploadTable).filter_by(id=upload_id).first()

        if upload:
            upload.fastqc_files_progress = progress
            session.commit()
            session.close()
            return True
        else:
            session.close()
            return False

    @classmethod
    def update_renamed_sent_to_bucket_progress(cls, upload_id, progress):
        db_engine = connect_db()
        session = get_session(db_engine)

        upload = session.query(UploadTable).filter_by(id=upload_id).first()

        if upload:
            upload.renamed_sent_to_bucket_progress = progress
            session.commit()
            session.close()
            return True
        else:
            session.close()
            return False

    @classmethod
    def update_files_json(cls, upload_id, files_dict):
        db_engine = connect_db()
        session = get_session(db_engine)
        files_json = json.dumps(files_dict)

        upload = session.query(UploadTable).filter_by(id=upload_id).first()

        if upload:
            upload.files_json = files_json
            session.commit()
            session.close()
            return True
        else:
            session.close()
            return False

    @classmethod
    def get_files_json(cls, upload_id):
        logger.info(upload_id)
        db_engine = connect_db()
        session = get_session(db_engine)
        upload = session.query(UploadTable).filter_by(id=upload_id).first()
        logger.info(upload)
        
        matching_files_dict = {}
        files_json = upload.files_json
        
        if files_json is not None:
            matching_files_dict = json.loads(upload.files_json)
            
        session.commit()
        session.close()

        # remove files where the name starts with '._' (non real files, artifacts of zip process)
        matching_files_dict = {key: value for key, value in matching_files_dict.items() if not key.startswith('._')}

        # Sort the dictionary based on 'bucket' and 'folder'
        matching_files_dict = OrderedDict(sorted(matching_files_dict.items(), key=lambda x: (x[1].get('bucket', ''), x[1].get('folder', ''))))
        rowspan_counts = {}
        for filename, data in matching_files_dict.items():
            if 'bucket' in data and 'folder' in data:
                key = data['bucket'] + '_' + data['folder']
                if (key in rowspan_counts):
                    rowspan_counts[key] = rowspan_counts[key] + 1
                else:
                    rowspan_counts[key] = 1

        lastkey = ''
        for filename, data in matching_files_dict.items():
            if 'bucket' in data and 'folder' in data:
                key = data['bucket'] + '_' + data['folder']
                if key != lastkey:
                    data['rowspan'] = rowspan_counts[key]
                lastkey = key

        return matching_files_dict


    @classmethod
    def get_uploads_by_user(cls, user_id):
        db_engine = connect_db()
        session = get_session(db_engine)

        uploads = session.query(UploadTable).filter_by(user_id=user_id).all()

        session.close()

        if not uploads:
            return []

        uploads_list = [
            cls(**{key: getattr(upload, key) for key in upload.__dict__.keys() if not key.startswith('_')})
            for upload in uploads
        ]

        return uploads_list
