from contextlib import contextmanager
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
        email = email.strip().lower()
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
    def delete(cls, user_id, session=None):
        """
        Deletes a preapproved user from the database
        using the provided session.
        If no session is provided, it will create
        a new one using session_scope().
        """

        # Import session_scope only if needed, as per your original code
        # We need to explicitly handle it for the test
        import helpers.dbm as original_dbm_module

        to_return = {"status": 0, "message": "Not run"}
        own_session = False

        if session is None:
            own_session = True
            # Use the actual session_scope from helpers.dbm
            session_context = original_dbm_module.session_scope()
        else:
            # make a fake context manager that does nothing
            @contextmanager
            def dummy_scope():
                yield session

            session_context = dummy_scope()

        with session_context as s:
            user_db = (
                s.query(PreapprovedUsersTable).filter_by(id=user_id).first()
            )
            if user_db:
                s.delete(user_db)
                if own_session:
                    s.commit()
                to_return = {"status": 1, "message": "Success"}
            else:
                # Add a message for when user is not found, to clarify behavior
                to_return["message"] = "User not found"
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
