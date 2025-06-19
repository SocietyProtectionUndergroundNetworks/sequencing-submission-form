import logging
import re
import os
import pandas as pd
import numpy as np
from helpers.dbm import session_scope
from helpers.cutadapt import (
    detect_single_read_primers,
    parse_detect_single_read_primers_output,
    detect_merged_read_primers,
    parse_detect_merged_read_primers_output,
)
from models.db_model import (
    SequencingSequencerIDsTable,
    SequencingSamplesTable,
    SequencingFilesUploadedTable,
)
from models.sequencing_upload import SequencingUpload
from sqlalchemy import and_

# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class SequencingSequencerId:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

    @classmethod
    def get(self, id):
        with session_scope() as session:

            sequencer_id_db = (
                session.query(SequencingSequencerIDsTable)
                .filter_by(id=id)
                .first()
            )

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
    def create(cls, sample_id, sequencer_id, region, index_1, index_2):
        with session_scope() as session:

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
                # Prepare the new record dictionary with mandatory fields
                record_data = {
                    "sequencingSampleId": sample_id,
                    "SequencerID": sequencer_id,
                    "Region": region,
                }

                # Only add index_1 and index_2 if they are not None or empty
                if index_1:
                    record_data["Index_1"] = index_1
                if index_2:
                    record_data["Index_2"] = index_2

                # Create the new record using the dictionary
                new_record = SequencingSequencerIDsTable(**record_data)
                session.add(new_record)
                session.commit()
                # Return the id of the newly created record
                new_record_id = new_record.id
                return new_record_id, "new"

    @classmethod
    def check_df_and_add_records(cls, process_id, df, process_data):
        result = 1
        messages = []
        # Check the columns
        uploaded_columns = df.columns.tolist()
        if "SampleID" not in uploaded_columns:
            result = 1
            messages = []
        logger.info(df)

        # Ensure no NaN values in 'Index_1' and 'Index_2'
        if "Index_1" in df.columns:
            df["Index_1"] = df["Index_1"].apply(
                lambda x: None if pd.isna(x) else x
            )
        if "Index_2" in df.columns:
            df["Index_2"] = df["Index_2"].apply(
                lambda x: None if pd.isna(x) else x
            )

        expected_columns = [
            "SampleID",
            "Region",
            "SequencerID",
            "Index_1",
            "Index_2",
        ]
        for expected_column in expected_columns:
            if expected_column not in uploaded_columns:
                result = 0
                messages.append(
                    "Expected column " + expected_column + " is missing"
                )

        if result == 1:
            # Check each row to see if they are as expected.
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
                            + str(row["SampleID"])
                            + "' is not in the list of expected"
                            + "' SampleIDs from the metadata"
                        )

            else:
                result = 0
                messages.append("No sample data found for this upload")

            regions = SequencingUpload.get_regions(
                process_data["region_1_forward_primer"],
                process_data["region_1_reverse_primer"],
                process_data["region_2_forward_primer"],
                process_data["region_2_reverse_primer"],
            )
            for index, row in df.iterrows():
                if row["Region"] not in regions:
                    result = 0
                    messages.append(
                        "Region: in row "
                        + str(index + 1)
                        + " with the value '"
                        + str(row["Region"])
                        + "' is not in the list of expected Regions"
                    )

                if pd.isna(row["SequencerID"]):
                    result = 0
                    messages.append(
                        "SequencerID: in row "
                        + str(index + 1)
                        + " cannot be empty"
                    )

        # New Check for duplicate SampleID and Region combinations
        if result == 1:
            duplicate_combinations = df[
                df.duplicated(subset=["SampleID", "Region"], keep=False)
            ]
            if not duplicate_combinations.empty:
                result = 0
                for (
                    sample_id,
                    region,
                ), group in duplicate_combinations.groupby(
                    ["SampleID", "Region"]
                ):
                    indices = group.index.tolist()
                    messages.append(
                        f"Lines {indices} are assigning "
                        f"sequencerID to the same "
                        f"SampleID/Region ({sample_id}/{region})"
                    )

        if result == 1:
            indexes = ["Index_1", "Index_2"]
            for index_x in indexes:
                logger.info("Checking for " + index_x)
                # Check index_1 if present
                for index, row in df.iterrows():
                    if index_x in row:

                        index_value = row[index_x]
                        logger.info(index_value)
                        if pd.notna(index_value):
                            # Check length
                            if len(index_value) > 100:
                                result = 0
                                messages.append(
                                    f"{ index_x } in row {index + 1} is "
                                    "longer than 100 characters"
                                )
                            # Check if only contains ATGC
                            if not all(char in "ATGC" for char in index_value):
                                result = 0
                                messages.append(
                                    f"{index_x} in row {index + 1} "
                                    "contains invalid characters "
                                    "(only ATGC are allowed)"
                                )

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
                    index_1=row["Index_1"],
                    index_2=row["Index_2"],
                )

        return {
            "result": result,
            "data": df.replace({np.nan: None}).to_dict(orient="records"),
            "messages": messages,
        }

    @classmethod
    def get_matching_sequencer_ids(
        cls, process_id, filename, sequencing_run=None
    ):
        with session_scope() as session:
            matching_ids = []

            # Ensure the filename ends
            # with .fastq.gz or .fq.gz and strip it off
            if filename.endswith(".fastq.gz"):
                filename_no_ext = filename[:-9]  # Remove the .fastq.gz suffix
            elif filename.endswith(".fq.gz"):
                filename_no_ext = filename[:-6]  # Remove the .fq.gz suffix
            else:
                # Return empty list if filename
                # doesn't match expected extensions
                return matching_ids

            # Start building the query
            query = (
                session.query(
                    SequencingSequencerIDsTable.id,
                    SequencingSequencerIDsTable.SequencerID,
                )
                .join(SequencingSamplesTable)
                .filter(
                    SequencingSamplesTable.sequencingUploadId == process_id
                )
            )

            # Execute the query and retrieve results
            sequencer_ids = query.all()

            # Extract id and SequencerID pairs from the query result
            sequencer_ids = [(id, seq_id) for id, seq_id in sequencer_ids]

            # Find matching sequencer IDs and return the corresponding ids
            for id, seq_id in sequencer_ids:
                if filename_no_ext.startswith(seq_id):
                    matching_ids.append(id)

            return matching_ids

    @classmethod
    def generate_new_filename(cls, process_id, filename):
        with session_scope() as session:
            # Ensure the filename ends
            # with .fastq.gz or .fq.gz and strip it off
            if filename.endswith(".fastq.gz"):
                filename_no_ext = filename[:-9]  # Remove the .fastq.gz suffix
                extension = ".fastq.gz"
            elif filename.endswith(".fq.gz"):
                filename_no_ext = filename[:-6]  # Remove the .fq.gz suffix
                extension = ".fq.gz"
            else:
                # Return None if the filename doesn't have the correct suffix
                return None

            # Query to get all relevant records
            sequencer_records = (
                session.query(
                    SequencingSamplesTable.SampleID,
                    SequencingSequencerIDsTable.SequencerID,
                    SequencingSequencerIDsTable.Region,
                )
                .join(SequencingSequencerIDsTable)
                .filter(
                    SequencingSamplesTable.sequencingUploadId == process_id
                )
                .all()
            )

            # Iterate through the results to find the matching record
            for sample_id, sequencer_id, region in sequencer_records:
                if filename_no_ext.startswith(sequencer_id):
                    # Generate the new filename
                    region = region.replace(" ", "_")
                    new_filename = (
                        filename_no_ext.replace(
                            sequencer_id, f"{sample_id}_{region}_"
                        )
                        + extension
                    )
                    return new_filename

            # Return None if no matching record is found
            return None

    @classmethod
    def adapters_count(
        cls,
        sequencer_id,
        process_folder,
        forward_primer,
        reverse_primer,
        reverse_primer_revcomp,
    ):

        # Fetch sequencer record early so we can check fields and update later
        with session_scope() as session:
            sequencer_record = (
                session.query(SequencingSequencerIDsTable)
                .filter_by(id=sequencer_id["id"])
                .first()
            )
            if not sequencer_record:
                logger.error(
                    f"Sequencer record with id {sequencer_id['id']} not found"
                )
                return

            # Check primers exist
            if not (forward_primer and reverse_primer):
                logger.warning(
                    "Forward or reverse primer not provided, "
                    "skipping adapter count."
                )
                return

            # Determine if single-read adapters need
            # to be counted (any of first 3 is None)
            need_single_read = any(
                getattr(sequencer_record, field) is None
                for field in [
                    "fwd_read_fwd_adap",
                    "rev_read_rev_adap",
                    "fwd_rev_adap",
                ]
            )

            # Determine if merged-read adapters
            # need to be counted (4th field is None)
            need_merged_read = (
                sequencer_record.fwd_rev_mrg_adap is None
                and reverse_primer_revcomp
            )

            # If nothing to do, skip
            if not (need_single_read or need_merged_read):
                logger.info("Adapters already counted, skipping.")
                return

            # Find matching forward and reverse files as before
            files_of_sequencer = (
                session.query(SequencingFilesUploadedTable)
                .filter_by(sequencerId=sequencer_id["id"])
                .all()
            )
            filenames = [f.new_name for f in files_of_sequencer]

            pattern = re.compile(r"(.+)_1(_\d+.*\.fastq(?:\.gz)?)$")
            forward_file = None
            reverse_file = None

            for fname in filenames:
                m = pattern.match(fname)
                if m:
                    base = m.group(1)
                    suffix = m.group(2)
                    rev_fname = f"{base}_2{suffix}"
                    if rev_fname in filenames:
                        forward_file = fname
                        reverse_file = rev_fname
                        break

            if not (forward_file and reverse_file):
                logger.warning(
                    "Could not find matching pair"
                    " of forward and reverse files."
                )
                return

            file_1_path = os.path.join(
                "seq_processed", process_folder, forward_file
            )
            file_2_path = os.path.join(
                "seq_processed", process_folder, reverse_file
            )

            # Run single-read adapter counting if needed
            if need_single_read:
                try:
                    cutadapt_log = detect_single_read_primers(
                        file_1_path=file_1_path,
                        file_2_path=file_2_path,
                        forward_primer_seq=forward_primer,
                        reverse_primer_seq=reverse_primer,
                    )
                except RuntimeError as e:
                    logger.error(f"Cutadapt single-read detection failed: {e}")
                    return

                reads = parse_detect_single_read_primers_output(cutadapt_log)

                if reads.get("read1_with_adapter") is not None:
                    sequencer_record.fwd_read_fwd_adap = reads[
                        "read1_with_adapter"
                    ]
                if reads.get("read2_with_adapter") is not None:
                    sequencer_record.rev_read_rev_adap = reads[
                        "read2_with_adapter"
                    ]
                if reads.get("pairs_written") is not None:
                    sequencer_record.fwd_rev_adap = reads["pairs_written"]

                session.commit()

            # Run merged-read adapter counting if needed
            if need_merged_read:
                try:
                    merged_log = detect_merged_read_primers(
                        file_1_path=file_1_path,
                        file_2_path=file_2_path,
                        forward_primer_seq=forward_primer,
                        reverse_primer_seq=reverse_primer_revcomp,
                    )
                except RuntimeError as e:
                    logger.error(f"Cutadapt merged-read detection failed: {e}")
                    return

                merged_reads = parse_detect_merged_read_primers_output(
                    merged_log
                )

                if merged_reads is not None:
                    sequencer_record.fwd_rev_mrg_adap = merged_reads

                session.commit()
