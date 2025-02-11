from flask_login import UserMixin

from helpers.dbm import session_scope
from models.db_model import (
    UserTable,
    BucketTable,
    UserGroupsTable,
    SequencingUploadsTable,
    user_groups_association,
)
from sqlalchemy import func
from sqlalchemy.orm import subqueryload
import logging

logger = logging.getLogger("my_app_logger")  # Use the same name as in app.py


class User(UserMixin):
    def __init__(
        self,
        id_,
        name,
        email,
        profile_pic,
        admin,
        approved,
        goodgrands_slug=None,
        buckets=None,
        groups=None,
        spun_staff=False,
    ):
        self.id = id_
        self.name = name
        self.email = email
        self.profile_pic = profile_pic
        self.admin = admin
        self.approved = approved
        self.goodgrands_slug = goodgrands_slug
        self.buckets = buckets or []
        self.groups = groups
        self.spun_staff = spun_staff

    @classmethod
    def get(cls, user_id):
        with session_scope() as session:

            user_db = session.query(UserTable).filter_by(id=user_id).first()
            if not user_db:
                return None

            user_buckets = user_db.buckets
            buckets = [bucket.id for bucket in user_buckets]

            # Check if the user belongs to the group with id=4
            spun_staff = any(group.id == 4 for group in user_db.groups)

            user = User(
                id_=user_db.id,
                name=user_db.name,
                email=user_db.email,
                profile_pic=user_db.profile_pic,
                admin=user_db.admin,
                goodgrands_slug=user_db.goodgrands_slug,
                approved=user_db.approved,
                buckets=buckets,
                spun_staff=spun_staff,
            )

            return user

    @classmethod
    def create(
        cls,
        id_,
        name,
        email,
        profile_pic,
        admin=False,
        approved=False,
        goodgrands_slug=None,
    ):
        with session_scope() as session:

            new_user = UserTable(
                id=id_,
                name=name,
                email=email,
                profile_pic=profile_pic,
                admin=admin,
                approved=approved,
                goodgrands_slug=goodgrands_slug,
            )

            session.add(new_user)
            session.commit()

            return id_

    @classmethod
    def get_all(cls):
        with session_scope() as session:

            # Subquery to get group names per user
            groups_subquery = (
                session.query(
                    user_groups_association.c.user_id,
                    func.group_concat(UserGroupsTable.name).label("groups"),
                )
                .join(
                    UserGroupsTable,
                    UserGroupsTable.id == user_groups_association.c.group_id,
                )
                .group_by(user_groups_association.c.user_id)
                .subquery()
            )

            # Subquery to count sequencing uploads per user
            sequencing_uploads_subquery = (
                session.query(
                    SequencingUploadsTable.user_id,
                    func.count(SequencingUploadsTable.id).label(
                        "uploads_v2_count"
                    ),
                )
                .group_by(SequencingUploadsTable.user_id)
                .subquery()
            )

            # Main query to get users along with aggregated upload
            # data, group names, and sequencing uploads count
            all_users_db = (
                session.query(
                    UserTable,
                    func.coalesce(groups_subquery.c.groups, "").label(
                        "groups"
                    ),
                    func.coalesce(
                        sequencing_uploads_subquery.c.uploads_v2_count, 0
                    ).label("uploads_v2_count"),
                )
                .outerjoin(
                    groups_subquery, UserTable.id == groups_subquery.c.user_id
                )
                .outerjoin(
                    sequencing_uploads_subquery,
                    UserTable.id == sequencing_uploads_subquery.c.user_id,
                )
                .options(
                    subqueryload(UserTable.buckets),  # Load buckets eagerly
                    subqueryload(UserTable.groups),  # Load groups eagerly
                )
                .all()
            )

            all_users = []
            for (
                user_db,
                groups_str,
                uploads_v2_count,
            ) in all_users_db:
                user_buckets = [bucket.id for bucket in user_db.buckets]
                user_groups = groups_str.split(",") if groups_str else []
                user_info = {
                    "user": User(
                        id_=user_db.id,
                        name=user_db.name,
                        email=user_db.email,
                        profile_pic=user_db.profile_pic,
                        admin=user_db.admin,
                        approved=user_db.approved,
                        goodgrands_slug=user_db.goodgrands_slug,
                        buckets=user_buckets,
                        groups=user_groups,
                    ),
                    "uploads_v2_count": uploads_v2_count,
                }
                all_users.append(user_info)

            return all_users

    @classmethod
    def update_admin_status(cls, user_id, new_admin_status):
        with session_scope() as session:

            user_db = session.query(UserTable).filter_by(id=user_id).first()

            if user_db:
                user_db.admin = new_admin_status
                session.commit()

    @classmethod
    def add_user_bucket_access(cls, user_id, bucket_name):
        with session_scope() as session:

            user = session.query(UserTable).filter_by(id=user_id).first()
            if user:
                bucket = (
                    session.query(BucketTable)
                    .filter_by(id=bucket_name)
                    .first()
                )
                if bucket:
                    user.buckets.append(bucket)
                    session.commit()
                else:
                    raise ValueError(f"Bucket '{bucket_name}' not found")
            else:
                raise ValueError(f"User with ID '{user_id}' not found")

    @classmethod
    def add_user_goodgrands_slug(cls, user_id, goodgrands_slug):
        with session_scope() as session:

            user_db = session.query(UserTable).filter_by(id=user_id).first()

            if user_db:
                user_db.goodgrands_slug = goodgrands_slug
                session.commit()

    @classmethod
    def add_user_group_access(cls, user_id, group_id):
        with session_scope() as session:
            # Find the user by ID
            user = session.query(UserTable).filter_by(id=user_id).first()
            if not user:
                raise ValueError(f"User with ID '{user_id}' not found")

            # Find the group by ID
            group = (
                session.query(UserGroupsTable).filter_by(id=group_id).first()
            )
            if not group:
                raise ValueError(f"Group with ID '{group_id}' not found")

            # Add the user to the group
            if group not in user.groups:
                user.groups.append(group)
                session.commit()

    @classmethod
    def delete_user_group_access(cls, user_id, group_name):
        with session_scope() as session:

            # Find the user by ID
            user = session.query(UserTable).filter_by(id=user_id).first()
            if not user:
                raise ValueError(f"User with ID '{user_id}' not found")

            # Find the group by name
            group = (
                session.query(UserGroupsTable)
                .filter_by(name=group_name)
                .first()
            )
            if not group:
                raise ValueError(f"Group with name '{group_name}' not found")

            # Remove the user from the group if present
            if group in user.groups:
                user.groups.remove(group)
                session.commit()

    @classmethod
    def delete_user_bucket_access(cls, user_id, bucket_name):
        with session_scope() as session:

            user = session.query(UserTable).filter_by(id=user_id).first()
            if user:
                bucket = (
                    session.query(BucketTable)
                    .filter_by(id=bucket_name)
                    .first()
                )
                if bucket:
                    user.buckets.remove(bucket)
                    session.commit()
                else:
                    raise ValueError(f"Bucket '{bucket_name}' not found")
            else:
                raise ValueError(f"User with ID '{user_id}' not found")

    @classmethod
    def update_approved_status(cls, user_id, new_approved_status):
        with session_scope() as session:

            user_db = session.query(UserTable).filter_by(id=user_id).first()

            if user_db:
                user_db.approved = new_approved_status
                session.commit()

    @classmethod
    def has_bucket_access(cls, user_id, bucket_name):
        with session_scope() as session:

            user = session.query(UserTable).filter_by(id=user_id).first()
            if user:
                # Explicitly load the buckets relationship before closing the
                # session
                user_buckets = user.buckets  # This will trigger a lazy load
                return bucket_name in [bucket.id for bucket in user_buckets]
            else:
                raise ValueError(f"User with ID '{user_id}' not found")

    @classmethod
    def is_user_in_group_by_name(cls, user_id, group_name):
        with session_scope() as session:

            # Find the user by ID
            user = session.query(UserTable).filter_by(id=user_id).first()
            if not user:
                raise ValueError(f"User with ID '{user_id}' not found")

            # Find the group by name
            group = (
                session.query(UserGroupsTable)
                .filter_by(name=group_name)
                .first()
            )
            if not group:
                raise ValueError(f"Group with name '{group_name}' not found")

            # Explicitly load the groups relationship
            # before closing the session
            user_groups = user.groups  # This will trigger a lazy load

            return group in user_groups

    @classmethod
    def delete(cls, user_id):
        with session_scope() as session:
            to_return = {"status": 0, "message": "Not run"}
            # Check if the user has uploads
            uploads_count = (
                session.query(func.count(SequencingUploadsTable.id))
                .filter_by(user_id=user_id)
                .scalar()
            )

            if uploads_count == 0:
                user_db = (
                    session.query(UserTable).filter_by(id=user_id).first()
                )
                if user_db:
                    # Delete user's bucket accesses
                    for bucket in user_db.buckets:
                        user_db.buckets.remove(bucket)

                    # Delete the user
                    session.delete(user_db)
                    session.commit()
                    to_return = {"status": 1, "message": "Success"}
                else:
                    to_return = {
                        "status": 0,
                        "message": "Not deleted. User doesnt exist",
                    }
            else:
                to_return = {
                    "status": 0,
                    "message": "Not deleted. Uploads exist",
                }
            return to_return

    @classmethod
    def get_user_groups(cls, user_id):
        with session_scope() as session:
            user = (
                session.query(UserTable)
                .filter_by(id=user_id)
                .options(
                    subqueryload(UserTable.groups)
                )  # Use subqueryload to load related groups
                .first()
            )

            if not user:
                raise ValueError(f"User with ID '{user_id}' not found")

            # Return a list of dictionaries representing the group details
            user_groups_list = [
                {"id": group.id, "name": group.name, "version": group.version}
                for group in user.groups
            ]

            return user_groups_list
