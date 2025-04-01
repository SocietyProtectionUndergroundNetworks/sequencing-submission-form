# -*- coding: utf-8 -*-
from contextlib import contextmanager
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
import os


def connect_db():
    db_engine = create_engine(
        "mysql+mysqldb://{0}:{1}@{2}:{4}/{3}?charset=utf8mb4".format(
            os.environ["MYSQL_USER"],
            os.environ["MYSQL_PASSWORD"],
            os.environ["MYSQL_HOST"],
            os.environ["MYSQL_DATABASE"],
            os.environ["MYSQL_PORT"],
        ),
        pool_recycle=3600,
    )
    return db_engine


@contextmanager
def session_scope():
    """Provide a transactional scope around a series of operations."""
    db_engine = connect_db()
    session = sessionmaker(bind=db_engine, autoflush=False)()
    try:
        yield session  # Provide the session for use
        session.commit()  # Commit any changes made inside the block
    except Exception:
        session.rollback()  # Rollback on error
        raise
    finally:
        session.close()  # Always close the session


# To delete when I have removed all of them
def get_session(db_engine):
    # https://docs.sqlalchemy.org/en/13/orm/session_api.html#session-and-sessionmaker
    Session_mysql = sessionmaker(autoflush=False)
    session = Session_mysql(bind=db_engine)
    return session
