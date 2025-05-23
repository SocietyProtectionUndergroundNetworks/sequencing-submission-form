import logging
import pandas as pd
import os
from helpers.dbm import session_scope
from helpers.bucket import list_buckets, init_bucket_chunked_upload_v2
from models.db_model import (
    SequencingCompanyInputTable,
    SequencingSamplesTable,
    SequencingUploadsTable,
    SequencingSequencerIDsTable,
)


# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class SequencingCompanyInput:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get(self, id):
        with session_scope() as session:

            upload_db = (
                session.query(SequencingCompanyInputTable)
                .filter_by(id=id)
                .first()
            )

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
            upload = SequencingCompanyInputTable(**filtered_dict)

            return upload

    @classmethod
    def create(cls, sequencingCompanyUploadId, datadict):
        with session_scope() as session:

            # Create a new instance of SequencingUploadsTable
            new_company_input = SequencingCompanyInputTable(
                sequencingCompanyUploadId=sequencingCompanyUploadId,
            )

            new_company_input.sample_number = datadict[
                "sample_number"
            ]  # Use the updated keys
            new_company_input.sample_id = datadict["sample_id"]
            new_company_input.sequencer_id = datadict["sequencer_id"]
            new_company_input.sequencing_provider = datadict[
                "sequencing_provider"
            ]
            new_company_input.project = datadict["project"]
            new_company_input.region = datadict["region"]
            new_company_input.index_1 = datadict["index_1"]
            new_company_input.barcode_2 = datadict["barcode_2"]

            session.add(new_company_input)
            session.commit()

            session.refresh(new_company_input)

            new_id = new_company_input.id

            return new_id

    @classmethod
    def get_all_by_upload_id(cls, sequencingCompanyUploadId):
        with session_scope() as session:

            # Query all records with the specified sequencingCompanyUploadId
            results = (
                session.query(SequencingCompanyInputTable)
                .filter_by(sequencingCompanyUploadId=sequencingCompanyUploadId)
                .order_by(
                    SequencingCompanyInputTable.project,
                    SequencingCompanyInputTable.sample_number,
                )
                .all()
            )

            all_records = []
            for record in results:
                record_dict = {
                    key: value
                    for key, value in record.__dict__.items()
                    if not key.startswith("_")
                }

                sample_id = record_dict.get("sample_id")
                project_id = record_dict.get("project")

                if sample_id and project_id:
                    existing_sample_id, metadata_upload_id = (
                        cls.check_sample_exists(sample_id, project_id)
                    )
                    record_dict["SampleID"] = (
                        existing_sample_id if existing_sample_id else None
                    )
                    record_dict["metadata_upload_id"] = (
                        metadata_upload_id if metadata_upload_id else None
                    )

                # If the project is not "sequencing_blanks_dev" or
                # "sequencing_blanks" and no SampleID found
                if project_id not in [
                    "sequencing_blanks_dev",
                    "sequencing_blanks",
                ]:
                    if not record_dict.get("SampleID"):
                        if "problems" not in record_dict:
                            record_dict["problems"] = []
                        record_dict["problems"] = (
                            "The sample ID was not found in that project"
                        )

                # Check if SequencingSequencerIDsTable has a record
                # for this sample_id and region
                sequencer_info = (
                    cls.check_if_sequencer_entry_exists_for_sample_and_region(
                        record_dict.get("SampleID"), record_dict.get("region")
                    )
                )
                record_dict["sample_region_taken"] = bool(sequencer_info)
                record_dict["sequencer_info"] = sequencer_info

                # Check if this sequencer id already exists in this project
                # This could happen because some sequencing providers
                # use the same filenames in all their runs. If a project
                # has been run in multiple runs, we may receive the same
                # filename but attributed to different files
                sequencer_id = record_dict.get("sequencer_id")
                sequencer_id_exists_in_project = (
                    cls.check_if_sequencer_id_exists_in_project(
                        sequencer_id, project_id
                    )
                )
                record_dict["sequencer_id_exists_in_project"] = None
                if sequencer_id_exists_in_project:
                    record_dict["sequencer_id_exists_in_project"] = True

                all_records.append(record_dict)

            return all_records

    @classmethod
    def check_dataframe(cls, df):
        # Initialize a list to store problems for each row
        problems = []
        buckets = list_buckets()
        for index, row in df.iterrows():
            problem_messages = []

            # Check for missing values and add appropriate messages
            if pd.isna(row.get("project")):
                problem_messages.append("Missing Project")
            else:
                # Check if the project exists in known buckets
                if row["project"] not in buckets:
                    problem_messages.append(
                        "Project cannot be found in known buckets"
                    )
            if pd.isna(row.get("sample_id")):
                problem_messages.append("Missing Sample_ID")
            if pd.isna(row.get("sequencer_id")):
                problem_messages.append("Missing Sequencer_ID")
            if pd.isna(row.get("sequencing_provider")):
                problem_messages.append("Missing Sequencing Provider")
            if pd.isna(row.get("region")):
                problem_messages.append("Missing Region")
            if pd.isna(row.get("index_1")):
                problem_messages.append("Missing Index_1")
            if pd.isna(row.get("barcode_2")):
                problem_messages.append("Missing Barcode_2")

            # Combine all problem messages for the row
            if problem_messages:
                problems.append(", ".join(problem_messages))
            else:
                problems.append(None)  # No problems

        # Add the problems column to the DataFrame
        df["problems"] = problems

        return df

    @classmethod
    def check_sample_exists(cls, sample_id, project_id):
        with session_scope() as session:

            # Query to check if the sample exists in SequencingSamplesTable
            sample = (
                session.query(SequencingSamplesTable)
                .join(
                    SequencingUploadsTable,
                    SequencingSamplesTable.sequencingUploadId
                    == SequencingUploadsTable.id,
                )
                .filter(
                    SequencingSamplesTable.SampleID == sample_id,
                    SequencingUploadsTable.project_id == project_id,
                )
                .first()
            )

            return (
                [sample.id, sample.sequencingUploadId]
                if sample
                else [None, None]
            )

    @classmethod
    def check_if_sequencer_entry_exists_for_sample_and_region(
        cls, sample_id, region
    ):
        if not sample_id or not region:
            return None

        with session_scope() as session:

            # Query to check if the sequencer entry
            # exists for the sample_id and region
            sequencer_entry = (
                session.query(SequencingSequencerIDsTable)
                .filter_by(sequencingSampleId=sample_id, Region=region)
                .first()
            )
            return (
                {
                    "SequencerID": sequencer_entry.SequencerID,
                    "Index_1": sequencer_entry.Index_1,
                    "Index_2": sequencer_entry.Index_2,
                }
                if sequencer_entry
                else None
            )

    @classmethod
    def check_if_sequencer_id_exists_in_project(cls, SequencerID, project_id):
        if not SequencerID or not project_id:
            return None

        with session_scope() as session:

            result = (
                session.query(SequencingSequencerIDsTable.id)
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
                .filter(
                    SequencingSequencerIDsTable.SequencerID == SequencerID,
                    SequencingUploadsTable.project_id == project_id,
                )
                .first()
            )

            if result:
                return result.id
            return None

    @classmethod
    def copy_sequencer_ids_to_metadata_upload(
        cls, upload_id, metadata_upload_id, sequencing_run
    ):
        with session_scope() as session:

            # Retrieve all records from
            # SequencingCompanyInputTable with the given upload_id
            input_records = (
                session.query(SequencingCompanyInputTable)
                .filter_by(sequencingCompanyUploadId=upload_id)
                .all()
            )

            for record in input_records:
                # Check if the corresponding sample exists
                sample_id, sequencingUploadId = cls.check_sample_exists(
                    record.sample_id, record.project
                )

                if not sample_id:
                    # If the sample does not exist, continue to the next record
                    continue

                # Check if a record already exists
                # in SequencingSequencerIDsTable
                existing_entry = (
                    session.query(SequencingSequencerIDsTable)
                    .filter_by(
                        sequencingSampleId=sample_id, Region=record.region
                    )
                    .first()
                )

                if existing_entry:
                    # If the record already exists, skip this record
                    continue

                # Additional check: Is this sequencer
                # ID already used in the project?
                sequencer_id_used = (
                    cls.check_if_sequencer_id_exists_in_project(
                        record.sequencer_id, record.project
                    )
                )

                if sequencer_id_used:
                    # Sequencer ID found in the project, so skip
                    continue

                if int(metadata_upload_id) == int(sequencingUploadId):
                    # If the record doesn't exist, create a new entry
                    # in SequencingSequencerIDsTable
                    new_sequencer_entry = SequencingSequencerIDsTable(
                        sequencingSampleId=sample_id,
                        SequencerID=record.sequencer_id,
                        Region=record.region,
                        Index_1=record.index_1,
                        Index_2=record.barcode_2,
                        sequencing_run=sequencing_run,
                    )

                    session.add(new_sequencer_entry)

            # Commit the new entries to the database
            session.commit()

    @classmethod
    def move_sequencing_blanks(
        cls, sequencingCompanyUploadId, directory_name, bucket_folder_name
    ):
        with session_scope() as session:
            # Query all records with the specified sequencingCompanyUploadId
            results = (
                session.query(SequencingCompanyInputTable)
                .filter_by(
                    sequencingCompanyUploadId=sequencingCompanyUploadId,
                    project="sequencing_blanks",
                )
                .order_by(
                    SequencingCompanyInputTable.project,
                    SequencingCompanyInputTable.sample_number,
                )
                .all()
            )

            for record in results:
                record_dict = {
                    key: value
                    for key, value in record.__dict__.items()
                    if not key.startswith("_")
                }

                sequencer_id = record_dict.get("sequencer_id")
                if not sequencer_id:
                    logger.warning(
                        f"Skipping record {record_dict.get('id')}"
                        f" due to missing sequencer_id"
                    )
                    continue

                logger.info(f"Processing sequencer_id: {sequencer_id}")

                # Step 1: List and filter files
                matching_files = [
                    f
                    for f in os.listdir(directory_name)
                    if f.startswith(sequencer_id)
                ]

                if not matching_files:
                    logger.warning(
                        f"No files found for sequencer_id: {sequencer_id}"
                    )

                # Step 2: Upload each file
                for filename in matching_files:
                    local_file_path = os.path.join(directory_name, filename)
                    destination_blob_name = (
                        filename  # Upload with the same filename
                    )

                    logger.info(
                        f"Uploading {local_file_path} to "
                        f"{bucket_folder_name}/{destination_blob_name}"
                    )

                    init_bucket_chunked_upload_v2(
                        local_file_path=local_file_path,
                        destination_upload_directory=bucket_folder_name,
                        destination_blob_name=destination_blob_name,
                        sequencer_file_id=None,
                        bucket_name="sequencing_blanks",
                        known_md5=None,
                    )

                    logger.info(f"Upload complete for {filename}")

        logger.info("Processing complete for all sequencing blanks.")
