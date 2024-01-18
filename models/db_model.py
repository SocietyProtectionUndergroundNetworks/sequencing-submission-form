# helpers/db_model.py
from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, BigInteger, ForeignKey
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

class UserTable(Base):
    __tablename__ = 'users'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    profile_pic = Column(String(255), nullable=False)
    admin = Column(Boolean, default=False)
    uploads = relationship("UploadTable", backref="user")

        
class UploadTable(Base):
    __tablename__ = 'uploads'

    id = Column(Integer, primary_key=True)
    user_id = Column(String(36), ForeignKey('users.id', ondelete='CASCADE'))
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(
        DateTime, 
        default=func.now(), 
        onupdate=func.now(), 
        nullable=True
    )
    uploads_folder = Column(String(20), nullable=True)
    csv_uploaded = Column(Boolean, default=False)
    csv_filename = Column(String(255), nullable=True)
    gz_uploaded = Column(Boolean, default=False)
    gz_filename = Column(String(255), nullable=True)
    gz_sent_to_bucket = Column(Boolean, default=False)
    gz_sent_to_bucket_progress = Column(Integer, default=0)
    gz_unziped = Column(Boolean, default=False)
    gz_unziped_progress = Column(Integer, default=0)
    files_json = Column(JSON(none_as_null=True))
    files_renamed = Column(Boolean, default=False)
    fastqc_run = Column(Boolean, default=False)
    fastqc_files_progress = Column(Integer, default=0)
    fastqc_process_id = Column(String(255), nullable=True, index=True)
    fastqc_sent_to_bucket = Column(Boolean, default=False)
    renamed_sent_to_bucket = Column(Boolean, default=False)
    renamed_sent_to_bucket_progress = Column(Integer, default=0)