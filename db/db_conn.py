import os


def get_database_uri():
    # Allow full override using DATABASE_URL
    if "DATABASE_URL" in os.environ:
        return os.environ["DATABASE_URL"]

    DB_USER = os.environ["MYSQL_USER"]
    DB_PASSWORD = os.environ["MYSQL_PASSWORD"]
    DB_HOST = os.environ["MYSQL_HOST"]
    DB_PORT = os.environ["MYSQL_PORT"]
    DB_NAME = os.environ["MYSQL_DATABASE"]

    SQLALCHEMY_DATABASE_URI = (
        f"mysql+mysqldb://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:"
        f"{DB_PORT}/{DB_NAME}?charset=utf8mb4"
    )
    return SQLALCHEMY_DATABASE_URI
