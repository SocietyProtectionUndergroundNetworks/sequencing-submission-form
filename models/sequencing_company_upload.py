import datetime
import random
import string
import logging
from helpers.dbm import connect_db, get_session
from models.db_model import (
    SequencingCompanyUploadTable,
    SequencingCompanyInputTable,
    UserTable,
)
from pathlib import Path
from flask_login import current_user
from sqlalchemy import desc

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class SequencingCompanyUpload:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get(cls, id):
        db_engine = connect_db()
        session = get_session(db_engine)

        upload_db = (
            session.query(SequencingCompanyUploadTable)
            .filter_by(id=id)
            .first()
        )

        session.close()

        if not upload_db:
            return None

        # Assuming upload_db is an instance of some SQLAlchemy model
        upload_db_dict = upload_db.__dict__

        # Remove keys starting with '_'
        filtered_dict = {
            key: value
            for key, value in upload_db_dict.items()
            if not key.startswith("_")
        }

        # Create an instance of SequencingUpload using the dictionary
        upload = cls(**filtered_dict)

        # Convert the instance to a dictionary including the custom attribute
        upload_dict = upload.__dict__

        return upload_dict

    @classmethod
    def get_all(cls, user_id=None):
        db_engine = connect_db()
        session = get_session(db_engine)

        query = session.query(SequencingCompanyUploadTable, UserTable).join(
            UserTable, SequencingCompanyUploadTable.user_id == UserTable.id
        )

        upload_dbs = query.order_by(
            desc(SequencingCompanyUploadTable.id)
        ).all()

        uploads = []
        for upload_db, user in upload_dbs:
            upload_db_dict = upload_db.__dict__
            user_dict = user.__dict__

            filtered_dict = {
                key: value
                for key, value in upload_db_dict.items()
                if not key.startswith("_")
            }

            upload = cls(**filtered_dict)

            # Count the number of samples associated with this upload
            nr_sequencer_ids = (
                session.query(SequencingCompanyInputTable)
                .filter_by(sequencingCompanyUploadId=filtered_dict["id"])
                .count()
            )
            upload.nr_sequencer_ids = nr_sequencer_ids

            # Add user name and email to the upload dictionary
            upload.user_name = user_dict["name"]
            upload.user_email = user_dict["email"]

            upload_dict = upload.__dict__
            uploads.append(upload_dict)

        session.close()

        return uploads

    @classmethod
    def create(cls, csv_filename):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Create a new instance of SequencingUploadsTable
        new_upload = SequencingCompanyUploadTable(
            user_id=current_user.id,
        )

        new_upload.csv_filename = csv_filename

        session.add(new_upload)
        session.commit()

        # Refresh the object to get the updated ID
        session.refresh(new_upload)

        new_upload_id = new_upload.id

        id_str = f"{new_upload_id:05}"

        # lets create a directory only for this process.
        uploads_folder = (
            id_str
            + "_"
            + datetime.datetime.now().strftime("%Y%m%d")
            + "".join(
                random.choices(string.ascii_uppercase + string.digits, k=6)
            )
        )

        path = Path("seq_company_uploads", uploads_folder)
        path.mkdir(parents=True, exist_ok=True)

        new_upload.uploads_folder = uploads_folder
        session.commit()

        session.close()

        return new_upload_id

    @classmethod
    def update_field(cls, id, fieldname, value):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Fetch the existing record
        upload_db = (
            session.query(SequencingCompanyUploadTable)
            .filter_by(id=id)
            .first()
        )

        if not upload_db:
            session.close()
            return None

        # Update the specified field
        setattr(upload_db, fieldname, value)

        # Commit the changes
        session.commit()
        session.close()

        return True
