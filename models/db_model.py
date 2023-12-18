# helpers/db_model.py

from sqlalchemy import Column, Integer, String, Boolean, DateTime, func, BigInteger
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class UserTable(Base):
    __tablename__ = 'users'

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=False)
    profile_pic = Column(String(255), nullable=False)
    admin = Column(Boolean, default=False)

        
class UploadTable(Base):
    __tablename__ = 'uploads'

    id = Column(Integer, primary_key=True)
    user_id = Column(String(36), default=lambda: str(uuid.uuid4()), index=True)
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