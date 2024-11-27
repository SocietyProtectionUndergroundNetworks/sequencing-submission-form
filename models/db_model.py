# helpers/db_model.py
from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    Text,
    Boolean,
    DateTime,
    func,
    ForeignKey,
)
from sqlalchemy.dialects.mysql import JSON, MEDIUMTEXT
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import uuid

Base = declarative_base()

association_table = Table(
    "user_buckets",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id")),
    Column("bucket_id", String(250), ForeignKey("buckets.id")),
)

user_groups_association = Table(
    "user_groups_association",
    Base.metadata,
    Column("user_id", String(36), ForeignKey("users.id")),
    Column("group_id", Integer, ForeignKey("user_groups.id")),
)


class UserTable(Base):
    __tablename__ = "users"

    id = Column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    profile_pic = Column(String(255), nullable=False)
    admin = Column(Boolean, default=False)
    uploads = relationship("UploadTable", backref="user")
    approved = Column(Boolean, default=False)
    goodgrands_slug = Column(String(50), nullable=True)
    buckets = relationship(
        "BucketTable", secondary=association_table, backref="users"
    )
    groups = relationship(
        "UserGroupsTable",
        secondary=user_groups_association,
        back_populates="users",
    )


class PreapprovedUsersTable(Base):
    __tablename__ = "preapproved_users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), nullable=False)
    bucket = Column(String(255), nullable=True)
    group_id = Column(Integer, nullable=True)


class UserGroupsTable(Base):
    __tablename__ = "user_groups"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    version = Column(Integer, nullable=True)
    users = relationship(
        "UserTable", secondary=user_groups_association, back_populates="groups"
    )


class BucketTable(Base):
    __tablename__ = "buckets"

    id = Column(String(250), primary_key=True)
    archive_file = Column(String(255), nullable=True)
    archive_file_created_at = Column(DateTime, nullable=True)
    archive_file_creation_progress = Column(Integer, nullable=True)


class UploadTable(Base):
    __tablename__ = "uploads"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=True
    )
    metadata_filename = Column(String(255), nullable=True)
    uploads_folder = Column(String(20), nullable=True)
    sequencing_method = Column(Integer, default=0)
    csv_uploaded = Column(Boolean, default=False)
    csv_filename = Column(String(255), nullable=True)
    gz_filedata = Column(JSON(none_as_null=True))
    files_json = Column(JSON(none_as_null=True))
    files_renamed = Column(Boolean, default=False)
    renaming_skipped = Column(Boolean, default=False)
    fastqc_run = Column(Boolean, default=False)
    fastqc_files_progress = Column(String(255), nullable=True)
    fastqc_process_id = Column(String(255), nullable=True, index=True)
    fastqc_sent_to_bucket = Column(Boolean, default=False)
    renamed_sent_to_bucket = Column(Boolean, default=False)
    renamed_sent_to_bucket_progress = Column(Integer, default=0)
    reviewed_by_admin = Column(Boolean, default=False)


class SequencingUploadsTable(Base):
    __tablename__ = "sequencing_uploads"

    id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=True
    )
    project_id = Column(
        String(250), ForeignKey("buckets.id", ondelete="CASCADE")
    )
    latest_metadata_filename = Column(String(255), nullable=True)
    final_metadata_filename = Column(String(255), nullable=True)
    uploads_folder = Column(String(20), nullable=True)
    sequencing_upload_filedata = Column(JSON(none_as_null=True))
    using_scripps = Column(Boolean, default=False)
    Country = Column(String(255), nullable=True)
    Sequencing_platform = Column(String(255), nullable=True)
    Sequencing_facility = Column(String(255), nullable=True)
    Expedition_lead = Column(String(255), nullable=True)
    Collaborators = Column(String(255), nullable=True)
    region_1 = Column(String(255), nullable=True)
    region_1_forward_primer = Column(String(255), nullable=True)
    region_1_reverse_primer = Column(String(255), nullable=True)
    region_2 = Column(String(255), nullable=True)
    region_2_forward_primer = Column(String(255), nullable=True)
    region_2_reverse_primer = Column(String(255), nullable=True)
    Extraction_method = Column(String(255), nullable=True)
    Multiple_sequencing_runs = Column(String(255), nullable=True)
    Sequencing_regions_number = Column(Integer, nullable=True)
    metadata_upload_confirmed = Column(Boolean, default=False)
    DNA_conc_instrument = Column(String(255), nullable=True)
    reviewed_by_admin = Column(Boolean, default=False)
    files_uploading_confirmed = Column(Boolean, default=False)
    region_1_rscripts_report_task_id = Column(String(255), nullable=True)
    region_1_rscripts_report_started_at = Column(DateTime, nullable=True)
    region_1_rscripts_report_status = Column(String(255), nullable=True)
    region_1_rscripts_report_result = Column(Text, nullable=True)
    region_2_rscripts_report_task_id = Column(String(255), nullable=True)
    region_2_rscripts_report_started_at = Column(DateTime, nullable=True)
    region_2_rscripts_report_status = Column(String(255), nullable=True)
    region_2_rscripts_report_result = Column(Text, nullable=True)


class SequencingAnalysisTable(Base):
    __tablename__ = "sequencing_analysis"
    id = Column(Integer, primary_key=True)
    sequencingUploadId = Column(
        Integer, ForeignKey("sequencing_uploads.id", ondelete="CASCADE")
    )
    sequencingAnalysisTypeId = Column(
        Integer, ForeignKey("sequencing_analysis_types.id")
    )
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=True
    )
    lotus2_started_at = Column(DateTime)
    lotus2_finished_at = Column(DateTime)
    lotus2_celery_task_id = Column(String(255), nullable=True)
    lotus2_status = Column(String(255), nullable=True)
    lotus2_result = Column(
        MEDIUMTEXT(charset="utf8mb4", collation="utf8mb4_unicode_ci"),
        nullable=True,
    )
    rscripts_started_at = Column(DateTime)
    rscripts_finished_at = Column(DateTime)
    rscripts_celery_task_id = Column(String(255), nullable=True)
    rscripts_status = Column(String(255), nullable=True)
    rscripts_result = Column(
        MEDIUMTEXT(charset="utf8mb4", collation="utf8mb4_unicode_ci"),
        nullable=True,
    )
    parameters = Column(JSON(none_as_null=True))


class SequencingAnalysisTypesTable(Base):
    __tablename__ = "sequencing_analysis_types"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=True)
    region = Column(String(255), nullable=True)
    parameters = Column(JSON(none_as_null=True))


class SequencingSamplesTable(Base):
    __tablename__ = "sequencing_samples"
    id = Column(Integer, primary_key=True)
    sequencingUploadId = Column(
        Integer, ForeignKey("sequencing_uploads.id", ondelete="CASCADE")
    )
    SampleID = Column(String(255), nullable=True)
    Site_name = Column(String(255), nullable=True)
    Latitude = Column(String(255), nullable=True)
    Longitude = Column(String(255), nullable=True)
    Vegetation = Column(String(255), nullable=True)
    Land_use = Column(String(255), nullable=True)
    Agricultural_land = Column(String(255), nullable=True)
    Ecosystem = Column(String(255), nullable=True)
    ResolveEcoregion = Column(String(255), nullable=True)
    BaileysEcoregion = Column(String(255), nullable=True)
    Grid_Size = Column(String(255), nullable=True)
    Soil_depth = Column(String(255), nullable=True)
    Transport_refrigeration = Column(String(255), nullable=True)
    Drying = Column(String(255), nullable=True)
    Date_collected = Column(String(255), nullable=True)
    DNA_concentration_ng_ul = Column(String(255), nullable=True)
    Elevation = Column(String(255), nullable=True)
    Sample_or_Control = Column(String(255), nullable=True)
    SequencingRun = Column(String(255), nullable=True)
    Notes = Column(String(255), nullable=True)
    sequencer_ids = relationship(
        "SequencingSequencerIDsTable", backref="sample"
    )
    extracolumns_json = Column(JSON(none_as_null=True))


class SequencingSequencerIDsTable(Base):
    __tablename__ = "sequencing_sequencer_ids"
    id = Column(Integer, primary_key=True)
    sequencingSampleId = Column(
        Integer, ForeignKey("sequencing_samples.id", ondelete="CASCADE")
    )
    SequencerID = Column(String(255), nullable=True)
    Region = Column(String(25), nullable=True)
    Index_1 = Column(String(100), nullable=True)
    Index_2 = Column(String(100), nullable=True)


class SequencingFilesUploadedTable(Base):
    __tablename__ = "sequencing_files_uploaded"
    id = Column(Integer, primary_key=True)
    sequencerId = Column(
        Integer, ForeignKey("sequencing_sequencer_ids.id", ondelete="CASCADE")
    )
    original_filename = Column(String(255), nullable=True)
    new_name = Column(String(255), nullable=True)
    md5 = Column(String(50), nullable=True)
    exclude_from_mapping = Column(Boolean, default=False)
    total_sequences_number = Column(Integer, nullable=True)
    bucket_upload_progress = Column(Integer, nullable=True)
    primer_occurrences_count = Column(Integer, nullable=True)


class SequencingCompanyUploadTable(Base):
    __tablename__ = "sequencing_company_uploads"
    id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    created_at = Column(DateTime, default=func.now())
    uploads_folder = Column(String(20), nullable=True)
    csv_filename = Column(String(255), nullable=True)
    tar_filename = Column(String(255), nullable=True)


class SequencingCompanyInputTable(Base):
    __tablename__ = "sequencing_company_input"
    id = Column(Integer, primary_key=True)
    sequencingCompanyUploadId = Column(
        Integer,
        ForeignKey("sequencing_company_uploads.id", ondelete="CASCADE"),
    )
    sample_number = Column(String(255), nullable=True)
    sample_id = Column(String(255), nullable=True)
    sequencer_id = Column(String(255), nullable=True)
    sequencing_provider = Column(String(255), nullable=True)
    project = Column(String(50), nullable=True)
    region = Column(String(50), nullable=True)
    index_1 = Column(String(50), nullable=True)
    barcode_2 = Column(String(50), nullable=True)
