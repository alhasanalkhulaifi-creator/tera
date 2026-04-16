from sqlalchemy.orm import Session
from datetime import datetime
from backend.models.models import User


def get_or_create_user(db: Session, username: str, mac: str = None) -> User:
    user = db.query(User).filter(User.username == username).one_or_none()
    if user:
        if mac and user.mac != mac:
            user.mac = mac
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    user = User(username=username, mac=mac, created_at=datetime.utcnow())
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
