import logging
from helpers.dbm import session_scope
from models.db_model import (
    SequencingFilesUploadedTable,
    SequencingUploadsTable,
    SequencingSequencerIDsTable,
    SequencingSamplesTable,
)
from helpers.fastqc import (
    check_fastqc_report,
    extract_total_sequences_from_fastqc_zip,
)

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class SequencingFileUploaded:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get(self, id):
        with session_scope() as session:

            db_data = (
                session.query(SequencingFilesUploadedTable)
                .filter_by(id=id)
                .first()
            )

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
        with session_scope() as session:

            # Get valid columns from the table's model class
            valid_keys = {
                c.name for c in SequencingFilesUploadedTable.__table__.columns
            }

            # Filter out invalid keys
            filtered_datadict = {
                key: value
                for key, value in datadict.items()
                if key in valid_keys
            }

            # Include sequencerId in the filters
            filters = [
                getattr(SequencingFilesUploadedTable, key) == value
                for key, value in filtered_datadict.items()
            ]
            filters.append(
                SequencingFilesUploadedTable.sequencerId == sequencerId
            )

            # Query to check if an identical record exists
            existing_record = (
                session.query(SequencingFilesUploadedTable)
                .filter(*filters)
                .first()
            )

            if existing_record:
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

            return new_file_upload_id

    @classmethod
    def check_if_exists(cls, sequencerId, datadict):
        with session_scope() as session:

            # Get valid columns from the table's model class
            valid_keys = {
                c.name for c in SequencingFilesUploadedTable.__table__.columns
            }

            # Filter out invalid keys from datadict
            filtered_datadict = {
                key: value
                for key, value in datadict.items()
                if key in valid_keys
            }

            # Create filters based on the filtered datadict and sequencerId
            filters = [
                getattr(SequencingFilesUploadedTable, key) == value
                for key, value in filtered_datadict.items()
            ]
            filters.append(
                SequencingFilesUploadedTable.sequencerId == sequencerId
            )

            # Query to check if an identical record exists
            existing_record = (
                session.query(SequencingFilesUploadedTable)
                .filter(*filters)
                .first()
            )

            # If record exists, return the id; otherwise, return False
            if existing_record:
                return existing_record.id
            return False

    @classmethod
    def get_fastqc_report(cls, id, return_format="html"):
        # Connect to the database and create a session
        with session_scope() as session:

            # Perform a single query to get all necessary information
            result = (
                session.query(
                    SequencingFilesUploadedTable.new_name,
                    SequencingUploadsTable.project_id,
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
                logger.error(f"No record found for id: {id}")
                return None

            # Unpack the result
            filename, bucket, upload_folder, region = result

            # Call the check_fastqc_report function
            fastqc_report = check_fastqc_report(
                filename, region, upload_folder, return_format
            )

            return fastqc_report

    @classmethod
    def update_field(cls, id, fieldname, value):
        with session_scope() as session:

            # Fetch the existing record
            upload_db = (
                session.query(SequencingFilesUploadedTable)
                .filter_by(id=id)
                .first()
            )

            if not upload_db:
                return None

            # Update the specified field
            setattr(upload_db, fieldname, value)

            # Commit the changes
            session.commit()

            return True

    @classmethod
    def update_total_sequences(cls, id):
        abs_zip_path = cls.get_fastqc_report(id, return_format="zip")
        total_sequences = extract_total_sequences_from_fastqc_zip(abs_zip_path)

        if isinstance(total_sequences, int):
            cls.update_field(id, "total_sequences_number", total_sequences)
        return total_sequences
