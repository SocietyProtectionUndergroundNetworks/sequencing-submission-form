# models/meta_project.py
from helpers.dbm import session_scope
from models.db_model import (
    MetaProjectsTable,
    MetaProjectUploadsTable,
    SequencingAnalysisTypesTable,
    SequencingAnalysisTable,
)
from models.sequencing_sample import SequencingSample
from models.sequencing_upload import SequencingUpload
from models.sequencing_analysis import SequencingAnalysis
import os
import logging

logger = logging.getLogger(__name__)


class MetaProject:
    @classmethod
    def create(cls, name, user_id):
        """Creates a new meta project and its associated results folder with zero-prefixed ID."""
        with session_scope() as session:
            new_meta = MetaProjectsTable(name=name, user_id=user_id)
            session.add(new_meta)
            session.flush()  # Ensures the database assigns an ID

            # Format the ID with prefixed zeros (e.g., 1 -> 0001) for alphabetical sorting
            formatted_id = f"{new_meta.id:04d}"
            folder_name = f"meta_project_{formatted_id}"
            new_meta.results_folder = folder_name

            # Physical directory creation logic
            # Assuming 'seq_processed' is your base directory for analysis outputs
            processed_path = os.path.join("seq_processed", folder_name)
            if not os.path.exists(processed_path):
                os.makedirs(processed_path)
                logger.info(f"Created meta-project folder: {processed_path}")

            return new_meta.id

    @classmethod
    def get(cls, meta_project_id):
        """Retrieves meta project details and its associated upload IDs."""
        with session_scope() as session:
            meta = (
                session.query(MetaProjectsTable)
                .filter_by(id=meta_project_id)
                .first()
            )
            if not meta:
                return None

            return {
                "id": meta.id,
                "name": meta.name,
                "user_id": meta.user_id,
                "results_folder": meta.results_folder,
                "upload_ids": [u.id for u in meta.uploads],
            }

    @classmethod
    def get_all(cls):
        """Retrieves all meta projects from the database for staff/admin overview."""
        with session_scope() as session:
            projects = session.query(MetaProjectsTable).all()
            return [
                {
                    "id": p.id,
                    "name": p.name,
                    "created_at": p.created_at,
                    "results_folder": p.results_folder,
                    "user_id": p.user_id,
                }
                for p in projects
            ]

    @classmethod
    def add_uploads(cls, meta_project_id, sequencing_upload_ids):
        """Links existing sequencing uploads to the meta project."""
        with session_scope() as session:
            # Clear existing links if necessary or just add new ones
            for upload_id in sequencing_upload_ids:
                # Verify link doesn't already exist
                exists = (
                    session.query(MetaProjectUploadsTable)
                    .filter_by(
                        meta_project_id=meta_project_id,
                        sequencing_upload_id=upload_id,
                    )
                    .first()
                )

                if not exists:
                    link = MetaProjectUploadsTable(
                        meta_project_id=meta_project_id,
                        sequencing_upload_id=upload_id,
                    )
                    session.add(link)

    @classmethod
    def get_combined_samples_data(cls, meta_project_id):
        meta_data = cls.get(meta_project_id)
        combined_data = []
        for upload_id in meta_data["upload_ids"]:
            project_samples = (
                SequencingUpload.get_samples_with_sequencers_and_files(
                    upload_id
                )
            )
            project_info = SequencingUpload.get(upload_id)

            folder = project_info.get("uploads_folder")
            country = project_info.get("Country")

            for sample in project_samples:
                # We must attach these at the top level of the sample dict
                sample["project_uploads_folder"] = folder
                sample["project_country"] = country
                combined_data.append(sample)

        return combined_data

    @classmethod
    def generate_mapping_files(
        cls, meta_project_id, mode="Forward and reverse"
    ):
        """Aggregates data and triggers the refactored mapping generator."""
        meta_data = cls.get(meta_project_id)
        if not meta_data:
            raise ValueError("Meta project not found")

        # 1. Get the regions that exist across all projects in this Meta Project
        # This replaces the manual 'regions' parameter to make the UI simpler
        region_list = cls.get_regions(meta_project_id)

        # 2. Aggregate samples
        combined_samples = cls.get_combined_samples_data(meta_project_id)

        # 3. Build the primer dictionary for these regions
        region_dict = {}
        with session_scope() as session:
            meta = (
                session.query(MetaProjectsTable)
                .filter_by(id=meta_project_id)
                .first()
            )
            from helpers.metadata_check import get_sequences_based_on_primers

            for upload_db in meta.uploads:
                for r_num in [1, 2]:
                    fwd = getattr(upload_db, f"region_{r_num}_forward_primer")
                    rev = getattr(upload_db, f"region_{r_num}_reverse_primer")
                    if fwd and rev:
                        seqs = get_sequences_based_on_primers(fwd, rev)
                        if seqs and seqs["Region"] in region_list:
                            region_dict[seqs["Region"]] = {
                                "Forward Primer": seqs["Forward Primer"],
                                "Reverse Primer": seqs["Reverse Primer"],
                            }

        # 4. Define output directory
        output_dir = (
            f"seq_processed/{meta_data['results_folder']}/mapping_files/"
        )

        # 5. Call the core generator with the correct positional arguments:
        # (samples_data_complete, output_dir, bucket, region_dict, mode)
        from models.sequencing_upload import SequencingUpload

        return SequencingUpload.generate_mapping_files_from_data(
            combined_samples,  # 1
            output_dir,  # 2
            None,  # 3: bucket (meta projects don't have a single source bucket)
            region_dict,  # 4
            mode,  # 5
        )

    @classmethod
    def get_regions(cls, meta_project_id):
        from models.db_model import (
            MetaProjectUploadsTable,
            SequencingUploadsTable,
        )

        with session_scope() as session:
            results = (
                session.query(
                    SequencingUploadsTable.region_1,
                    SequencingUploadsTable.region_2,
                )
                .join(
                    MetaProjectUploadsTable,
                    SequencingUploadsTable.id
                    == MetaProjectUploadsTable.sequencing_upload_id,
                )
                .filter(
                    MetaProjectUploadsTable.meta_project_id == meta_project_id
                )
                .all()
            )

            regions = set()
            for row in results:
                # Row is a tuple like ('SSU', None)
                if row[0]:
                    regions.add(str(row[0]).strip())
                if row[1]:
                    regions.add(str(row[1]).strip())

            final_list = sorted([r for r in regions if r])
            return final_list

    @classmethod
    def check_lotus2_reports_exist(cls, meta_project_id):
        """Checks for existing Lotus2 reports linked to this meta project."""
        regions = cls.get_regions(meta_project_id)
        meta_data = cls.get(meta_project_id)
        results = []

        with session_scope() as session:
            for region in regions:
                # Find analysis types for this region
                analysis_types = (
                    session.query(SequencingAnalysisTypesTable)
                    .filter_by(region=region)
                    .all()
                )

                for a_type in analysis_types:
                    # Look for analysis linked to metaProjectId
                    analysis_id = (
                        SequencingAnalysis.get_by_meta_project_and_type(
                            meta_project_id, a_type.id
                        )
                    )

                    region_result = {
                        "region": region,
                        "analysis_type": a_type.name,
                        "analysis_type_id": a_type.id,
                        "lotus2_status": None,
                        "log_files_exist": {
                            k: False
                            for k in [
                                "LotuS_progout",
                                "demulti",
                                "LotuS_run",
                                "phyloseq",
                            ]
                        },
                        "bucket_log_exists": False,
                        "lotus2_command_outcome": False,
                        "parameters": {},
                        "started_at": None,
                        "finished_at": None,
                    }

                    if analysis_id:
                        analysis = SequencingAnalysis.get(analysis_id)
                        region_result.update(
                            {
                                "lotus2_status": analysis.lotus2_status,
                                "parameters": analysis.parameters or {},
                                "lotus2_command_outcome": bool(
                                    analysis.lotus2_result
                                ),
                                "started_at": analysis.lotus2_started_at,
                                "finished_at": analysis.lotus2_finished_at,
                            }
                        )

                        if analysis.lotus2_status == "Finished":
                            report_path = os.path.join(
                                "seq_processed",
                                meta_data["results_folder"],
                                "lotus2_report",
                                a_type.name,
                            )
                            log_path = os.path.join(report_path, "LotuSLogS")

                            region_result["log_files_exist"] = {
                                "LotuS_progout": os.path.isfile(
                                    os.path.join(log_path, "LotuS_progout.log")
                                ),
                                "demulti": os.path.isfile(
                                    os.path.join(log_path, "demulti.log")
                                ),
                                "LotuS_run": os.path.isfile(
                                    os.path.join(log_path, "LotuS_run.log")
                                ),
                                "phyloseq": os.path.isfile(
                                    os.path.join(report_path, "phyloseq.Rdata")
                                ),
                            }
                    results.append(region_result)
        return results

    @classmethod
    def check_rscripts_reports_exist(cls, meta_project_id):
        """Checks for existing R-script reports linked to this meta project."""
        regions = cls.get_regions(meta_project_id)
        meta_data = cls.get(meta_project_id)
        if not meta_data:
            return []

        results = []
        with session_scope() as session:
            for region in regions:
                # Get all analysis types associated with this region
                analysis_types = (
                    session.query(SequencingAnalysisTypesTable)
                    .filter(SequencingAnalysisTypesTable.region == region)
                    .all()
                )

                for analysis_type in analysis_types:
                    # Initialize the status dictionary for this specific analysis
                    region_result = {
                        "region": region,
                        "analysis_type": analysis_type.name,
                        "analysis_type_id": analysis_type.id,
                        "rscripts_status": None,
                        "files_exist": {
                            "LibrarySize": False,
                            "control_vs_sample": False,
                            "filtered_rarefaction": False,
                            "physeq_decontam": False,
                            "metadata_chaorichness": False,
                            "contaminants": False,
                            "physeq_by_genus": False,
                        },
                        "bucket_log_exists": False,  # Meta-projects may not have a single bucket yet
                        "rscripts_command_outcome": False,
                        "started_at": None,
                        "finished_at": None,
                    }

                    # Query SequencingAnalysis for metaProjectId (requires the model update)
                    analysis = (
                        session.query(SequencingAnalysisTable)
                        .filter_by(
                            metaProjectId=meta_project_id,
                            sequencingAnalysisTypeId=analysis_type.id,
                        )
                        .first()
                    )

                    if analysis:
                        region_result.update(
                            {
                                "rscripts_status": analysis.rscripts_status,
                                "started_at": analysis.rscripts_started_at,
                                "finished_at": analysis.rscripts_finished_at,
                                "rscripts_command_outcome": bool(
                                    analysis.rscripts_result
                                ),
                            }
                        )

                        if analysis.rscripts_status == "Finished":
                            # Construct the path to the meta-project results folder
                            report_folder = os.path.join(
                                "seq_processed",
                                meta_data["results_folder"],
                                "r_output",
                                analysis_type.name,
                            )

                            # Map the specific files expected by the UI
                            file_mapping = {
                                "LibrarySize": "LibrarySize.pdf",
                                "control_vs_sample": "control_vs_sample.pdf",
                                "filtered_rarefaction": "filtered_rarefaction.pdf",
                                "physeq_decontam": "physeq_decontam.Rdata",
                                "metadata_chaorichness": "metadata_chaorichness.csv",
                                "contaminants": "contaminants.csv",
                            }

                            for key, filename in file_mapping.items():
                                region_result["files_exist"][key] = (
                                    os.path.isfile(
                                        os.path.join(report_folder, filename)
                                    )
                                )

                            # Handle region-specific genus plot naming
                            genus_file = "ecm_physeq_by_genus.pdf"
                            if analysis_type.name in [
                                "SSU_dada2",
                                "SSU_vsearch",
                                "SSU_eukaryome",
                            ]:
                                genus_file = "amf_physeq_by_genus.pdf"

                            region_result["files_exist"]["physeq_by_genus"] = (
                                os.path.isfile(
                                    os.path.join(report_folder, genus_file)
                                )
                            )

                    results.append(region_result)
        return results

    @classmethod
    def check_mapping_files_exist(cls, meta_project_id):
        """Checks if mapping files exist in the meta-project results folder."""
        meta_data = cls.get(meta_project_id)
        regions = cls.get_regions(meta_project_id)
        if not meta_data or not regions:
            return False

        mappings_folder = os.path.join(
            "seq_processed", meta_data["results_folder"], "mapping_files"
        )

        for region in regions:
            mapping_file = os.path.join(
                mappings_folder, f"{region}_Mapping.txt"
            )
            if not os.path.isfile(mapping_file):
                return False
        return True
