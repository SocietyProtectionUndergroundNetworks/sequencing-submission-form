from flask_login import UserMixin
from helpers.dbm import connect_db, get_session
from models.db_model import UserGroupsTable, UserTable
from models.db_model import user_groups_association
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
import logging

logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class UserGroups(UserMixin):
    def __init__(self, _id, name):
        self.id = _id
        self.name = name

    @classmethod
    def get(cls, group_id):
        try:
            # Establish a database connection
            db_engine = connect_db()
            session = get_session(db_engine)

            # Query the database for the group by id
            group = (
                session.query(UserGroupsTable).filter_by(id=group_id).first()
            )

            if group:
                return cls(group.id, group.name)
            else:
                return None
        except SQLAlchemyError as e:
            logger.error(f"Error getting user group with id {group_id}: {e}")
            return None
        finally:
            session.close()

    @classmethod
    def create(cls, name):
        try:
            # Establish a database connection
            db_engine = connect_db()
            session = get_session(db_engine)
            logger.info(name)
            # Create a new UserGroupsTable record
            new_group = UserGroupsTable(name=name)
            session.add(new_group)
            session.commit()

            # Return the created UserGroups instance
            return cls(new_group.id, new_group.name)
        except SQLAlchemyError as e:
            logger.error(f"Error creating user group with name {name}: {e}")
            session.rollback()
            return None
        finally:
            session.close()

    @classmethod
    def get_all_with_user_count(cls):
        try:
            # Establish a database connection
            db_engine = connect_db()
            session = get_session(db_engine)

            # Query to get all groups with user count
            result = (
                session.query(
                    UserGroupsTable.id,
                    UserGroupsTable.name,
                    func.count(UserTable.id).label("users_count"),
                )
                .outerjoin(
                    user_groups_association,
                    UserGroupsTable.id == user_groups_association.c.group_id,
                )
                .outerjoin(
                    UserTable,
                    UserTable.id == user_groups_association.c.user_id,
                )
                .group_by(UserGroupsTable.id, UserGroupsTable.name)
                .all()
            )

            # Convert query result to a list of dictionaries or objects
            all_groups = [
                {
                    "id": group.id,
                    "name": group.name,
                    "users_count": group.users_count,
                }
                for group in result
            ]

            return all_groups
        except SQLAlchemyError as e:
            logger.error(f"Error fetching groups with user count: {e}")
            return []
        finally:
            session.close()
