from flask_login import UserMixin

from helpers.dbm import connect_db, get_session
from models.db_model import UserTable, UploadTable
from sqlalchemy import func


class User(UserMixin):
    def __init__(self, id_, name, email, profile_pic, admin, approved):
        self.id = id_
        self.name = name
        self.email = email
        self.profile_pic = profile_pic
        self.admin = admin
        self.approved = approved

    @classmethod
    def get(cls, user_id):
        db_engine = connect_db()
        session = get_session(db_engine)
        
        user_db = session.query(UserTable).filter_by(id=user_id).first()
        
        session.close()
        
        if not user_db:
            return None

        user = User(
            id_=user_db.id, name=user_db.name, email=user_db.email, profile_pic=user_db.profile_pic, admin=user_db.admin, approved=user_db.approved
        )
        
        return user

    @classmethod
    def create(cls, id_, name, email, profile_pic, admin=False, approved=False):
        db_engine = connect_db()
        session = get_session(db_engine)
        
        new_user = UserTable(id=id_, name=name, email=email, profile_pic=profile_pic, admin=admin, approved=approved)
        
        session.add(new_user)
        session.commit()
        
        session.close()
        
        return id_
        
    @classmethod
    def get_all(cls):
        db_engine = connect_db()
        session = get_session(db_engine)
        
        all_users_db = session.query(UserTable, func.count(UploadTable.id)).outerjoin(UploadTable).group_by(UserTable.id).all()
        
        session.close()
        
        if not all_users_db:
            return []
        
        all_users = [
            {
                'user': User(
                    id_=user_db[0].id, name=user_db[0].name, email=user_db[0].email,
                    profile_pic=user_db[0].profile_pic, admin=user_db[0].admin, 
                    approved=user_db[0].approved
                ),
                'uploads_count': user_db[1] if user_db[1] else 0
            }
            for user_db in all_users_db
        ]
        
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
    def update_approved_status(cls, user_id, new_approved_status):
        db_engine = connect_db()
        session = get_session(db_engine)

        user_db = session.query(UserTable).filter_by(id=user_id).first()

        if user_db:
            user_db.approved = new_approved_status
            session.commit()

        session.close()