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
)
from sqlalchemy.dialects.mysql import JSON
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
    buckets = relationship(
        "BucketTable", secondary=association_table, backref="users"
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
