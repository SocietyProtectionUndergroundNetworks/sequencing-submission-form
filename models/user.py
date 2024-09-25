from flask_login import UserMixin

from helpers.dbm import connect_db, get_session
from models.db_model import (
    UserTable,
    UploadTable,
    BucketTable,
    UserGroupsTable,
    SequencingUploadsTable,
    user_groups_association,
)
from sqlalchemy import func, case
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

    @classmethod
    def get(cls, user_id):
        db_engine = connect_db()
        session = get_session(db_engine)

        user_db = session.query(UserTable).filter_by(id=user_id).first()
        if not user_db:
            return None

        user_buckets = user_db.buckets
        buckets = [bucket.id for bucket in user_buckets]
        session.close()

        user = User(
            id_=user_db.id,
            name=user_db.name,
            email=user_db.email,
            profile_pic=user_db.profile_pic,
            admin=user_db.admin,
            goodgrands_slug=user_db.goodgrands_slug,
            approved=user_db.approved,
            buckets=buckets,
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
        db_engine = connect_db()
        session = get_session(db_engine)

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

        session.close()

        return id_

    @classmethod
    def get_all(cls):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Subquery to get counts of uploads per user
        uploads_subquery = (
            session.query(
                UploadTable.user_id,
                func.count(UploadTable.id).label("uploads_count"),
                func.sum(
                    case(
                        (UploadTable.reviewed_by_admin.is_(False), 1), else_=0
                    )
                ).label("reviewed_false_count"),
                func.sum(
                    case((UploadTable.reviewed_by_admin.is_(True), 1), else_=0)
                ).label("reviewed_true_count"),
            )
            .group_by(UploadTable.user_id)
            .subquery()
        )

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
                func.coalesce(uploads_subquery.c.uploads_count, 0).label(
                    "uploads_count"
                ),
                func.coalesce(
                    uploads_subquery.c.reviewed_false_count, 0
                ).label("reviewed_false_count"),
                func.coalesce(uploads_subquery.c.reviewed_true_count, 0).label(
                    "reviewed_true_count"
                ),
                func.coalesce(groups_subquery.c.groups, "").label("groups"),
                func.coalesce(
                    sequencing_uploads_subquery.c.uploads_v2_count, 0
                ).label("uploads_v2_count"),
            )
            .outerjoin(
                uploads_subquery, UserTable.id == uploads_subquery.c.user_id
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

        session.close()

        all_users = []
        for (
            user_db,
            uploads_count,
            reviewed_false_count,
            reviewed_true_count,
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
                "uploads_count": uploads_count,
                "reviewed_by_admin_count": reviewed_true_count,
                "uploads_v2_count": uploads_v2_count,
            }
            all_users.append(user_info)

        return all_users

    @classmethod
    def update_admin_status(cls, user_id, new_admin_status):
        db_engine = connect_db()
        session = get_session(db_engine)

        user_db = session.query(UserTable).filter_by(id=user_id).first()

        if user_db:
            user_db.admin = new_admin_status
            session.commit()

        session.close()

    @classmethod
    def add_user_bucket_access(cls, user_id, bucket_name):
        db_engine = connect_db()
        session = get_session(db_engine)

        user = session.query(UserTable).filter_by(id=user_id).first()
        if user:
            bucket = (
                session.query(BucketTable).filter_by(id=bucket_name).first()
            )
            if bucket:
                user.buckets.append(bucket)
                session.commit()
            else:
                session.close()
                raise ValueError(f"Bucket '{bucket_name}' not found")
        else:
            session.close()
            raise ValueError(f"User with ID '{user_id}' not found")

    @classmethod
    def add_user_goodgrands_slug(cls, user_id, goodgrands_slug):
        db_engine = connect_db()
        session = get_session(db_engine)

        user_db = session.query(UserTable).filter_by(id=user_id).first()

        if user_db:
            user_db.goodgrands_slug = goodgrands_slug
            session.commit()

        session.close()

    @classmethod
    def add_user_group_access(cls, user_id, group_id):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Find the user by ID
        user = session.query(UserTable).filter_by(id=user_id).first()
        if not user:
            session.close()
            raise ValueError(f"User with ID '{user_id}' not found")

        # Find the group by ID
        group = session.query(UserGroupsTable).filter_by(id=group_id).first()
        if not group:
            session.close()
            raise ValueError(f"Group with ID '{group_id}' not found")

        # Add the user to the group
        if group not in user.groups:
            user.groups.append(group)
            session.commit()

        session.close()

    @classmethod
    def delete_user_group_access(cls, user_id, group_name):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Find the user by ID
        user = session.query(UserTable).filter_by(id=user_id).first()
        if not user:
            session.close()
            raise ValueError(f"User with ID '{user_id}' not found")

        # Find the group by name
        group = (
            session.query(UserGroupsTable).filter_by(name=group_name).first()
        )
        if not group:
            session.close()
            raise ValueError(f"Group with name '{group_name}' not found")

        # Remove the user from the group if present
        if group in user.groups:
            user.groups.remove(group)
            session.commit()

        session.close()

    @classmethod
    def delete_user_bucket_access(cls, user_id, bucket_name):
        db_engine = connect_db()
        session = get_session(db_engine)

        user = session.query(UserTable).filter_by(id=user_id).first()
        if user:
            bucket = (
                session.query(BucketTable).filter_by(id=bucket_name).first()
            )
            if bucket:
                user.buckets.remove(bucket)
                session.commit()
            else:
                session.close()
                raise ValueError(f"Bucket '{bucket_name}' not found")
        else:
            session.close()
            raise ValueError(f"User with ID '{user_id}' not found")

    @classmethod
    def update_approved_status(cls, user_id, new_approved_status):
        db_engine = connect_db()
        session = get_session(db_engine)

        user_db = session.query(UserTable).filter_by(id=user_id).first()

        if user_db:
            user_db.approved = new_approved_status
            session.commit()

        session.close()

    @classmethod
    def has_bucket_access(cls, user_id, bucket_name):
        db_engine = connect_db()
        session = get_session(db_engine)

        user = session.query(UserTable).filter_by(id=user_id).first()
        if user:
            # Explicitly load the buckets relationship before closing the
            # session
            user_buckets = user.buckets  # This will trigger a lazy load
            session.close()
            return bucket_name in [bucket.id for bucket in user_buckets]
        else:
            session.close()
            raise ValueError(f"User with ID '{user_id}' not found")

    @classmethod
    def is_user_in_group_by_name(cls, user_id, group_name):
        db_engine = connect_db()
        session = get_session(db_engine)

        # Find the user by ID
        user = session.query(UserTable).filter_by(id=user_id).first()
        if not user:
            session.close()
            raise ValueError(f"User with ID '{user_id}' not found")

        # Find the group by name
        group = (
            session.query(UserGroupsTable).filter_by(name=group_name).first()
        )
        if not group:
            session.close()
            raise ValueError(f"Group with name '{group_name}' not found")

        # Explicitly load the groups relationship before closing the session
        user_groups = user.groups  # This will trigger a lazy load
        session.close()

        return group in user_groups

    @classmethod
    def delete(cls, user_id):
        db_engine = connect_db()
        session = get_session(db_engine)
        to_return = {"status": 0, "message": "Not run"}
        # Check if the user has uploads
        uploads_count = (
            session.query(func.count(UploadTable.id))
            .filter_by(user_id=user_id)
            .scalar()
        )

        if uploads_count == 0:
            user_db = session.query(UserTable).filter_by(id=user_id).first()
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
            to_return = {"status": 0, "message": "Not deleted. Uploads exist"}
        session.close()
        return to_return

    @classmethod
    def get_user_groups(cls, user_id):
        db_engine = connect_db()
        session = get_session(db_engine)

        try:
            # Fetch the user by user_id
            user = session.query(UserTable).filter_by(id=user_id).first()

            if not user:
                raise ValueError(f"User with ID '{user_id}' not found")

            # Assuming 'groups' is a relationship attribute in UserTable
            user_groups = (
                user.groups
            )  # This will fetch the groups associated with the user

            # Return the full group objects instead of just the names
            return user_groups

        finally:
            session.close()
