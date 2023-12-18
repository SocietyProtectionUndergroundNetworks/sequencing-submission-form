from flask_login import UserMixin

from helpers.dbm import connect_db, get_session
from models.db_model import UserTable

class User(UserMixin):
    def __init__(self, id_, name, email, profile_pic, admin):
        self.id = id_
        self.name = name
        self.email = email
        self.profile_pic = profile_pic
        self.admin = admin

    @classmethod
    def get(cls, user_id):
        db_engine = connect_db()
        session = get_session(db_engine)
        
        user_db = session.query(UserTable).filter_by(id=user_id).first()
        
        session.close()
        
        if not user_db:
            return None

        user = User(
            id_=user_db.id, name=user_db.name, email=user_db.email, profile_pic=user_db.profile_pic, admin=user_db.admin
        )
        
        return user

    @classmethod
    def create(cls, id_, name, email, profile_pic, admin=False):
        db_engine = connect_db()
        session = get_session(db_engine)
        
        new_user = UserTable(id=id_, name=name, email=email, profile_pic=profile_pic, admin=admin)
        
        session.add(new_user)
        session.commit()
        
        session.close()
        
        return id_
