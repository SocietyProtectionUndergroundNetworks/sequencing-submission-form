from helpers.dbm import session_scope
from models.db_model import PreapprovedUsersTable
import logging

logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class PreapprovedUser:
    def __init__(self, id, email, bucket=None, group_id=None):
        self.id = id
        self.email = email
        self.bucket = bucket or ""
        self.group_id = group_id or ""

    @classmethod
    def get(cls, user_id):
        with session_scope() as session:
            user_db = (
                session.query(PreapprovedUsersTable)
                .filter_by(id=user_id)
                .first()
            )
            if not user_db:
                return None

            user = PreapprovedUser(
                id=user_db.id,
                email=user_db.email,
                bucket=user_db.bucket,
                group_id=user_db.group_id,
            )

            return user

    @classmethod
    def create(cls, email, bucket, group_id):
        with session_scope() as session:
            new_user = PreapprovedUsersTable(
                email=email,
                bucket=bucket,
                group_id=group_id,
            )

            session.add(new_user)
            session.commit()

            return id

    @classmethod
    def delete(cls, user_id):
        with session_scope() as session:
            to_return = {"status": 0, "message": "Not run"}

            user_db = (
                session.query(PreapprovedUsersTable)
                .filter_by(id=user_id)
                .first()
            )
            if user_db:

                # Delete the user
                session.delete(user_db)
                session.commit()
                to_return = {"status": 1, "message": "Success"}

            return to_return

    @classmethod
    def get_all(cls):
        with session_scope() as session:
            users_db = session.query(PreapprovedUsersTable).all()
            users = [
                PreapprovedUser(
                    id=user.id,
                    email=user.email,
                    bucket=user.bucket,
                    group_id=user.group_id,
                )
                for user in users_db
            ]

            return users

    @classmethod
    def get_by_email(cls, email):
        with session_scope() as session:
            user_db = (
                session.query(PreapprovedUsersTable)
                .filter_by(email=email)
                .first()
            )
            if not user_db:
                return None

            user = PreapprovedUser(
                id=user_db.id,
                email=user_db.email,
                bucket=user_db.bucket,
                group_id=user_db.group_id,
            )
            return user
