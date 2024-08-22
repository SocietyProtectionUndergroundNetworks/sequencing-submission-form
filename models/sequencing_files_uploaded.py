import logging
from helpers.dbm import connect_db, get_session
from models.db_model import (
    SequencingFilesUploadedTable,
    SequencingUploadsTable,
    SequencingSequencerIDsTable,
    SequencingSamplesTable,
)
from helpers.fastqc import check_fastqc_report

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class SequencingFileUploaded:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get(self, id):
        db_engine = connect_db()
        session = get_session(db_engine)

        db_data = (
            session.query(SequencingFilesUploadedTable)
            .filter_by(id=id)
            .first()
        )

        session.close()

        if not db_data:
            return None

        dict_data = db_data.__dict__

        # Remove keys starting with '_'
        filtered_dict = {
            key: value
            for key, value in dict_data.items()
            if not key.startswith("_")
        }

        # Create an instance of the using the dictionary
        file_uploaded = SequencingFilesUploadedTable(**filtered_dict)

        return file_uploaded

    @classmethod
    def create(cls, sequencerId, datadict):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Get valid columns from the table's model class
        valid_keys = {
            c.name for c in SequencingFilesUploadedTable.__table__.columns
        }

        # Filter out invalid keys
        filtered_datadict = {
            key: value for key, value in datadict.items() if key in valid_keys
        }

        # Include sequencerId in the filters
        filters = [
            getattr(SequencingFilesUploadedTable, key) == value
            for key, value in filtered_datadict.items()
        ]
        filters.append(SequencingFilesUploadedTable.sequencerId == sequencerId)

        # Query to check if an identical record exists
        existing_record = (
            session.query(SequencingFilesUploadedTable)
            .filter(*filters)
            .first()
        )

        if existing_record:
            session.close()
            return existing_record.id

        # If no existing record is found, create a new one
        new_file_upload = SequencingFilesUploadedTable(
            sequencerId=sequencerId,
        )

        for key, value in filtered_datadict.items():
            if hasattr(new_file_upload, key):
                setattr(new_file_upload, key, value)

        session.add(new_file_upload)
        session.commit()

        session.refresh(new_file_upload)

        new_file_upload_id = new_file_upload.id

        session.close()

        return new_file_upload_id

    @classmethod
    def get_fastqc_report(cls, id):
        # Connect to the database and create a session
        db_engine = connect_db()
        session = get_session(db_engine)

        # Perform a single query to get all necessary information
        result = (
            session.query(
                SequencingFilesUploadedTable.new_name,
                SequencingUploadsTable.project_id,  # (bucket)
                SequencingUploadsTable.uploads_folder,
                SequencingSequencerIDsTable.Region,
            )
            .join(
                SequencingSequencerIDsTable,
                SequencingFilesUploadedTable.sequencerId
                == SequencingSequencerIDsTable.id,
            )
            .join(
                SequencingSamplesTable,
                SequencingSequencerIDsTable.sequencingSampleId
                == SequencingSamplesTable.id,
            )
            .join(
                SequencingUploadsTable,
                SequencingSamplesTable.sequencingUploadId
                == SequencingUploadsTable.id,
            )
            .filter(SequencingFilesUploadedTable.id == id)
            .first()
        )

        if not result:
            session.close()
            logger.error(f"No record found for id: {id}")
            return None

        # Unpack the result
        filename, bucket, upload_folder, region = result

        # Close the session before checking the FastQC report
        session.close()

        # Call the check_fastqc_report function
        fastqc_report = check_fastqc_report(
            filename, bucket, region, upload_folder
        )

        if fastqc_report:
            logger.info(f"FastQC report found: {fastqc_report}")
        else:
            logger.warning(f"No FastQC report found for file: {filename}")

        return fastqc_report
