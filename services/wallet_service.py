from typing import Tuple
from sqlalchemy.orm import Session
from datetime import datetime
from backend.models.models import User, Transaction


def get_balance(db: Session, username: str) -> float:
    user = db.query(User).filter(User.username == username).one_or_none()
    if not user:
        return 0.0
    return float(user.balance or 0.0)


def deposit(db: Session, username: str, amount: float) -> Tuple[bool, float]:
    if amount <= 0:
        return False, 0.0
    user = db.query(User).filter(User.username == username).one_or_none()
    if not user:
        from services.user_service import get_or_create_user
        user = get_or_create_user(db, username)
    user.balance = (user.balance or 0.0) + amount
    tx = Transaction(username=username, amount=amount, type="deposit", created_at=datetime.utcnow())
    db.add(tx)
    db.add(user)
    db.commit()
    db.refresh(user)
    return True, float(user.balance)


def deduct(db: Session, username: str, amount: float) -> Tuple[bool, float]:
    if amount <= 0:
        return False, 0.0
    user = db.query(User).filter(User.username == username).one_or_none()
    if not user or (user.balance or 0.0) < amount:
        return False, 0.0
    user.balance = (user.balance or 0.0) - amount
    tx = Transaction(username=username, amount=-amount, type="deduct", created_at=datetime.utcnow())
    db.add(tx)
    db.add(user)
    db.commit()
    db.refresh(user)
    return True, float(user.balance)
