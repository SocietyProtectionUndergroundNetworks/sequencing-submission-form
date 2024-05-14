# -*- coding: utf-8 -*-
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.sql import and_, not_, select, exists, text

import os
import time

from models.db_model import Base  # Import your models from db_model.py

def connect_db():
    db_engine = create_engine(
        'mysql+mysqldb://{0}:{1}@{2}:{4}/{3}?charset=utf8mb4'.format(
            os.environ['MYSQL_USER'],
            os.environ['MYSQL_PASSWORD'],
            os.environ['MYSQL_HOST'],
            os.environ['MYSQL_DATABASE'],
            os.environ['MYSQL_PORT']
        ),
        pool_recycle=3600
    )   
    return db_engine

def get_session(db_engine):
    # https://docs.sqlalchemy.org/en/13/orm/session_api.html#session-and-sessionmaker
    Session_mysql = sessionmaker(autoflush=False)
    session = Session_mysql(bind=db_engine)
    return session

