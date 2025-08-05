# helpers/db_model.py
from sqlalchemy import (
    Table,
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    func,
    ForeignKey,
    Float,
    JSON,
    Index,
)

from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.mysql import MEDIUMTEXT
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
    cohort = Column(String(255), nullable=True)


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
    files_uploading_confirmed = Column(Boolean, default=False)
    share_url = Column(String(255), nullable=True)
    share_sync_completed = Column(Boolean, default=False)


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
    lotus2_command = Column(
        MEDIUMTEXT(charset="utf8mb4", collation="utf8mb4_unicode_ci"),
        nullable=True,
    )
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
    # Define the relationship to OTU
    otus = relationship(
        "OTU",
        back_populates="sequencing_analysis",
        cascade="all, delete-orphan",  # Enable cascading delete
    )


class SequencingAnalysisSampleRichnessTable(Base):
    __tablename__ = "sequencing_analysis_sample_richness"
    id = Column(Integer, primary_key=True)
    analysis_id = Column(
        Integer,
        ForeignKey("sequencing_analysis.id", ondelete="CASCADE"),
        nullable=False,
    )
    sample_id = Column(
        Integer,
        ForeignKey("sequencing_samples.id", ondelete="CASCADE"),
        nullable=False,
    )
    observed = Column(Float, nullable=True)
    estimator = Column(Float, nullable=True)
    est_s_e = Column(Float, nullable=True)
    x95_percent_lower = Column(Float, nullable=True)
    x95_percent_upper = Column(Float, nullable=True)
    seq_depth = Column(Float, nullable=True)

    # Optional: Add timestamps for auditing purposes
    created_at = Column(DateTime, default=func.now())


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
    resolve_ecoregion_id = Column(
        Integer,
        ForeignKey("resolve_ecoregions.id", ondelete="SET NULL"),
        nullable=True,
    )
    BaileysEcoregion = Column(String(255), nullable=True)
    Grid_Size = Column(String(255), nullable=True)
    Soil_depth = Column(String(255), nullable=True)
    Transport_refrigeration = Column(String(255), nullable=True)
    Drying = Column(String(255), nullable=True)
    Date_collected = Column(String(255), nullable=True)
    DNA_concentration_ng_ul = Column(String(255), nullable=True)
    Elevation = Column(String(255), nullable=True)
    Sample_type = Column(String(255), nullable=True)
    Sample_or_Control = Column(String(255), nullable=True)
    IndigenousPartnership = Column(Boolean, default=False)
    Notes = Column(String(255), nullable=True)
    sequencer_ids = relationship(
        "SequencingSequencerIDsTable", backref="sample"
    )
    extracolumns_json = Column(JSON(none_as_null=True))
    otus = relationship(
        "OTU", back_populates="sample", cascade="all, delete-orphan"
    )

    # Relationship with ResolveEcoregionsTable
    resolve_ecoregion = relationship(
        "ResolveEcoregionsTable", back_populates="sequencing_samples"
    )


class SequencingSequencerIDsTable(Base):
    __tablename__ = "sequencing_sequencer_ids"
    id = Column(Integer, primary_key=True)
    sequencingSampleId = Column(
        Integer, ForeignKey("sequencing_samples.id", ondelete="CASCADE")
    )
    SequencerID = Column(String(255), nullable=True)
    Region = Column(String(25), nullable=True)
    sequencing_run = Column(String(255), nullable=True)
    Index_1 = Column(String(100), nullable=True)
    Index_2 = Column(String(100), nullable=True)
    fwd_read_fwd_adap = Column(Integer, nullable=True)
    rev_read_rev_adap = Column(Integer, nullable=True)
    fwd_rev_adap = Column(Integer, nullable=True)
    fwd_rev_mrg_adap = Column(Integer, nullable=True)


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


# Domain Table
class Domain(Base):
    __tablename__ = "taxonomy_domain"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), unique=True, nullable=False)  # Max length 255

    phyla = relationship(
        "Phylum", back_populates="domain", cascade="all, delete-orphan"
    )


# Phylum Table
class Phylum(Base):
    __tablename__ = "taxonomy_phylum"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    domain_id = Column(
        Integer, ForeignKey("taxonomy_domain.id"), nullable=False
    )

    domain = relationship("Domain", back_populates="phyla")
    classes = relationship(
        "Class", back_populates="phylum", cascade="all, delete-orphan"
    )


# Class Table
class Class(Base):
    __tablename__ = "taxonomy_class"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    phylum_id = Column(
        Integer, ForeignKey("taxonomy_phylum.id"), nullable=False
    )

    phylum = relationship("Phylum", back_populates="classes")
    orders = relationship(
        "Order", back_populates="class_", cascade="all, delete-orphan"
    )


# Order Table
class Order(Base):
    __tablename__ = "taxonomy_order"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    class_id = Column(Integer, ForeignKey("taxonomy_class.id"), nullable=False)

    class_ = relationship("Class", back_populates="orders")
    families = relationship(
        "Family", back_populates="order", cascade="all, delete-orphan"
    )


# Family Table
class Family(Base):
    __tablename__ = "taxonomy_family"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    order_id = Column(Integer, ForeignKey("taxonomy_order.id"), nullable=False)

    order = relationship("Order", back_populates="families")
    genera = relationship(
        "Genus", back_populates="family", cascade="all, delete-orphan"
    )


# Genus Table
class Genus(Base):
    __tablename__ = "taxonomy_genus"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    family_id = Column(
        Integer, ForeignKey("taxonomy_family.id"), nullable=False
    )

    family = relationship("Family", back_populates="genera")
    species = relationship(
        "Species", back_populates="genus", cascade="all, delete-orphan"
    )


# Species Table
class Species(Base):
    __tablename__ = "taxonomy_species"
    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    genus_id = Column(Integer, ForeignKey("taxonomy_genus.id"), nullable=False)

    genus = relationship("Genus", back_populates="species")


# Taxonomy Table
class Taxonomy(Base):
    __tablename__ = "taxonomy"
    id = Column(Integer, primary_key=True)
    domain_id = Column(
        Integer, ForeignKey("taxonomy_domain.id"), nullable=False
    )
    phylum_id = Column(
        Integer, ForeignKey("taxonomy_phylum.id"), nullable=True
    )
    class_id = Column(Integer, ForeignKey("taxonomy_class.id"), nullable=True)
    order_id = Column(Integer, ForeignKey("taxonomy_order.id"), nullable=True)
    family_id = Column(
        Integer, ForeignKey("taxonomy_family.id"), nullable=True
    )
    genus_id = Column(Integer, ForeignKey("taxonomy_genus.id"), nullable=True)
    species_id = Column(
        Integer, ForeignKey("taxonomy_species.id"), nullable=True
    )

    domain = relationship("Domain")
    phylum = relationship("Phylum")
    class_ = relationship("Class")
    order = relationship("Order")
    family = relationship("Family")
    genus = relationship("Genus")
    species = relationship("Species")


# OTU Table
class OTU(Base):
    __tablename__ = "otu"

    id = Column(Integer, primary_key=True)
    sample_id = Column(
        Integer, ForeignKey("sequencing_samples.id"), nullable=False
    )
    taxonomy_id = Column(Integer, ForeignKey("taxonomy.id"), nullable=False)
    abundance = Column(Integer, nullable=True)
    sequencing_analysis_id = Column(
        Integer, ForeignKey("sequencing_analysis.id"), nullable=False
    )
    ecm_flag = Column(Boolean, default=False, nullable=False)

    sample = relationship("SequencingSamplesTable", back_populates="otus")
    taxonomy = relationship("Taxonomy")
    sequencing_analysis = relationship("SequencingAnalysisTable")

    __table_args__ = (
        Index("idx_ecm_flag", ecm_flag),  # Simple index for ecm_flag
        Index(
            "idx_ecm_sample", ecm_flag, sample_id
        ),  # Composite index for ecm_flag + sample_id
        Index(
            "idx_ecm_taxonomy", ecm_flag, taxonomy_id
        ),  # Composite index for ecm_flag + taxonomy_id
        Index(
            "idx_ecm_analysis", ecm_flag, sequencing_analysis_id
        ),  # Composite index for ecm_flag + sequencing_analysis_id
    )


class ResolveEcoregionsTable(Base):
    __tablename__ = "resolve_ecoregions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    FID = Column(Integer, nullable=False)
    OBJECTID = Column(Integer, nullable=False)
    ecoregion_name = Column(String(255), nullable=True)
    biome_number = Column(Integer, nullable=True)
    biome_name = Column(String(255), nullable=True)
    realm_name = Column(String(255), nullable=True)
    ecoregion_biome = Column(String(255), nullable=True)
    nature_needs_half_number = Column(Integer, nullable=True)
    ecoregion_unique_id = Column(Integer, nullable=True)
    shape_leng = Column(Float, nullable=True)
    nature_needs_half_description = Column(String(255), nullable=True)
    color = Column(String(50), nullable=True)
    biome_color = Column(String(50), nullable=True)
    nature_needs_half_color = Column(String(50), nullable=True)
    license = Column(String(255), nullable=True)
    shape_area = Column(Float, nullable=True)
    shape_length = Column(Float, nullable=True)

    # Relationship to ExternalSamplingTable
    external_samples = relationship(
        "ExternalSamplingTable", back_populates="ecoregion"
    )
    # Define relationship with sequencing_samples
    sequencing_samples = relationship(
        "SequencingSamplesTable",
        back_populates="resolve_ecoregion",
        cascade="save-update",
    )


class ExternalSamplingTable(Base):
    __tablename__ = "external_sampling"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sample_id = Column(String(255), nullable=True)
    dna_region = Column(String(3), nullable=True)
    longitude = Column(String(255), nullable=True)
    latitude = Column(String(255), nullable=True)

    # Foreign Key Relationship
    resolve_ecoregion_id = Column(
        Integer, ForeignKey("resolve_ecoregions.id"), nullable=True
    )
    ecoregion = relationship(
        "ResolveEcoregionsTable", back_populates="external_samples"
    )

    __table_args__ = (Index("idx_dna_region", dna_region),)
