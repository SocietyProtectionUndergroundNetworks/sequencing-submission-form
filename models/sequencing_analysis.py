import os
import pandas as pd
import logging
from models.db_model import (
    SequencingAnalysisTable,
    SequencingSamplesTable,
    SequencingAnalysisTypesTable,
    SequencingUploadsTable,
    SequencingAnalysisSampleRichnessTable,
)
from helpers.dbm import connect_db, get_session

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class SequencingAnalysis:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get(self, id):
        db_engine = connect_db()
        session = get_session(db_engine)

        item_db = (
            session.query(SequencingAnalysisTable).filter_by(id=id).first()
        )

        session.close()

        if not item_db:
            return None

        # Assuming upload_db is an instance of some SQLAlchemy model
        item_db_dict = item_db.__dict__

        # Remove keys starting with '_'
        filtered_dict = {
            key: value
            for key, value in item_db_dict.items()
            if not key.startswith("_")
        }

        # Create an instance of YourClass using the dictionary
        upload = SequencingAnalysisTable(**filtered_dict)

        return upload

    @classmethod
    def create(cls, sequencingUploadId, sequencingAnalysisTypeId):
        # Try to get an existing record using the get_by_upload_and_type method
        existing_item = cls.get_by_upload_and_type(
            sequencingUploadId, sequencingAnalysisTypeId
        )

        if existing_item:
            # If it exists, return the ID of the existing record
            return existing_item

        # If it doesn't exist, create a new record
        db_engine = connect_db()
        session = get_session(db_engine)

        new_item = SequencingAnalysisTable(
            sequencingUploadId=sequencingUploadId,
            sequencingAnalysisTypeId=sequencingAnalysisTypeId,
        )

        session.add(new_item)
        session.commit()

        # Get the ID of the newly created record
        new_id = new_item.id

        session.close()

        return new_id

    @classmethod
    def get_by_upload_and_type(
        cls, sequencingUploadId, sequencingAnalysisTypeId
    ):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Query the database for the item matching both sequencingUploadId
        # and sequencingAnalysisTypeId
        item_db = (
            session.query(SequencingAnalysisTable)
            .filter_by(
                sequencingUploadId=sequencingUploadId,
                sequencingAnalysisTypeId=sequencingAnalysisTypeId,
            )
            .first()
        )

        session.close()

        if not item_db:
            return None

        return item_db.id

    @classmethod
    def get_by_upload(cls, sequencingUploadId):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Query the database for all items matching the sequencingUploadId,
        # joining with the SequencingAnalysisTypesTable to
        # include analysisTypeName
        items = (
            session.query(
                SequencingAnalysisTable,
                SequencingAnalysisTypesTable.name.label("analysisTypeName"),
                SequencingAnalysisTypesTable.id.label("analysisTypeId"),
                SequencingAnalysisTypesTable.region,
            )
            .join(
                SequencingAnalysisTypesTable,
                SequencingAnalysisTable.sequencingAnalysisTypeId
                == SequencingAnalysisTypesTable.id,
            )
            .filter(
                SequencingAnalysisTable.sequencingUploadId
                == sequencingUploadId
            )
            .all()
        )

        session.close()
        # Format the results as a list of dictionaries with desired fields
        results = [
            {
                "id": item.SequencingAnalysisTable.id,
                "sequencingUploadId": (
                    item.SequencingAnalysisTable.sequencingUploadId
                ),
                "analysisTypeId": item.analysisTypeId,
                "analysisTypeName": item.analysisTypeName,
                "region": item.region,
                "lotus2_status": item.SequencingAnalysisTable.lotus2_status,
                "rscripts_status": (
                    item.SequencingAnalysisTable.rscripts_status
                ),
            }
            for item in items
        ]

        return results

    @classmethod
    def update_field(cls, id, fieldname, value):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Fetch the existing record
        upload_db = (
            session.query(SequencingAnalysisTable).filter_by(id=id).first()
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
    def import_richness(cls, analysis_id):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Step 1: Query necessary data
        data = (
            session.query(
                SequencingAnalysisTable.id.label("analysis_id"),
                SequencingUploadsTable.id.label("upload_id"),
                SequencingAnalysisTypesTable.id.label("type_id"),
                SequencingAnalysisTypesTable.name.label("type_name"),
                SequencingUploadsTable.uploads_folder,
                SequencingAnalysisTable.rscripts_status,
            )
            .join(
                SequencingUploadsTable,
                SequencingAnalysisTable.sequencingUploadId
                == SequencingUploadsTable.id,
            )
            .join(
                SequencingAnalysisTypesTable,
                SequencingAnalysisTable.sequencingAnalysisTypeId
                == SequencingAnalysisTypesTable.id,
            )
            .filter(SequencingAnalysisTable.id == analysis_id)
            .first()
        )

        if not data:
            session.close()
            raise ValueError(
                f"No analysis found for analysis_id {analysis_id}"
            )

        # Step 2: Construct the path to the file
        folder_path = os.path.join(
            "seq_processed", data.uploads_folder, "r_output", data.type_name
        )
        csv_path = os.path.join(folder_path, "metadata_chaorichness.csv")

        if not os.path.exists(csv_path):
            session.close()
            raise FileNotFoundError(f"File not found: {csv_path}")

        # Step 3: Read and process the CSV
        richness_data = pd.read_csv(csv_path)

        # Step 4: Map `sample_id` to the `id` in SequencingSamplesTable
        sample_ids = richness_data["sample_id"].tolist()
        samples = (
            session.query(
                SequencingSamplesTable.id, SequencingSamplesTable.SampleID
            )
            .filter(SequencingSamplesTable.SampleID.in_(sample_ids))
            .all()
        )
        sample_map = {sample.SampleID: sample.id for sample in samples}

        # Step 5: Prepare data for insertion
        records_to_insert = []
        for _, row in richness_data.iterrows():
            sample_db_id = sample_map.get(row["sample_id"])
            if not sample_db_id:
                logger.warning(
                    f"SampleID {row['sample_id']} not found in the database"
                )
                continue

            records_to_insert.append(
                SequencingAnalysisSampleRichnessTable(
                    analysis_id=data.analysis_id,
                    sample_id=sample_db_id,
                    observed=row["observed"],
                    estimator=row["estimator"],
                    est_s_e=row["est_s_e"],
                    x95_percent_lower=row["x95_percent_lower"],
                    x95_percent_upper=row["x95_percent_upper"],
                    seq_depth=row["seq_depth"],
                )
            )

        # Step 6: Insert records into the database
        if records_to_insert:
            session.bulk_save_objects(records_to_insert)
            session.commit()
            logger.info(f"Imported {len(records_to_insert)} richness records.")
        else:
            logger.warning("No records to import.")

        session.close()

    @classmethod
    def delete_richness_data(cls, analysis_id):
        """
        Deletes all richness data associated with the given analysis_id.

        Args:
            analysis_id (int): The ID of the analysis for
                                which to delete richness data.

        Returns:
            bool: True if records were deleted, False if no records were found.
        """
        db_engine = connect_db()
        session = get_session(db_engine)

        try:
            # Query for all richness records associated with the analysis_id
            records_to_delete = (
                session.query(SequencingAnalysisSampleRichnessTable)
                .filter_by(analysis_id=analysis_id)
                .all()
            )

            if not records_to_delete:
                logger.info(
                    f"No richness data found for analysis_id {analysis_id}."
                )
                return False

            # Delete the records
            for record in records_to_delete:
                session.delete(record)

            # Commit the changes
            session.commit()
            logger.info(
                f"Deleted {len(records_to_delete)} richness "
                f"records for analysis_id {analysis_id}."
            )
            return True

        except Exception as e:
            logger.error(
                f"Error deleting richness "
                f"data for analysis_id {analysis_id}: {str(e)}"
            )
            session.rollback()
            raise

        finally:
            session.close()
