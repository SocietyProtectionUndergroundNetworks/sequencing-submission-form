import datetime
import random
import string
import logging
import os
import json
import shutil
import csv
import re
import pandas as pd
from collections import defaultdict
from helpers.dbm import session_scope
from helpers.fastqc import init_create_fastqc_report, check_fastqc_report
from helpers.metadata_check import (
    get_sequences_based_on_primers,
)
from helpers.bucket import check_file_exists_in_bucket, calculate_md5
from models.db_model import (
    ResolveEcoregionsTable,
    SequencingUploadsTable,
    SequencingSamplesTable,
    SequencingSequencerIDsTable,
    SequencingFilesUploadedTable,
    SequencingAnalysisTable,
    SequencingAnalysisTypesTable,
    Taxonomy,
    UserTable,
    OTU,
)
from models.sequencing_analysis import SequencingAnalysis
from models.taxonomy import TaxonomyManager
from models.sequencing_analysis_type import SequencingAnalysisType
from models.sequencing_files_uploaded import SequencingFileUploaded
from helpers.bucket import init_bucket_chunked_upload_v2
from pathlib import Path
from flask_login import current_user
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc, func, text


# Get the logger instance from app.py
logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class SequencingUpload:
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.nr_files_per_sequence = 2
        self.regions = []

    @classmethod
    def get(cls, id):
        with session_scope() as session:

            upload_db = (
                session.query(SequencingUploadsTable).filter_by(id=id).first()
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

            # Create an instance of SequencingUpload using the dictionary
            upload = cls(**filtered_dict)

            upload.nr_files_per_sequence = cls.determine_nr_files_per_sequence(
                filtered_dict["Sequencing_platform"]
            )

            # Calculate the number of regions
            upload.nr_regions = 0
            upload.regions = []
            if upload.region_1 is not None:
                upload.nr_regions += 1
                upload.regions.append(upload.region_1)
            if upload.region_2 is not None:
                upload.nr_regions += 1
                upload.regions.append(upload.region_2)

            # Convert the instance to a dictionary
            # including the custom attribute
            upload_dict = upload.__dict__

            return upload_dict

    @classmethod
    def get_all(cls, user_id=None):
        with session_scope() as session:

            query = session.query(SequencingUploadsTable, UserTable).join(
                UserTable, SequencingUploadsTable.user_id == UserTable.id
            )

            if user_id is not None:
                query = query.filter(SequencingUploadsTable.user_id == user_id)

            upload_dbs = query.order_by(desc(SequencingUploadsTable.id)).all()

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

                upload.nr_files_per_sequence = (
                    cls.determine_nr_files_per_sequence(
                        filtered_dict["Sequencing_platform"]
                    )
                )

                # Calculate the total size of the uploads folder and
                # count the fastq files
                upload.total_uploads_file_size = 0
                upload.nr_fastq_files = 0
                uploads_folder = filtered_dict["uploads_folder"]
                if uploads_folder:
                    total_size, fastq_count = cls.get_directory_size(
                        os.path.join("seq_processed", uploads_folder)
                    )
                    upload.total_uploads_file_size = total_size
                    upload.nr_fastq_files = fastq_count

                # Calculate the number of regions
                upload.nr_regions = 0
                upload.regions = []
                if upload.region_1 is not None:
                    upload.nr_regions += 1
                    upload.regions.append(upload.region_1)
                if upload.region_2 is not None:
                    upload.nr_regions += 1
                    upload.regions.append(upload.region_2)

                # Count the number of samples associated with this upload
                nr_samples = (
                    session.query(SequencingSamplesTable)
                    .filter_by(sequencingUploadId=filtered_dict["id"])
                    .count()
                )
                upload.nr_samples = nr_samples

                analysis_all = SequencingAnalysis.get_by_upload(upload.id)

                # Extract the analysis type IDs from the
                # existing analyses for easier lookup
                existing_analysis_type_ids = {
                    analysis["analysisTypeId"] for analysis in analysis_all
                }

                # Initialize the analysis structure grouped by region
                upload.analysis = {}

                for region in upload.regions:
                    if uploads_folder:
                        # Get the required analyses for the current region
                        required_analyses = (
                            SequencingAnalysisType.get_all_by_region(region)
                        )

                        # Initialize a list to store analyses
                        # for the current region
                        region_analyses = []

                        # Because plural of analysis had to
                        # be so close as to be confusing!
                        for required_one_analysis in required_analyses:

                            # Set up the basic structure for the analysis item
                            upload_required_analysis = {
                                "analysis_type_id": required_one_analysis[
                                    "id"
                                ],
                                "analysis_id": None,
                                "analysis_type_name": required_one_analysis[
                                    "name"
                                ],
                                "lotus2_status": None,
                                "lotus2_phyloseq_file_exists": False,
                                "rscripts_status": None,
                                "rscripts_phyloseq_file_exists": False,
                                "richness_file_exists": False,
                            }

                            if (
                                required_one_analysis["id"]
                                in existing_analysis_type_ids
                            ):
                                # Find the corresponding existing
                                # analysis to get the status
                                matching_analysis = next(
                                    (
                                        a
                                        for a in analysis_all
                                        if a["analysisTypeId"]
                                        == required_one_analysis["id"]
                                    ),
                                    None,
                                )

                                # If a match is found, set the status
                                if matching_analysis:
                                    upload_required_analysis[
                                        "lotus2_status"
                                    ] = matching_analysis["lotus2_status"]
                                    upload_required_analysis[
                                        "rscripts_status"
                                    ] = matching_analysis["rscripts_status"]
                                    upload_required_analysis["analysis_id"] = (
                                        matching_analysis["id"]
                                    )

                            # Construct the phyloseq file path for lotus2 and
                            # check if it exists
                            lotus2_phyloseq_file = os.path.join(
                                "seq_processed",
                                uploads_folder,
                                "lotus2_report",
                                required_one_analysis["name"],
                                "phyloseq.Rdata",
                            )
                            upload_required_analysis[
                                "lotus2_phyloseq_file_exists"
                            ] = os.path.isfile(lotus2_phyloseq_file)

                            # Construct the phyloseq file path
                            # for rscripts and check if it exists
                            rscripts_phyloseq_file = os.path.join(
                                "seq_processed",
                                uploads_folder,
                                "r_output",
                                required_one_analysis["name"],
                                "physeq_decontam.Rdata",
                            )
                            upload_required_analysis[
                                "rscripts_phyloseq_file_exists"
                            ] = os.path.isfile(rscripts_phyloseq_file)

                            richness_file = os.path.join(
                                "seq_processed",
                                uploads_folder,
                                "r_output",
                                required_one_analysis["name"],
                                "metadata_chaorichness.csv",
                            )
                            upload_required_analysis[
                                "richness_file_exists"
                            ] = os.path.isfile(richness_file)

                            # Append this analysis to the current region's list
                            region_analyses.append(upload_required_analysis)

                        # Store the analyses for this region in
                        # the main upload analysis structure
                        upload.analysis[region] = region_analyses

                # Count the number of sequencer IDs associated with this upload
                nr_sequencer_ids = (
                    session.query(SequencingSequencerIDsTable)
                    .join(
                        SequencingSamplesTable,
                        SequencingSamplesTable.id
                        == SequencingSequencerIDsTable.sequencingSampleId,
                    )
                    .filter(
                        SequencingSamplesTable.sequencingUploadId
                        == filtered_dict["id"]
                    )
                    .count()
                )
                upload.nr_sequencer_ids = nr_sequencer_ids

                # Add user name and email to the upload dictionary
                upload.user_name = user_dict["name"]
                upload.user_email = user_dict["email"]

                upload_dict = upload.__dict__
                uploads.append(upload_dict)

            return uploads

    @staticmethod
    def get_directory_size(directory):
        total_size = 0
        fastq_count = 0
        for dirpath, dirnames, filenames in os.walk(directory):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if os.path.isfile(fp):
                    total_size += os.path.getsize(fp)
                    if f.endswith(".fastq.gz") or f.endswith(".fastq"):
                        fastq_count += 1
        return total_size, fastq_count

    @staticmethod
    def determine_nr_files_per_sequence(sequencing_platform):
        sequencers_expecting_pairs = [
            "Illumina NextSeq",
            "Illumina MiSeq",
            "Illumina NovaSeq",
            "Element Biosciences AVITI",
            "Other",
        ]

        # Strip whitespace
        sequencing_platform = sequencing_platform.strip()

        if sequencing_platform in sequencers_expecting_pairs:
            return 2
        return 1

    @classmethod
    def get_region(cls, forward_primer, reverse_primer):
        current_dir = os.path.dirname(__file__)
        base_dir = os.path.abspath(os.path.join(current_dir, os.pardir))
        regions_file_path = os.path.join(
            base_dir, "metadataconfig", "primer_set_regions.json"
        )

        # Load the JSON file
        with open(regions_file_path, "r") as f:
            primer_set_region = json.load(f)

        # Create a reverse lookup dictionary from primers to region names
        primer_to_region = {
            (key): value["Region"] for key, value in primer_set_region.items()
        }

        # Combine forward and reverse primer
        primer_set = f"{forward_primer}/{reverse_primer}"

        # Return the corresponding region if it exists
        return primer_to_region.get(primer_set, None)

    @classmethod
    def get_regions(
        cls,
        region_1_forward_primer=None,
        region_1_reverse_primer=None,
        region_2_forward_primer=None,
        region_2_reverse_primer=None,
    ):
        # Initialize a list to keep regions in order
        regions = []
        # Check for empty string primers and return "Other" region
        if region_1_forward_primer == "" and region_1_reverse_primer == "":
            regions.append("Other")
        elif region_1_forward_primer and region_1_reverse_primer:
            region_1 = cls.get_region(
                region_1_forward_primer, region_1_reverse_primer
            )
            if region_1:
                regions.append(region_1)

        if region_2_forward_primer == "" and region_2_reverse_primer == "":
            regions.append("Other")
        elif region_2_forward_primer and region_2_reverse_primer:
            region_2 = cls.get_region(
                region_2_forward_primer, region_2_reverse_primer
            )
            if region_2:
                regions.append(region_2)

        # Return the regions in the order they were added
        return regions

    @classmethod
    def get_samples(self, sequencingUploadId):
        # Connect to the database and create a session
        with session_scope() as session:

            # Fetch related samples
            samples = (
                session.query(
                    SequencingSamplesTable,
                    ResolveEcoregionsTable.ecoregion_name.label(
                        "ResolveEcoregion"
                    ),
                )
                .outerjoin(
                    ResolveEcoregionsTable,
                    SequencingSamplesTable.resolve_ecoregion_id
                    == ResolveEcoregionsTable.id,
                )
                .filter(
                    SequencingSamplesTable.sequencingUploadId
                    == sequencingUploadId
                )
                .all()
            )

            # Define the as_dict method within this function
            def as_dict(instance):
                """Convert SQLAlchemy model instance to a dictionary."""
                return {
                    column.name: getattr(instance, column.name)
                    for column in instance.__table__.columns
                }

            # Convert each sample instance to a dictionary and add otu_counts
            samples_list = []
            for sample, ecoregion_name in samples:  # ✅ Unpack tuple properly
                sample_data = as_dict(sample)  # Convert sample to dictionary
                sample_data["ResolveEcoregion"] = (
                    ecoregion_name  # Add ecoregion text
                )

                sample_id = sample_data.get("id")  # Get the sample id
                otu_counts = {}

                # Query to get the counts grouped by analysis
                # type name and analysis_type_id
                counts = (
                    session.query(
                        SequencingAnalysisTypesTable.name,
                        func.count(Taxonomy.id),
                        SequencingAnalysisTypesTable.id,
                    )
                    .join(OTU, OTU.taxonomy_id == Taxonomy.id)
                    .join(
                        SequencingAnalysisTable,
                        SequencingAnalysisTable.id
                        == OTU.sequencing_analysis_id,
                    )
                    .join(
                        SequencingAnalysisTypesTable,
                        SequencingAnalysisTypesTable.id
                        == SequencingAnalysisTable.sequencingAnalysisTypeId,
                    )
                    .filter(OTU.sample_id == sample_id)
                    .group_by(
                        SequencingAnalysisTypesTable.name,
                        SequencingAnalysisTypesTable.id,
                    )
                    .all()
                )

                # Populate the otu_counts dictionary
                for analysis_name, count, analysis_type_id in counts:
                    otu_counts[analysis_type_id] = {
                        "name": analysis_name,
                        "count": count,
                    }

                # Add the otu_counts dictionary to the sample data
                sample_data["otu_counts"] = otu_counts

                # Append the updated sample data to the list
                samples_list.append(sample_data)

            return samples_list

    @classmethod
    def create(cls, datadict):
        with session_scope() as session:

            # Create a new instance of SequencingUploadsTable
            new_upload = SequencingUploadsTable(
                user_id=current_user.id,
            )

            if datadict["using_scripps"] == "yes":
                datadict["region_1_forward_primer"] = "ITS3"
                datadict["region_1_reverse_primer"] = "ITS4"
                datadict["region_2_forward_primer"] = "WANDA"
                datadict["region_2_reverse_primer"] = "AML2"
                datadict["region_1"] = "ITS2"
                datadict["region_2"] = "SSU"
                datadict["Sequencing_platform"] = "Element Biosciences AVITI"
                datadict["Sequencing_facility"] = "Scripps Research"
            else:
                datadict["region_1"] = cls.get_region(
                    datadict["region_1_forward_primer"],
                    datadict["region_1_reverse_primer"],
                )

            if (
                datadict["region_2_forward_primer"] == "0"
                and datadict["region_2_reverse_primer"] == "0"
            ):
                datadict["Sequencing_regions_number"] = 1
            else:
                datadict["Sequencing_regions_number"] = 2
                datadict["region_2"] = cls.get_region(
                    datadict["region_2_forward_primer"],
                    datadict["region_2_reverse_primer"],
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

            path = Path("seq_uploads", uploads_folder)
            path.mkdir(parents=True, exist_ok=True)

            new_upload.uploads_folder = uploads_folder
            session.commit()

            return new_upload_id

    @classmethod
    def get_sequencer_ids(self, sequencingUploadId):
        # Connect to the database and create a session
        with session_scope() as session:

            # Query to get all SequencingSequencerIDsTable
            # entries associated with the given process_id
            sequencer_ids = (
                session.query(SequencingSequencerIDsTable)
                .join(SequencingSamplesTable)
                .join(SequencingUploadsTable)
                .filter(SequencingUploadsTable.id == sequencingUploadId)
                .all()
            )

            # Define the as_dict method within this function
            def as_dict(instance):
                """Convert SQLAlchemy model instance to a dictionary."""
                return {
                    column.name: getattr(instance, column.name)
                    for column in instance.__table__.columns
                }

            # Convert each sample instance to a dictionary
            sequencer_ids_list = [
                as_dict(sequencer_id) for sequencer_id in sequencer_ids
            ]

            return sequencer_ids_list

    @classmethod
    def mark_upload_confirmed_as_true(cls, process_id):
        with session_scope() as session:

            upload = (
                session.query(SequencingUploadsTable)
                .filter_by(id=process_id)
                .first()
            )

            if upload:
                upload.metadata_upload_confirmed = True
                session.commit()
                return True
            else:
                return False

    @classmethod
    def mark_upload_confirmed_as_false(cls, process_id):
        with session_scope() as session:

            upload = (
                session.query(SequencingUploadsTable)
                .filter_by(id=process_id)
                .first()
            )

            if upload:
                upload.metadata_upload_confirmed = False
                session.commit()
                return True
            else:
                return False

    @classmethod
    def validate_samples(cls, id):
        with session_scope() as session:

            # Get the upload instance
            upload = (
                session.query(SequencingUploadsTable).filter_by(id=id).first()
            )
            if not upload:
                return False  # Upload not found

            # Query to get all samples and their sequencer IDs
            samples = (
                session.query(SequencingSamplesTable)
                .options(joinedload(SequencingSamplesTable.sequencer_ids))
                .filter_by(sequencingUploadId=id)
                .all()
            )

            upload = cls.get(id)

            nr_files_per_sequence = cls.determine_nr_files_per_sequence(
                upload["Sequencing_platform"]
            )

            regions = [upload["region_1"], upload["region_2"]]

            for sample in samples:
                sequencer_ids = (
                    sample.sequencer_ids
                )  # Assuming `sequencer_ids` is a relationship
                if len(sequencer_ids) != nr_files_per_sequence:
                    return False  # Incorrect number of sequencer IDs

                sample_regions = {
                    sid.Region for sid in sequencer_ids if sid.Region
                }
                if not sample_regions.issubset(set(regions)):
                    return False  # Incorrect regions

            return True

    @classmethod
    def get_missing_ssu_files(cls, sequencingUploadId):
        query = text(
            """
        SELECT ss.id, ss.SampleID
        FROM sequencing_samples AS ss
        WHERE ss.sequencingUploadId = :sequencingUploadId
        AND ss.id NOT IN (
            SELECT ss.id
            FROM sequencing_samples AS ss
            JOIN sequencing_sequencer_ids
                AS ssi ON ssi.sequencingSampleId = ss.id
            JOIN sequencing_files_uploaded
                AS sfu ON sfu.sequencerId = ssi.id
            WHERE ss.sequencingUploadId = :sequencingUploadId
            AND ssi.Region IN ('SSU')
            GROUP BY ss.id
        )
        """
        )
        with session_scope() as session:
            results = session.execute(
                query, {"sequencingUploadId": sequencingUploadId}
            ).fetchall()

        return results

    @classmethod
    def get_missing_its_files(cls, sequencingUploadId):
        query = text(
            """
        SELECT ss.id, ss.SampleID
        FROM sequencing_samples AS ss
        WHERE ss.sequencingUploadId = :sequencingUploadId
        AND ss.id NOT IN (
            SELECT ss.id
            FROM sequencing_samples AS ss
            JOIN sequencing_sequencer_ids
                AS ssi ON ssi.sequencingSampleId = ss.id
            JOIN sequencing_files_uploaded
                AS sfu ON sfu.sequencerId = ssi.id
            WHERE ss.sequencingUploadId = :sequencingUploadId
            AND ssi.Region IN ('ITS1', 'ITS2')
            GROUP BY ss.id
        )
        """
        )
        with session_scope() as session:
            results = session.execute(
                query, {"sequencingUploadId": sequencingUploadId}
            ).fetchall()

        return results

    @classmethod
    def get_uploaded_files(cls, sequencingUploadId):
        # Connect to the database and create a session
        with session_scope() as session:

            # Fetch the SequencingUpload instance
            upload_instance = (
                session.query(SequencingUploadsTable)
                .filter_by(id=sequencingUploadId)
                .first()
            )

            # If no instance is found, return an empty result
            # or handle the case as needed
            if not upload_instance:
                return []

            # Access the 'bucket' and 'uploads_folder' fields
            uploads_folder = upload_instance.uploads_folder

            # Query to get all SequencingFilesUploadedTable entries
            # associated with the given sequencingUploadId
            uploaded_files = (
                session.query(
                    SequencingFilesUploadedTable,  # Select the files
                    SequencingSamplesTable.id.label(
                        "sample_id"
                    ),  # Select the corresponding sample_id
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
                .filter(
                    SequencingSamplesTable.sequencingUploadId
                    == sequencingUploadId
                )
                .all()
            )

            # Define the as_dict method within this function
            def as_dict(instance):
                """Convert SQLAlchemy model instance to a dictionary."""
                return {
                    column.name: getattr(instance, column.name)
                    for column in instance.__table__.columns
                }

            # Convert each file instance and sample_id to a dictionary
            uploaded_files_list = [
                {
                    **as_dict(file),  # File data
                    "sample_id": sample_id,  # Include the sample_id
                    "region": region,
                    "fastqc_report": check_fastqc_report(
                        file.new_name, region, uploads_folder
                    ),  # Include the fastqc_report
                }
                for file, sample_id, region in uploaded_files
            ]

            return uploaded_files_list

    @classmethod
    def get_by_user_id(cls, user_id):
        with session_scope() as session:

            # Query to get the IDs of uploads for the given user_id
            uploads = (
                session.query(SequencingUploadsTable.id)
                .filter_by(user_id=user_id)
                .all()
            )

            # Extract the upload IDs from the query results
            upload_ids = [upload.id for upload in uploads]

            return upload_ids if upload_ids else []

    @classmethod
    def delete_upload_and_files(cls, upload_id):
        with session_scope() as session:

            upload_db = (
                session.query(SequencingUploadsTable)
                .filter_by(id=upload_id)
                .first()
            )
            if not upload_db:
                logger.error(f"No upload found with id {upload_id}")
                return

            if upload_db.uploads_folder:
                uploads_directory = Path("uploads", upload_db.uploads_folder)
                extract_directory = Path(
                    "processing", upload_db.uploads_folder
                )

                try:
                    shutil.rmtree(uploads_directory)
                    logger.info(
                        "Directory '{}' and its contents "
                        "deleted successfully.".format(uploads_directory)
                    )
                except Exception as e:
                    logger.error(
                        f"Error deleting directory '{uploads_directory}': {e}"
                    )

                try:
                    shutil.rmtree(extract_directory)
                    logger.info(
                        f"Directory '{extract_directory}'"
                        f" and contents deleted."
                    )
                except Exception as e:
                    logger.error(
                        f"Error deleting directory '{extract_directory}': {e}"
                    )

            try:
                session.delete(upload_db)
                session.commit()
                logger.info(
                    f"Upload record with id {upload_id} deleted successfully."
                )
            except SQLAlchemyError as e:
                session.rollback()
                logger.error(f"Error deleting upload record: {e}")

    @classmethod
    def check_missing_sequencer_ids(cls, process_id):
        """
        Checks if any related sampleID does not have a
        sequencerID for one of its regions.
        Returns a list of sample IDs with missing sequencer IDs.
        """
        # Connect to the database and create a session
        with session_scope() as session:

            # Retrieve the SequencingUpload instance
            # to get Sequencing_regions_number
            upload_instance = (
                session.query(SequencingUploadsTable)
                .filter_by(id=process_id)
                .first()
            )

            if not upload_instance:
                raise ValueError(
                    f"No SequencingUpload found with ID: {process_id}"
                )

            # Get the number of regions from the SequencingUpload instance
            expected_regions_number = upload_instance.Sequencing_regions_number

            # Query to get all samples related to the given process_id
            samples = (
                session.query(SequencingSamplesTable)
                .join(SequencingUploadsTable)
                .filter(SequencingUploadsTable.id == process_id)
                .all()
            )

            # List to store samples with missing sequencer IDs
            samples_with_missing_ids = []

            # Iterate over each sample and check the number of sequencer IDs
            for sample in samples:
                # Query to get all sequencer IDs associated with this sample
                sequencer_ids = (
                    session.query(SequencingSequencerIDsTable)
                    .filter(
                        SequencingSequencerIDsTable.sequencingSampleId
                        == sample.id
                    )
                    .all()
                )

                # Check if the number of sequencer IDs matches
                # the expected number of regions
                if len(sequencer_ids) < expected_regions_number:
                    # If not, add the sample ID to the list
                    samples_with_missing_ids.append(sample.id)

            # Return the list of sample IDs with missing sequencer IDs
            return samples_with_missing_ids

    @classmethod
    def get_samples_with_sequencers_and_files(self, sequencingUploadId):
        # Connect to the database and create a session
        with session_scope() as session:

            # Fetch the SequencingUpload instance
            upload_instance = (
                session.query(SequencingUploadsTable)
                .filter_by(id=sequencingUploadId)
                .first()
            )

            # If no instance is found, return an empty result or handle
            # the case as needed
            if not upload_instance:
                return []

            # Access the 'project' field
            uploads_folder = upload_instance.uploads_folder

            # Fetch related samples
            samples = (
                session.query(SequencingSamplesTable)
                .filter_by(sequencingUploadId=sequencingUploadId)
                .all()
            )

            # Fetch related sequencer IDs
            sequencer_ids = (
                session.query(SequencingSequencerIDsTable)
                .join(SequencingSamplesTable)
                .filter(
                    SequencingSamplesTable.sequencingUploadId
                    == sequencingUploadId
                )
                .all()
            )

            # Fetch related uploaded files
            uploaded_files = (
                session.query(
                    SequencingFilesUploadedTable,  # Select the files
                    SequencingSamplesTable.id.label(
                        "sample_id"
                    ),  # Select the corresponding sample_id
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
                .filter(
                    SequencingSamplesTable.sequencingUploadId
                    == sequencingUploadId
                )
                .all()
            )

            # Convert the fetched data to dictionaries
            def as_dict(instance):
                """Convert SQLAlchemy model instance to a dictionary."""
                return {
                    column.name: getattr(instance, column.name)
                    for column in instance.__table__.columns
                }

            samples_dict = {sample.id: as_dict(sample) for sample in samples}
            sequencer_ids_dict = {}
            for sequencer in sequencer_ids:
                sample_id = sequencer.sequencingSampleId
                if sample_id not in sequencer_ids_dict:
                    sequencer_ids_dict[sample_id] = []
                sequencer_ids_dict[sample_id].append(as_dict(sequencer))

            uploaded_files_dict = {}
            for file, sample_id, region in uploaded_files:

                # Check if the FastQC report exists
                fastqc_report = check_fastqc_report(
                    file.new_name, region, uploads_folder
                )
                if fastqc_report:
                    # Check if the total_sequences_number is updated
                    if not file.total_sequences_number:
                        SequencingFileUploaded.update_total_sequences(file.id)

                sequencer_id = file.sequencerId
                if sample_id not in uploaded_files_dict:
                    uploaded_files_dict[sample_id] = {}
                if sequencer_id not in uploaded_files_dict[sample_id]:
                    uploaded_files_dict[sample_id][sequencer_id] = []

                # Convert the file to a dictionary and
                # add the fastqc_report field
                file_dict = as_dict(file)
                file_dict["fastqc_report"] = fastqc_report

                # Append the file dictionary with the fastqc_report to the list
                uploaded_files_dict[sample_id][sequencer_id].append(file_dict)

            # Combine the data into a structured list
            result = []
            for sample_id, sample_data in samples_dict.items():
                sample_data["sequencer_ids"] = sequencer_ids_dict.get(
                    sample_id, []
                )

                for sequencer in sample_data["sequencer_ids"]:
                    sequencer_id = sequencer["id"]
                    sequencer["uploaded_files"] = uploaded_files_dict.get(
                        sample_id, {}
                    ).get(sequencer_id, [])

                result.append(sample_data)

            return result

    @classmethod
    def ensure_fastqc_reports(self, sequencingUploadId):
        # Connect to the database and create a session
        with session_scope() as session:

            # Fetch the SequencingUpload instance
            upload_instance = (
                session.query(SequencingUploadsTable)
                .filter_by(id=sequencingUploadId)
                .first()
            )

            # If no instance is found, return early
            if not upload_instance:
                return

            # Access the 'project' field
            bucket = upload_instance.project_id
            uploads_folder = upload_instance.uploads_folder

            # Fetch related uploaded files
            uploaded_files = (
                session.query(
                    SequencingFilesUploadedTable,
                    SequencingSamplesTable.id.label("sample_id"),
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
                .filter(
                    SequencingSamplesTable.sequencingUploadId
                    == sequencingUploadId
                )
                .all()
            )

            # Iterate through the files and check for FastQC reports
            for file, sample_id, region in uploaded_files:
                # Check if the FastQC report exists
                fastqc_report = check_fastqc_report(
                    file.new_name, region, uploads_folder
                )

                # If the report is missing, create it
                if not fastqc_report:
                    processed_folder = f"seq_processed/{uploads_folder}"
                    init_create_fastqc_report(
                        file.new_name, processed_folder, bucket, region
                    )

    @classmethod
    def ensure_bucket_upload_progress(self, sequencingUploadId):
        # Connect to the database and create a session
        with session_scope() as session:

            # Fetch the SequencingUpload instance
            upload_instance = (
                session.query(SequencingUploadsTable)
                .filter_by(id=sequencingUploadId)
                .first()
            )

            # If no instance is found, return early
            if not upload_instance:
                return

            # Access the 'project' field
            bucket = upload_instance.project_id
            uploads_folder = upload_instance.uploads_folder

            # Fetch related uploaded files
            uploaded_files = (
                session.query(
                    SequencingFilesUploadedTable,
                    SequencingSamplesTable.id.label("sample_id"),
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
                .filter(
                    SequencingSamplesTable.sequencingUploadId
                    == sequencingUploadId
                )
                .all()
            )

            # Iterate through the files and check the bucket_upload_progress
            for file, sample_id, region in uploaded_files:
                if (
                    not file.bucket_upload_progress
                    or file.bucket_upload_progress < 100
                ):
                    # Construct the local path to the processed file
                    processed_file_path = (
                        f"seq_processed/{uploads_folder}/{file.new_name}"
                    )

                    # Calculate MD5 if it is null
                    if not file.md5:
                        file.md5 = calculate_md5(
                            processed_file_path
                        )  # Calculate MD5
                        # Update the md5 field in the database
                        session.commit()  # Commit the change to the database

                    # Start the chunked upload to the bucket
                    init_bucket_chunked_upload_v2(
                        local_file_path=processed_file_path,
                        destination_upload_directory=region,
                        destination_blob_name=file.new_name,
                        sequencer_file_id=file.id,
                        bucket_name=bucket,
                        known_md5=file.md5,  # Pass the calculated MD5
                    )

    @classmethod
    def update_field(cls, id, fieldname, value):
        with session_scope() as session:

            # Fetch the existing record
            upload_db = (
                session.query(SequencingUploadsTable).filter_by(id=id).first()
            )

            if not upload_db:
                return None

            # Update the specified field
            setattr(upload_db, fieldname, value)

            # Commit the changes
            session.commit()

            return True

    @classmethod
    def generate_mapping_files_for_process(self, process_id, mode):

        def sanitize_mapping_string(value):
            if value is None:
                return "NA"  # Or any default value
            sanitized = re.sub(
                r"\s+", "_", value.strip()
            )  # Replace spaces with underscores
            sanitized = re.sub(
                r"[^\w\-_]", "", sanitized
            )  # Remove unwanted characters
            return sanitized

        samples_data_complete = self.get_samples_with_sequencers_and_files(
            process_id
        )
        process_data = self.get(process_id)
        uploads_folder = process_data["uploads_folder"]
        bucket = process_data["project_id"]
        sample_country = sanitize_mapping_string(process_data["Country"])

        # Dictionary to hold data organized by region
        region_data = defaultdict(list)

        # Get the primer sequences for regions
        region_1_sequences = get_sequences_based_on_primers(
            process_data["region_1_forward_primer"],
            process_data["region_1_reverse_primer"],
        )
        region_2_sequences = get_sequences_based_on_primers(
            process_data["region_2_forward_primer"],
            process_data["region_2_reverse_primer"],
        )

        region_dict = {}
        if region_1_sequences:
            region_dict[region_1_sequences["Region"]] = {
                "Forward Primer": region_1_sequences["Forward Primer"],
                "Reverse Primer": region_1_sequences["Reverse Primer"],
            }
        if region_2_sequences:
            region_dict[region_2_sequences["Region"]] = {
                "Forward Primer": region_2_sequences["Forward Primer"],
                "Reverse Primer": region_2_sequences["Reverse Primer"],
            }

        sample_info = {}

        # Process each sample data
        for sample_data in samples_data_complete:
            sample_id = sample_data["SampleID"]
            site_name = sanitize_mapping_string(sample_data["Site_name"])
            latitude = sample_data["Latitude"]
            longitude = sample_data["Longitude"]
            vegetation = sanitize_mapping_string(sample_data["Vegetation"])
            land_use = sanitize_mapping_string(sample_data["Land_use"])
            ecosystem = sanitize_mapping_string(sample_data["Ecosystem"])
            sample_or_control = sample_data["Sample_or_Control"]

            # Initialize sample_info dictionary if not already
            if sample_id not in sample_info:
                sample_info[sample_id] = {
                    "site_name": site_name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "vegetation": vegetation,
                    "land_use": land_use,
                    "ecosystem": ecosystem,
                    "sample_or_control": sample_or_control,
                    "files": defaultdict(list),  # Accumulate files by region
                }

            # Check if there are sequencers and uploaded files
            if "sequencer_ids" in sample_data:
                for sequencer in sample_data["sequencer_ids"]:
                    region = sequencer["Region"]

                    sequencing_run = sequencer.get("sequencing_run")
                    if not sequencing_run:
                        sequencing_run = "Run_1"

                    if "uploaded_files" in sequencer:
                        paired_files = []
                        for file_data in sequencer["uploaded_files"]:
                            fastq_file = file_data["new_name"]
                            exclude_from_mapping = file_data.get(
                                "exclude_from_mapping", False
                            )

                            # Only accumulate files that are not excluded
                            if not exclude_from_mapping:
                                paired_files.append(fastq_file)

                        # Sort filenames alphabetically
                        paired_files = sorted(paired_files)

                        # Process files based on the mode
                        if mode == "only_forward":
                            # Always select the first file after sorting
                            if paired_files:
                                sample_info[sample_id]["files"][region].append(
                                    paired_files[0]
                                )
                        else:
                            # Ensure files are in pairs (forward and reverse)
                            if len(paired_files) == 2:
                                sample_info[sample_id]["files"][region].extend(
                                    paired_files
                                )

        # Create directory for output files if it doesn't exist
        output_dir = f"seq_processed/{uploads_folder}/mapping_files/"
        os.makedirs(output_dir, exist_ok=True)

        # Write files for each region
        for sample_id, info in sample_info.items():
            site_name = info["site_name"]
            latitude = info["latitude"]
            longitude = info["longitude"]
            vegetation = info["vegetation"]
            land_use = info["land_use"]
            ecosystem = info["ecosystem"]
            sample_or_control = info["sample_or_control"]
            if sample_or_control in ["True sample", "True Sample"]:
                sample_or_control = "sample"

            # Process files for each region
            for region, files in info["files"].items():
                # Sort filenames alphabetically and join with commas
                sorted_files = sorted(files)

                fastq_files_combined = ",".join(sorted_files)

                forward_primer = region_dict[region]["Forward Primer"]
                reverse_primer = region_dict[region]["Reverse Primer"]

                # If Sample_or_Control is "Control"
                # set the relevant fields to empty strings
                if sample_or_control == "Control":
                    latitude = ""
                    longitude = ""
                    sample_country = ""
                    vegetation = ""
                    land_use = ""
                    ecosystem = ""

                # Add row to region data
                region_data[region].append(
                    [
                        sample_id,
                        fastq_files_combined,
                        forward_primer,
                        reverse_primer,
                        site_name,
                        latitude,
                        longitude,
                        sample_country,
                        vegetation,
                        land_use,
                        ecosystem,
                        sample_or_control,
                        sequencing_run,
                    ]
                )

        # Write each region's data to a TSV file
        for region, rows in region_data.items():
            mapping_filename = f"{region}_Mapping.txt"
            output_file_path = os.path.join(output_dir, mapping_filename)
            with open(output_file_path, "w", newline="") as file:
                writer = csv.writer(file, delimiter="\t")
                writer.writerow(
                    [
                        "#SampleID",
                        "fastqFile",
                        "ForwardPrimer",
                        "ReversePrimer",
                        "Site_name",
                        "Latitude",
                        "Longitude",
                        "Country",
                        "Vegetation",
                        "Land_use",
                        "Ecosystem",
                        "Sample_or_Control",
                        "SequencingRun",
                    ]
                )
                writer.writerows(rows)

            # Copy the file to the correct bucket and folder
            init_bucket_chunked_upload_v2(
                local_file_path=output_file_path,
                destination_upload_directory=None,
                destination_blob_name=mapping_filename,
                sequencer_file_id=None,
                bucket_name=bucket,
                known_md5=None,
            )

        return []

    @classmethod
    def export_sample_locations(cls, process_id):
        # Fetch sample data for the process ID
        samples_data_complete = cls.get_samples_with_sequencers_and_files(
            process_id
        )

        # Extract only the required fields: sample_id, latitude, longitude
        sample_locations = [
            {
                "sample_id": sample_data["SampleID"],
                "latitude": sample_data.get("Latitude", "NA"),
                "longitude": sample_data.get("Longitude", "NA"),
            }
            for sample_data in samples_data_complete
        ]

        # Create output directory if it doesn't exist
        process_data = cls.get(process_id)
        uploads_folder = process_data["uploads_folder"]
        output_dir = f"seq_processed/{uploads_folder}/metadata/"
        os.makedirs(output_dir, exist_ok=True)

        # Define the output CSV file path
        output_file_path = os.path.join(output_dir, "sample_locations.csv")

        # Write the data to the CSV file
        with open(output_file_path, "w", newline="") as csvfile:
            fieldnames = ["sample_id", "latitude", "longitude"]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

            # Write the header row
            writer.writeheader()

            # Write the sample location data
            writer.writerows(sample_locations)

        # Return the path of the generated file
        return output_file_path

    @classmethod
    def check_mapping_files_exist(self, process_id):
        process_data = self.get(process_id)

        # Extract uploads folder and project id from process data
        uploads_folder = process_data["uploads_folder"]

        # Construct the path to the mappings folder
        mappings_folder = os.path.join(
            "seq_processed", uploads_folder, "mapping_files"
        )

        # Check if regions are specified
        if process_data["regions"]:
            # Iterate through each region
            for region in process_data["regions"]:

                # Construct the path to the potential mappings file
                mapping_file = os.path.join(
                    mappings_folder, f"{region}_Mapping.txt"
                )

                # Check if the mapping file exists
                if not os.path.isfile(mapping_file):
                    # If any mapping file does not exist, return
                    # False immediately
                    return False

            # If all reports exist, return True
            return True

        else:
            # If there are no regions specified, we can assume
            # mappings do not exist
            return False

    @classmethod
    def check_lotus2_reports_exist(cls, process_id):
        with session_scope() as session:
            process_data = cls.get(process_id)

            # Extract uploads folder and bucket from process data
            uploads_folder = process_data["uploads_folder"]
            bucket = process_data["project_id"]
            results = []  # To store the results for each region

            # Iterate through each region
            for index, region in enumerate(process_data["regions"]):
                # Query to get all analysis types for the specified region

                analysis_types = (
                    session.query(SequencingAnalysisTypesTable)
                    .filter(SequencingAnalysisTypesTable.region == region)
                    .all()  # Retrieve all matching rows as a list
                )

                # Example of iterating over the result
                for analysis_type in analysis_types:
                    analysis_type_name = analysis_type.name
                    region_result = {
                        "region": region,
                        "report_status": None,
                        "log_files_exist": {
                            "LotuS_progout": False,
                            "demulti": False,
                            "LotuS_run": False,
                            "phyloseq": False,
                        },
                        "bucket_log_exists": False,
                        "lotus2_command_outcome": False,
                        "analysis_type": analysis_type_name,
                        "analysis_type_id": analysis_type.id,
                        "parameters": {},
                        "started_at": None,
                        "finished_at": None,
                    }
                    analysis_id = SequencingAnalysis.get_by_upload_and_type(
                        process_id, analysis_type.id
                    )
                    if analysis_id:
                        analysis = SequencingAnalysis.get(analysis_id)
                        region_result["lotus2_status"] = analysis.lotus2_status
                        region_result["parameters"] = analysis.parameters
                        region_result["lotus2_command_outcome"] = (
                            analysis.lotus2_result
                        )
                        region_result["started_at"] = (
                            analysis.lotus2_started_at
                        )
                        region_result["finished_at"] = (
                            analysis.lotus2_finished_at
                        )

                        # Proceed only if the status is "Finished"
                        if region_result["lotus2_status"] == "Finished":

                            # Construct the path to the log
                            # files inside uploads_folder
                            report_folder = os.path.join(
                                "seq_processed",
                                uploads_folder,
                                "lotus2_report",
                                analysis_type.name,
                            )

                            log_folder = os.path.join(
                                report_folder,
                                "LotuSLogS",
                            )

                            # Check if the required log files exist locally
                            lotus_progout_file = os.path.join(
                                log_folder, "LotuS_progout.log"
                            )
                            demulti_file = os.path.join(
                                log_folder, "demulti.log"
                            )
                            lotus_run_file = os.path.join(
                                log_folder, "LotuS_run.log"
                            )
                            phyloseq_file = os.path.join(
                                report_folder, "phyloseq.Rdata"
                            )
                            # Update the existence status in the
                            # result dictionary
                            region_result["log_files_exist"][
                                "LotuS_progout"
                            ] = os.path.isfile(lotus_progout_file)
                            region_result["log_files_exist"]["demulti"] = (
                                os.path.isfile(demulti_file)
                            )
                            region_result["log_files_exist"]["LotuS_run"] = (
                                os.path.isfile(lotus_run_file)
                            )
                            region_result["log_files_exist"]["phyloseq"] = (
                                os.path.isfile(phyloseq_file)
                            )

                            # Check if we need to verify files in the bucket
                            bucket_directory = (
                                f"lotus2_report/"
                                f"{analysis_type.name}/LotuSLogS"
                            )
                            # Check if LotuS_progout.log exists in the bucket
                            progout_exists = check_file_exists_in_bucket(
                                local_file_path=lotus_progout_file,
                                destination_upload_directory=bucket_directory,
                                destination_blob_name="LotuS_progout.log",
                                bucket_name=bucket,
                            )
                            region_result["bucket_log_exists"] = progout_exists

                    # Append the region result to the results list
                    results.append(region_result)
            return results

    @classmethod
    def check_rscripts_reports_exist(cls, process_id):
        with session_scope() as session:
            process_data = cls.get(process_id)

            # Extract uploads folder and bucket from process data
            uploads_folder = process_data["uploads_folder"]
            bucket = process_data["project_id"]
            results = []  # To store the results for each region

            # Iterate through each region
            for index, region in enumerate(process_data["regions"]):
                # Query to get all analysis types for the specified region

                analysis_types = (
                    session.query(SequencingAnalysisTypesTable)
                    .filter(SequencingAnalysisTypesTable.region == region)
                    .all()  # Retrieve all matching rows as a list
                )

                # Example of iterating over the result
                for analysis_type in analysis_types:
                    analysis_type_name = analysis_type.name
                    region_result = {
                        "region": region,
                        "report_status": None,
                        "files_exist": {
                            "LibrarySize": False,
                            "control_vs_sample": False,
                            "filtered_rarefaction": False,
                            "physeq_decontam": False,
                            "metadata_chaorichness": False,
                            "contaminants": False,
                            "physeq_by_genus": False,
                        },
                        "bucket_log_exists": False,
                        "rscripts_command_outcome": False,
                        "analysis_type": analysis_type_name,
                        "analysis_type_id": analysis_type.id,
                        "started_at": None,
                        "finished_at": None,
                    }
                    analysis_id = SequencingAnalysis.get_by_upload_and_type(
                        process_id, analysis_type.id
                    )
                    if analysis_id:
                        analysis = SequencingAnalysis.get(analysis_id)
                        region_result["rscripts_status"] = (
                            analysis.rscripts_status
                        )
                        region_result["started_at"] = (
                            analysis.rscripts_started_at
                        )
                        region_result["finished_at"] = (
                            analysis.rscripts_finished_at
                        )
                        region_result["rscripts_command_outcome"] = (
                            analysis.rscripts_result
                        )

                        # Proceed only if the status is "Finished"
                        if region_result["rscripts_status"] == "Finished":

                            # Construct the path to the log files
                            # inside uploads_folder
                            report_folder = os.path.join(
                                "seq_processed",
                                uploads_folder,
                                "r_output",
                                analysis_type.name,
                            )

                            # Check if the required log files exist locally
                            library_size_file = os.path.join(
                                report_folder, "LibrarySize.pdf"
                            )
                            region_result["files_exist"]["LibrarySize"] = (
                                os.path.isfile(library_size_file)
                            )

                            control_vs_sample_file = os.path.join(
                                report_folder, "control_vs_sample.pdf"
                            )
                            region_result["files_exist"][
                                "control_vs_sample"
                            ] = os.path.isfile(control_vs_sample_file)

                            filtered_rarefaction_file = os.path.join(
                                report_folder, "filtered_rarefaction.pdf"
                            )
                            region_result["files_exist"][
                                "filtered_rarefaction"
                            ] = os.path.isfile(filtered_rarefaction_file)

                            physeq_decontam_file = os.path.join(
                                report_folder, "physeq_decontam.Rdata"
                            )
                            region_result["files_exist"]["physeq_decontam"] = (
                                os.path.isfile(physeq_decontam_file)
                            )

                            metadata_chaorichness_file = os.path.join(
                                report_folder, "metadata_chaorichness.csv"
                            )
                            region_result["files_exist"][
                                "metadata_chaorichness"
                            ] = os.path.isfile(metadata_chaorichness_file)

                            contaminants_file = os.path.join(
                                report_folder, "contaminants.csv"
                            )
                            region_result["files_exist"]["contaminants"] = (
                                os.path.isfile(contaminants_file)
                            )

                            physeq_by_genus_file = os.path.join(
                                report_folder, "ecm_physeq_by_genus.pdf"
                            )
                            if analysis_type.name in [
                                "SSU_dada2",
                                "SSU_vsearch",
                                "SSU_eukaryome",
                            ]:
                                physeq_by_genus_file = os.path.join(
                                    report_folder, "amf_physeq_by_genus.pdf"
                                )
                            region_result["files_exist"]["physeq_by_genus"] = (
                                os.path.isfile(physeq_by_genus_file)
                            )

                            # Check if we need to verify files in the bucket
                            bucket_directory = (
                                f"lotus2_report/"
                                f"{analysis_type.name}/r_scripts_output"
                            )
                            # Check if LotuS_progout.log exists in the bucket
                            decontam_exists = check_file_exists_in_bucket(
                                local_file_path=physeq_decontam_file,
                                destination_upload_directory=bucket_directory,
                                destination_blob_name="physeq_decontam.Rdata",
                                bucket_name=bucket,
                            )
                            region_result["bucket_log_exists"] = (
                                decontam_exists
                            )

                    # Append the region result to the results list
                    results.append(region_result)
            return results

    @classmethod
    def reset_primers_count(cls, id):
        files = cls.get_uploaded_files(id)
        for file in files:
            # SequencingFileUploaded.update_field(
            #    file["id"], "primer_occurrences_count", None
            # )
            SequencingFileUploaded.update_primer_occurrences_count(file["id"])

    @classmethod
    def process_otu_data(
        cls, csv_file_path, sequencing_upload_id, analysis_id
    ):
        # Step 1: Read CSV into a Pandas DataFrame
        df = pd.read_csv(csv_file_path)
        # Step 2: Get all existing samples upfront
        samples = cls.get_samples(
            sequencing_upload_id
        )  # Fetch all samples once
        samples_dict = {
            sample["SampleID"]: sample["id"] for sample in samples
        }  # Map SampleID -> id
        # logger.info(samples_dict)

        # Part A: Create taxonomies and return their IDs
        taxonomies = cls.create_taxonomies_from_csv(
            df, sequencing_upload_id, samples_dict
        )

        # Part B: Bulk create OTUs using the taxonomy_ids
        with session_scope() as session:
            otus = []
            counter = 0

            for sample_id, taxonomy_id, abundance, ecm_flag in taxonomies:
                # Ensure that all required values are present and not None
                if (
                    sample_id is not None
                    and pd.notna(taxonomy_id)
                    and abundance is not None
                    and analysis_id is not None
                ):
                    counter += 1
                    otu = OTU(
                        sample_id=sample_id,
                        taxonomy_id=taxonomy_id,
                        abundance=abundance,
                        sequencing_analysis_id=analysis_id,
                        ecm_flag=ecm_flag,
                    )
                    otus.append(otu)

            # Bulk insert OTUs into the database
            if otus:
                session.add_all(otus)
                session.commit()

        logger.info(f"Nr of OTUs we found: {counter}")
        logger.info("OTU data processed and stored successfully.")

    @classmethod
    def create_taxonomies_from_csv(
        cls, df, sequencing_upload_id, samples_dict
    ):
        df = df.copy()
        # Drop rows where Domain is missing (optional,
        #  prevents unnecessary processing)
        df = df[df["Domain"].notna() & (df["Domain"] != "")]

        # Extract unique taxonomies
        unique_taxonomies = df[
            [
                "Domain",
                "Phylum",
                "Class",
                "Order",
                "Family",
                "Genus",
                "Species",
            ]
        ].drop_duplicates()

        logger.info(f"Found {len(unique_taxonomies)} unique taxonomies.")

        taxonomy_id_map = {}  # Maps taxonomy tuples to their database IDs

        # Start a session for database interaction
        with session_scope() as session:
            for _, row in unique_taxonomies.iterrows():
                # Create the taxonomy and store its ID in the map
                taxonomy_id = TaxonomyManager.create(
                    domain_name=row["Domain"],
                    phylum_name=row["Phylum"],
                    class_name=row["Class"],
                    order_name=row["Order"],
                    family_name=row["Family"],
                    genus_name=row["Genus"],
                    species_name=row["Species"],
                    session=session,
                )
                taxonomy_tuple = tuple(
                    row
                )  # Convert row to a tuple for unique identification
                taxonomy_id_map[taxonomy_tuple] = taxonomy_id  # Store in map

        # Map sample IDs to taxonomy IDs
        df["taxonomy_tuple"] = df[
            [
                "Domain",
                "Phylum",
                "Class",
                "Order",
                "Family",
                "Genus",
                "Species",
            ]
        ].apply(
            tuple, axis=1
        )  # Convert taxonomy columns into a tuple

        df["taxonomy_id"] = df["taxonomy_tuple"].map(
            taxonomy_id_map
        )  # Map to taxonomy_id

        # Create a list of tuples with (sample_id, taxonomy_id, abundance)
        # Use samples_dict to map SampleID to id and ensure we pass
        # the abundance as well
        taxonomies = []
        for _, row in df.iterrows():
            sample = str(row["sample_id"])
            sample_id = samples_dict.get(
                sample
            )  # Get the sample ID from the dict

            if not sample_id and sample.startswith(
                "S_"
            ):  # Only try without "S_" if the sample starts with it
                sample_without_prefix = sample[2:]  # Remove the "S_" prefix
                sample_id = samples_dict.get(sample_without_prefix)

            if (
                sample_id
            ):  # Only proceed if the sample exists in the dictionary
                ecm_flag = row["ecm_flag"] if "ecm_flag" in df.columns else 0
                taxonomies.append(
                    (sample_id, row["taxonomy_id"], row["abundance"], ecm_flag)
                )

        logger.info(f"Mapped taxonomies to sample IDs: {len(taxonomies)}")

        return taxonomies

    @classmethod
    def create_symlinks(cls, sequencingUploadId):
        process_data = cls.get(sequencingUploadId)
        uploads_folder = process_data["uploads_folder"]
        upload_files = cls.get_uploaded_files(sequencingUploadId)

        base_path = os.path.join("seq_processed", uploads_folder)
        share_folder = os.path.join(base_path, "share")
        r_output_folder = "r_output"
        fastqc_folder = "fastqc"
        lotus2_report_folder = "lotus2_report"

        # Ensure 'share' folder exists
        os.makedirs(share_folder, exist_ok=True)

        # Create relative symlink for report.pdf
        report_source = os.path.join(r_output_folder, "report.pdf")
        report_target = os.path.join("..", r_output_folder, "report.pdf")
        report_symlink = os.path.join(share_folder, "report.pdf")
        if os.path.exists(
            os.path.join(base_path, report_source)
        ) and not os.path.islink(report_symlink):
            os.symlink(report_target, report_symlink)

        for region in process_data["regions"]:
            region_folder = os.path.join(share_folder, region)
            raw_folder = os.path.join(region_folder, "raw")
            results_folder = os.path.join(region_folder, "results")
            predecontam_folder = os.path.join(results_folder, "predecontam")

            # Ensure directories exist
            os.makedirs(raw_folder, exist_ok=True)
            os.makedirs(results_folder, exist_ok=True)
            os.makedirs(predecontam_folder, exist_ok=True)

            # Create relative symlinks for raw files
            for file in upload_files:
                if file["region"] == region:
                    # Correct the relative path to go up three levels
                    target_path = os.path.join(
                        "..", "..", "..", file["new_name"]
                    )
                    symlink_path = os.path.join(raw_folder, file["new_name"])
                    source_file = os.path.join(base_path, file["new_name"])

                    if os.path.exists(source_file) and not os.path.islink(
                        symlink_path
                    ):
                        os.symlink(target_path, symlink_path)

            # Determine the correct folder name for SSU
            region_path = region if region != "SSU" else "SSU_dada2"
            base_lotus_path = os.path.join(
                base_path, lotus2_report_folder, region_path
            )
            base_r_output_path = os.path.join(
                base_path, r_output_folder, region_path
            )

            relative_lotus2_path_three_back = os.path.join(
                "..", "..", "..", lotus2_report_folder, region_path
            )
            relative_lotus2_path_four_back = os.path.join(
                "..", relative_lotus2_path_three_back
            )
            relative_r_output_path_three_back = os.path.join(
                "..", "..", "..", r_output_folder, region_path
            )

            # Define all file mappings in a structured dictionary
            file_mappings = {
                "contaminants.csv": {
                    "source": os.path.join(
                        base_r_output_path, "contaminants.csv"
                    ),
                    "symlink": os.path.join(
                        relative_r_output_path_three_back, "contaminants.csv"
                    ),
                },
                "multiqc_report.html": {
                    "source": os.path.join(
                        base_path, fastqc_folder, region, "multiqc_report.html"
                    ),
                    "symlink": os.path.join(
                        "..",
                        "..",
                        "..",
                        fastqc_folder,
                        region,
                        "multiqc_report.html",
                    ),
                },
                "physeq_decontam.Rdata": {
                    "source": os.path.join(
                        base_r_output_path, "physeq_decontam.Rdata"
                    ),
                    "symlink": os.path.join(
                        relative_r_output_path_three_back,
                        "physeq_decontam.Rdata",
                    ),
                },
                "predecontam/phyloseq_predecontam.Rdata": {
                    "source": os.path.join(base_lotus_path, "phyloseq.Rdata"),
                    "symlink": os.path.join(
                        relative_lotus2_path_four_back, "phyloseq.Rdata"
                    ),
                },
                "report_images/control_vs_sample.pdf": {
                    "source": os.path.join(
                        base_lotus_path, "control_vs_sample.pdf"
                    ),
                    "symlink": os.path.join(
                        relative_lotus2_path_four_back, "control_vs_sample.pdf"
                    ),
                },
                "report_images/filtered_rarefaction.pdf": {
                    "source": os.path.join(
                        base_lotus_path, "filtered_rarefaction.pdf"
                    ),
                    "symlink": os.path.join(
                        relative_lotus2_path_four_back,
                        "filtered_rarefaction.pdf",
                    ),
                },
                "report_images/LibrarySize.pdf": {
                    "source": os.path.join(base_lotus_path, "LibrarySize.pdf"),
                    "symlink": os.path.join(
                        relative_lotus2_path_four_back, "LibrarySize.pdf"
                    ),
                },
                "ExtraFiles": {
                    "source": os.path.join(base_lotus_path, "ExtraFiles"),
                    "symlink": os.path.join(
                        relative_lotus2_path_three_back, "ExtraFiles"
                    ),
                },
                "hiera_BLAST.txt": {
                    "source": os.path.join(base_lotus_path, "hiera_BLAST.txt"),
                    "symlink": os.path.join(
                        relative_lotus2_path_three_back, "hiera_BLAST.txt"
                    ),
                },
                "higherLvl": {
                    "source": os.path.join(base_lotus_path, "higherLvl"),
                    "symlink": os.path.join(
                        relative_lotus2_path_three_back, "higherLvl"
                    ),
                },
                "LotuSLogS": {
                    "source": os.path.join(base_lotus_path, "LotuSLogS"),
                    "symlink": os.path.join(
                        relative_lotus2_path_three_back, "LotuSLogS"
                    ),
                },
                "OTU.biom": {
                    "source": os.path.join(base_lotus_path, "OTU.biom"),
                    "symlink": os.path.join(
                        relative_lotus2_path_three_back, "OTU.biom"
                    ),
                },
                "OTU.fna": {
                    "source": os.path.join(base_lotus_path, "OTU.fna"),
                    "symlink": os.path.join(
                        relative_lotus2_path_three_back, "OTU.fna"
                    ),
                },
                "OTUphylo.nwk": {
                    "source": os.path.join(base_lotus_path, "OTUphylo.nwk"),
                    "symlink": os.path.join(
                        relative_lotus2_path_three_back, "OTUphylo.nwk"
                    ),
                },
                "OTU.txt": {
                    "source": os.path.join(base_lotus_path, "OTU.txt"),
                    "symlink": os.path.join(
                        relative_lotus2_path_three_back, "OTU.txt"
                    ),
                },
                "primary": {
                    "source": os.path.join(base_lotus_path, "primary"),
                    "symlink": os.path.join(
                        relative_lotus2_path_three_back, "primary"
                    ),
                },
            }

            # Add region-specific source paths for SSU and ITS regions
            if region == "SSU":
                file_mappings["amf_physeq.Rdata"] = {
                    "source": os.path.join(
                        base_path,
                        r_output_folder,
                        "SSU_dada2",
                        "amf_physeq.Rdata",
                    ),
                    "symlink": os.path.join(
                        "..",
                        "..",
                        "..",
                        r_output_folder,
                        "SSU_dada2",
                        "amf_physeq.Rdata",
                    ),
                }
                file_mappings["report_images/amf_physeq_by_genus.pdf"] = {
                    "source": os.path.join(
                        base_lotus_path, "amf_physeq_by_genus.pdf"
                    ),
                    "symlink": os.path.join(
                        relative_lotus2_path_four_back,
                        "amf_physeq_by_genus.pdf",
                    ),
                }
            elif region in ["ITS1", "ITS2"]:
                file_mappings["ecm_physeq.Rdata"] = {
                    "source": os.path.join(
                        base_path,
                        r_output_folder,
                        "SSU_dada2",
                        "ecm_physeq.Rdata",
                    ),
                    "symlink": os.path.join(
                        "..",
                        "..",
                        "..",
                        r_output_folder,
                        "SSU_dada2",
                        "ecm_physeq.Rdata",
                    ),
                }
                file_mappings["report_images/ecm_physeq_by_genus.pdf"] = {
                    "source": os.path.join(
                        base_lotus_path, "ecm_physeq_by_genus.pdf"
                    ),
                    "symlink": os.path.join(
                        relative_lotus2_path_four_back,
                        "ecm_physeq_by_genus.pdf",
                    ),
                }

            # Now check and create symlinks for each item
            for file_name, paths in file_mappings.items():
                symlink_path = os.path.join(results_folder, file_name)
                full_source_path = paths["source"]
                if os.path.exists(full_source_path) and not os.path.islink(
                    symlink_path
                ):
                    os.symlink(paths["symlink"], symlink_path)
