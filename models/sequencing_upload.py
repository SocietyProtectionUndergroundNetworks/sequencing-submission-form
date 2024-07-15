import json
import os
import shutil
import logging
from collections import OrderedDict
from helpers.dbm import connect_db, get_session
from models.db_model import SequencingUploadsTable, UserTable
from sqlalchemy import desc, or_
from sqlalchemy.exc import SQLAlchemyError
from pathlib import Path

from flask_login import (
    current_user,
    login_required,
)

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class SequencingUpload:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.path = Path("uploads", self.uploads_folder)

    @classmethod
    def get(self, id):
        db_engine = connect_db()
        session = get_session(db_engine)

        upload_db = session.query(SequencingUploadsTable).filter_by(id=id).first()

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

        # Create an instance of YourClass using the dictionary
        upload = SequencingUploadsTable(**filtered_dict)

        return upload


    @classmethod
    def create(cls, datadict):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Create a new instance of SequencingUploadsTable
        new_upload = SequencingUploadsTable(
            user_id=current_user.id,
        )

        # Dynamically set attributes from datadict
        for key, value in datadict.items():
            if key == "using_scripps":
                value = value.lower() == "yes"            
            if hasattr(new_upload, key):
                setattr(new_upload, key, value)

        session.add(new_upload)
        session.commit()

        # Refresh the object to get the updated ID
        session.refresh(new_upload)

        new_upload_id = new_upload.id

        session.close()

        return new_upload_id

