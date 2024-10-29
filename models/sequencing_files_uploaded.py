import logging
import os
from helpers.dbm import connect_db, get_session
from models.db_model import (
    SequencingFilesUploadedTable,
    SequencingUploadsTable,
    SequencingSequencerIDsTable,
    SequencingSamplesTable,
)
from helpers.fastqc import (
    check_fastqc_report,
    extract_total_sequences_from_fastqc_zip,
    count_primer_occurrences,
)
from helpers.csv import get_sequences_based_on_primers

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
            session.close()
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

        cls.update_primer_occurrences_count(new_file_upload_id)

        return new_file_upload_id

    @classmethod
    def check_if_exists(cls, sequencerId, datadict):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Get valid columns from the table's model class
        valid_keys = {
            c.name for c in SequencingFilesUploadedTable.__table__.columns
        }

        # Filter out invalid keys from datadict
        filtered_datadict = {
            key: value for key, value in datadict.items() if key in valid_keys
        }

        # Create filters based on the filtered datadict and sequencerId
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

        session.close()

        # If record exists, return the id; otherwise, return False
        if existing_record:
            return existing_record.id
        return False

    @classmethod
    def get_fastqc_report(cls, id, return_format="html"):
        # Connect to the database and create a session
        db_engine = connect_db()
        session = get_session(db_engine)

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
            session.close()
            logger.error(f"No record found for id: {id}")
            return None

        # Unpack the result
        filename, bucket, upload_folder, region = result

        # Close the session before checking the FastQC report
        session.close()

        # Call the check_fastqc_report function
        fastqc_report = check_fastqc_report(
            filename, bucket, region, upload_folder, return_format
        )

        return fastqc_report

    @classmethod
    def update_field(cls, id, fieldname, value):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Fetch the existing record
        upload_db = (
            session.query(SequencingFilesUploadedTable)
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

    @classmethod
    def update_total_sequences(cls, id):
        abs_zip_path = cls.get_fastqc_report(id, return_format="zip")
        total_sequences = extract_total_sequences_from_fastqc_zip(abs_zip_path)

        if isinstance(total_sequences, int):
            cls.update_field(id, "total_sequences_number", total_sequences)
        return total_sequences

    @classmethod
    def update_primer_occurrences_count(cls, id):
        # Connect to the database and create a session
        db_engine = connect_db()
        session = get_session(db_engine)

        # Perform a single query to get all necessary information
        result = (
            session.query(
                SequencingFilesUploadedTable.new_name,
                SequencingFilesUploadedTable.sequencerId,
                SequencingUploadsTable.region_1_forward_primer,
                SequencingUploadsTable.region_1_reverse_primer,
                SequencingUploadsTable.region_2_forward_primer,
                SequencingUploadsTable.region_2_reverse_primer,
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

        # Now that we have the regions primers, lets get the regions:
        from models.sequencing_upload import SequencingUpload

        regions = SequencingUpload.get_regions(
            result.region_1_forward_primer,
            result.region_1_reverse_primer,
            result.region_2_forward_primer,
            result.region_2_reverse_primer,
        )

        if len(regions) > 0 and regions[0] == result.Region:
            # The file belongs to region 1
            forward_primer = result.region_1_forward_primer
            reverse_primer = result.region_1_reverse_primer
        elif len(regions) > 1 and regions[1] == result.Region:
            # The file belongs to region 2 and regions has at least 2 values
            forward_primer = result.region_2_forward_primer
            reverse_primer = result.region_2_reverse_primer
        else:
            logger.info("No primers matched")
            return None

        region_sequences = get_sequences_based_on_primers(
            forward_primer,
            reverse_primer,
        )
        logger.info(region_sequences)

        # Find out if this is the forward or reverse file
        # Files with this sequencer ID
        # Perform a single query to get all necessary information
        result_files = (
            session.query(
                SequencingFilesUploadedTable.new_name,
            )
            .filter(
                SequencingFilesUploadedTable.sequencerId == result.sequencerId
            )
            .all()
        )
        new_names = [file.new_name for file in result_files]
        # Check if there are exactly two files
        if len(new_names) == 2:
            new_names.sort()  # Sort alphabetically

            # Determine if result.new_name is the
            # first or second in the sorted list
            if result.new_name == new_names[0]:
                logger.info("result.new_name is the first file.")
                # You can also assign a variable if needed
                sequence = region_sequences["Forward Primer"]
            elif result.new_name == new_names[1]:
                logger.info("result.new_name is the second file.")
                # Assign a variable if needed
                sequence = region_sequences["Reverse Primer"]
            else:
                logger.info("result.new_name is not in the sorted files.")
                return []

            path = (
                "seq_processed/"
                + result.uploads_folder
                + "/"
                + result.new_name
            )
            abs_path = os.path.abspath(path)
            primer_occurrences_count = count_primer_occurrences(
                abs_path, sequence
            )
            logger.info(primer_occurrences_count)

            if isinstance(primer_occurrences_count, int):
                cls.update_field(
                    id, "primer_occurrences_count", primer_occurrences_count
                )
                return primer_occurrences_count

            return primer_occurrences_count
        else:
            logger.info("There are not exactly two files.")

        return []
