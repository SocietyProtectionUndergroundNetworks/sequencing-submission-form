import os
import pandas as pd
import logging
import csv
from models.db_model import (
    SequencingAnalysisTable,
    SequencingSamplesTable,
    SequencingAnalysisTypesTable,
    SequencingUploadsTable,
    SequencingAnalysisSampleRichnessTable,
    OTU,
)
from helpers.dbm import session_scope

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class SequencingAnalysis:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get(self, id):
        with session_scope() as session:

            item_db = (
                session.query(SequencingAnalysisTable).filter_by(id=id).first()
            )

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
        with session_scope() as session:

            new_item = SequencingAnalysisTable(
                sequencingUploadId=sequencingUploadId,
                sequencingAnalysisTypeId=sequencingAnalysisTypeId,
            )

            session.add(new_item)
            session.commit()

            # Get the ID of the newly created record
            new_id = new_item.id

            return new_id

    @classmethod
    def get_by_upload_and_type(
        cls, sequencingUploadId, sequencingAnalysisTypeId
    ):
        with session_scope() as session:

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

            if not item_db:
                return None

            return item_db.id

    @classmethod
    def get_by_upload(cls, sequencingUploadId):
        with session_scope() as session:

            # Query the database for all items matching the sequencingUploadId,
            # joining with the SequencingAnalysisTypesTable to
            # include analysisTypeName
            items = (
                session.query(
                    SequencingAnalysisTable,
                    SequencingAnalysisTypesTable.name.label(
                        "analysisTypeName"
                    ),
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
                    "lotus2_status": (
                        item.SequencingAnalysisTable.lotus2_status
                    ),
                    "rscripts_status": (
                        item.SequencingAnalysisTable.rscripts_status
                    ),
                }
                for item in items
            ]

            return results

    @classmethod
    def update_field(cls, id, fieldname, value):
        with session_scope() as session:

            # Fetch the existing record
            upload_db = (
                session.query(SequencingAnalysisTable).filter_by(id=id).first()
            )

            if not upload_db:
                return None

            # Update the specified field
            setattr(upload_db, fieldname, value)

            # Commit the changes
            session.commit()

            return True

    @classmethod
    def import_richness(cls, analysis_id):
        with session_scope() as session:

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

            # Step 2: Construct the path to the file
            folder_path = os.path.join(
                "seq_processed",
                data.uploads_folder,
                "r_output",
                data.type_name,
            )
            csv_path = os.path.join(folder_path, "metadata_chaorichness.csv")

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

            # Fallback: Handle sample IDs starting with `S_`
            for sample_id in sample_ids:
                if sample_id not in sample_map and sample_id.startswith("S_"):
                    adjusted_sample_id = sample_id[2:]  # Remove "S_" prefix
                    fallback_sample = (
                        session.query(
                            SequencingSamplesTable.id,
                            SequencingSamplesTable.SampleID,
                        )
                        .filter(
                            SequencingSamplesTable.SampleID
                            == adjusted_sample_id
                        )
                        .first()
                    )
                    if fallback_sample:
                        sample_map[sample_id] = fallback_sample.id

            # Step 5: Prepare data for insertion
            records_to_insert = []
            for _, row in richness_data.iterrows():
                sample_db_id = sample_map.get(row["sample_id"])
                if not sample_db_id:
                    logger.warning(
                        f"SampleID {row['sample_id']}"
                        f" not found in the database"
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
                logger.info(
                    f"Imported {len(records_to_insert)} richness records."
                )
            else:
                logger.warning("No records to import.")

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
        with session_scope() as session:
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

    @classmethod
    def delete_otu_data(cls, analysis_id):
        """
        Deletes all OTU data associated with the given analysis_id.

        Args:
            analysis_id (int): The ID of the analysis for
                                which to delete richness data.

        Returns:
            bool: True if records were deleted, False if no records were found.
        """
        with session_scope() as session:
            # Query for all richness records associated with the analysis_id
            records_to_delete = (
                session.query(OTU)
                .filter_by(sequencing_analysis_id=analysis_id)
                .all()
            )

            if not records_to_delete:
                logger.info(f"No otu found for analysis_id {analysis_id}.")
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

    @classmethod
    def export_richness_data(cls, analysis_type_id, output_file):
        """
        Exports richness data for a specific analysis_type_id,
        including only specific samples.

        Args:
            analysis_type_id (int): The ID of the analysis
                                    type to export data for.
            output_file (str): Path to the CSV file where
                                the data will be saved.

        Returns:
            int: Number of rows exported.
        """

        with session_scope() as session:
            # Query the data based on the conditions
            query = (
                session.query(
                    SequencingUploadsTable.project_id,
                    SequencingSamplesTable.SampleID,
                    SequencingSamplesTable.Latitude,
                    SequencingSamplesTable.Longitude,
                    SequencingAnalysisSampleRichnessTable.observed,
                    SequencingAnalysisSampleRichnessTable.estimator,
                    SequencingAnalysisSampleRichnessTable.est_s_e,
                    SequencingAnalysisSampleRichnessTable.x95_percent_lower,
                    SequencingAnalysisSampleRichnessTable.x95_percent_upper,
                    SequencingAnalysisSampleRichnessTable.seq_depth,
                )
                .join(
                    SequencingAnalysisTable,
                    SequencingUploadsTable.id
                    == SequencingAnalysisTable.sequencingUploadId,
                )
                .join(
                    SequencingAnalysisTypesTable,
                    SequencingAnalysisTable.sequencingAnalysisTypeId
                    == SequencingAnalysisTypesTable.id,
                )
                .join(
                    SequencingAnalysisSampleRichnessTable,
                    SequencingAnalysisSampleRichnessTable.analysis_id
                    == SequencingAnalysisTable.id,
                )
                .join(
                    SequencingSamplesTable,
                    SequencingSamplesTable.id
                    == SequencingAnalysisSampleRichnessTable.sample_id,
                )
                .filter(
                    SequencingSamplesTable.Sample_or_Control == "True Sample",
                    SequencingSamplesTable.Sample_type == "soil",
                    SequencingAnalysisTable.sequencingAnalysisTypeId
                    == analysis_type_id,
                )
            )

            # Execute the query and fetch results
            results = query.all()

            # Write to the output file
            with open(output_file, mode="w", newline="") as csv_file:
                writer = csv.writer(csv_file)
                # Write the header
                writer.writerow(
                    [
                        "project_id",
                        "SampleID",
                        "Latitude",
                        "Longitude",
                        "observed",
                        "estimator",
                        "est_s_e",
                        "x95_percent_lower",
                        "x95_percent_upper",
                        "seq_depth",
                    ]
                )
                # Write the rows
                for row in results:
                    writer.writerow(row)

            logger.info(
                f"Exported {len(results)} rows of richness "
                f"data for analysis_type_id {analysis_type_id}."
            )
            return len(results)
