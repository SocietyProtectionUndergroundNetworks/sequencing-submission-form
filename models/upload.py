from helpers.dbm import connect_db, get_session
from models.db_model import UploadTable
from sqlalchemy import desc

class Upload():
    def __init__(
                    self, 
                    id, 
                    user_id, 
                    created_at, 
                    updated_at, 
                    uploads_folder, 
                    csv_uploaded, 
                    csv_filename, 
                    gz_uploaded, 
                    gz_filename, 
                    gz_sent_to_bucket
                ):
        self.id = id
        self.user_id = user_id
        self.created_at = created_at
        self.updated_at = updated_at
        self.uploads_folder = uploads_folder
        self.csv_uploaded = csv_uploaded
        self.csv_filename = csv_filename
        self.gz_uploaded = gz_uploaded        
        self.gz_filename = gz_filename
        self.gz_sent_to_bucket = gz_sent_to_bucket
              

    @classmethod
    def get(self, id):
        db_engine = connect_db()
        session = get_session(db_engine)
        
        upload_db = session.query(UploadTable).filter_by(id=id).first()
        
        session.close()
        
        if not upload_db:
            return None

        upload = UploadTable(
            id=upload_db.id, 
            user_id=upload_db.user_id, 
            created_at=upload_db.created_at, 
            updated_at=upload_db.updated_at, 
            uploads_folder=upload_db.uploads_folder, 
            csv_uploaded=upload_db.csv_uploaded, 
            csv_filename=upload_db.csv_filename, 
            gz_uploaded=upload_db.gz_uploaded, 
            gz_filename=upload_db.gz_filename, 
            gz_sent_to_bucket=upload_db.gz_sent_to_bucket
        )
        
        return upload

    @classmethod
    def get_latest_not_sent_to_bucket(cls, user_id):
        db_engine = connect_db()
        session = get_session(db_engine)

        latest_upload = (
            session.query(UploadTable)
            .filter(
                UploadTable.user_id == user_id,
                UploadTable.gz_sent_to_bucket != True  # Assuming it's a Boolean field
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
            
         