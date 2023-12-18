# -*- coding: utf-8 -*-
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.sql import and_, not_, select, exists, text

import os
import time

from helpers.db_model import Base, UserTable  # Import your models from db_model.py


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
    
def test_select(app):
    test3()
    db_engine = connect_db()
    session = get_session(db_engine)
    session.expire_all()
    sql_query = """SELECT test FROM test"""
    app.logger.info("SQL Query: " + sql_query)  # Log the SQL query
    result = session.execute(text(sql_query))
    nr = ''
    for row in result:
        app.logger.info("SQL result: " + str(row[0]))  # Log the SQL query
        nr = str(row[0])
    return nr

        
def test3():
    db_engine = connect_db()
    session = get_session(db_engine)
    with db_engine.connect() as conn:
        conn.execute(text("UPDATE test SET test = test+1;"))
        conn.commit()

