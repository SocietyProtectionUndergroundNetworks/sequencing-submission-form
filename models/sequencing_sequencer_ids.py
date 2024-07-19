import logging
import pandas as pd
import numpy as np
from helpers.dbm import connect_db, get_session
from models.db_model import SequencingSequencerIDsTable
from models.sequencing_upload import SequencingUpload
from helpers.metadata_check import get_regions
from sqlalchemy import and_

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class SequencingSequencerId:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get(self, id):
        db_engine = connect_db()
        session = get_session(db_engine)

        sequencer_id_db = (
            session.query(SequencingSequencerIDsTable).filter_by(id=id).first()
        )

        session.close()

        if not sequencer_id_db:
            return None

        # Assuming upload_db is an instance of some SQLAlchemy model
        sequencer_id_db_dict = sequencer_id_db.__dict__

        # Remove keys starting with '_'
        filtered_dict = {
            key: value
            for key, value in sequencer_id_db_dict.items()
            if not key.startswith("_")
        }

        # Create an instance of YourClass using the dictionary
        sequencer_id = SequencingSequencerId(**filtered_dict)

        return sequencer_id

    @classmethod
    def create(cls, sample_id, sequencer_id, region):
        db_engine = connect_db()
        session = get_session(db_engine)

        existing_record = (
            session.query(SequencingSequencerIDsTable)
            .filter(
                and_(
                    SequencingSequencerIDsTable.sequencingSampleId
                    == sample_id,
                    SequencingSequencerIDsTable.Region == region,
                )
            )
            .first()
        )

        if existing_record:
            # If record exists, return its id
            return existing_record.id, "existing"
        else:
            # If record does not exist, create a new one
            new_record = SequencingSequencerIDsTable(
                sequencingSampleId=sample_id,
                SequencerID=sequencer_id,
                Region=region,
            )
            session.add(new_record)
            session.commit()
            # Return the id of the newly created record
            return new_record.id, "new"

    @classmethod
    def check_df_and_add_records(cls, process_id, df, process_data):

        result = 1
        messages = []
        # check the columns
        uploaded_columns = df.columns.tolist()
        if "SampleID" not in uploaded_columns:
            result = 1
            messages = []
        logger.info(df)

        expected_columns = ["SampleID", "Region", "SequencerID"]
        for expected_column in expected_columns:
            if expected_column not in uploaded_columns:
                result = 0
                messages.append(
                    "Expected column " + expected_column + " is missing"
                )

        if result == 1:
            # check each row to see if they are as expected.
            samples_data = SequencingUpload.get_samples(process_id)
            if samples_data is not None:
                sample_ids = [row["SampleID"] for row in samples_data]
                logger.info(sample_ids)
                for index, row in df.iterrows():
                    if row["SampleID"] not in sample_ids:
                        result = 0
                        messages.append(
                            "SampleID: in row "
                            + str(index + 1)
                            + " with the value '"
                            + row["SampleID"]
                            + "' is not in the list of expected"
                            + "' SampleIDs from the metadata"
                        )

            else:
                result = 0
                messages.append("No sample data found for this upload")

            regions = get_regions(process_data)
            for index, row in df.iterrows():
                if row["Region"] not in regions:
                    result = 0
                    messages.append(
                        "Region: in row "
                        + str(index + 1)
                        + " with the value '"
                        + row["Region"]
                        + "' is not in the list of expected Regions"
                    )

                if pd.isna(row["SequencerID"]):
                    result = 0
                    messages.append(
                        "SequencerID: in row "
                        + str(index + 1)
                        + " cannot be empty"
                    )
        if result == 1:
            # Counting the regions per SampleID
            region_counts = df.groupby("SampleID")["Region"].nunique()
            # Checking for discrepancies
            for sample_id, count in region_counts.items():
                sequencing_regions_number = process_data[
                    "Sequencing_regions_number"
                ]
                if count != sequencing_regions_number:
                    result = 0
                    message = (
                        f"The SampleID {sample_id} has {count} regions "
                        f"while we expected {sequencing_regions_number}"
                    )
                    messages.append(message)

        # No problems found, so lets add these records
        if result == 1:
            sample_id_to_id = {
                sample["SampleID"]: sample["id"] for sample in samples_data
            }

            df["db_sample_id"] = None

            for index, row in df.iterrows():
                db_sample_id = sample_id_to_id[row["SampleID"]]
                df.at[index, "db_sample_id"] = (
                    db_sample_id  # Add db_sample_id to the DataFrame
                )
                cls.create(
                    sample_id=db_sample_id,
                    sequencer_id=row["SequencerID"],
                    region=row["Region"],
                )

        return {
            "result": result,
            "data": df.replace({np.nan: None}).to_dict(orient="records"),
            "messages": messages,
        }
