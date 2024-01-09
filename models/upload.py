import json
from helpers.dbm import connect_db, get_session
from models.db_model import UploadTable
from sqlalchemy import desc, or_
from pathlib import Path

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
                    UploadTable.fastqc_run == False,
                    UploadTable.fastqc_run.is_(None)
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
    def update_gz_filename(cls, upload_id, gz_filename):
        db_engine = connect_db()
        session = get_session(db_engine)

        upload = session.query(UploadTable).filter_by(id=upload_id).first()

        if upload:
            upload.gz_filename = gz_filename
            session.commit()
            session.close()
            return True
        else:
            session.close()
            return False

    @classmethod
    def update_gz_sent_to_bucket_progress(cls, upload_id, progress):
        db_engine = connect_db()
        session = get_session(db_engine)

        upload = session.query(UploadTable).filter_by(id=upload_id).first()

        if upload:
            upload.gz_sent_to_bucket_progress = progress
            session.commit()
            session.close()
            return True
        else:
            session.close()
            return False

    @classmethod
    def update_gz_unziped_progress(cls, upload_id, progress):
        db_engine = connect_db()
        session = get_session(db_engine)

        upload = session.query(UploadTable).filter_by(id=upload_id).first()

        if upload:
            upload.gz_unziped_progress = progress
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