from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, ForeignKey
from .database import Base
from datetime import datetime


class Session(Base):
    __tablename__ = 'sessions'

    id = Column(Integer, primary_key=True, index=True)
    # map to existing DB column 'card' while using attribute name 'card_number'
    card_number = Column('card', String(50), index=True)
    ip = Column('ip', String(50))
    mac = Column('mac', String(50))
    download = Column('download', BigInteger, default=0)
    upload = Column('upload', BigInteger, default=0)
    uptime = Column('uptime', String(50))
    profile = Column('profile', String(100))
    active = Column('active', Boolean)
    created_at = Column('created_at', DateTime, default=datetime.utcnow)
    from_time = Column('from_time', String(100), index=True)


class Card(Base):
    __tablename__ = 'cards'

    id = Column(Integer, primary_key=True, index=True)
    code = Column('code', String(100), unique=True, index=True, nullable=False)
    # category is the canonical name for card grouping (e.g., 200/500/1000)
    category = Column('category', String(50), index=True)
    # keep profile for backward compatibility
    profile = Column('profile', String(50), index=True)
    price = Column('price', Integer)
    status = Column('status', String(20), default='available', index=True)
    assigned_to = Column('assigned_to', String(50), nullable=True)
    user_id = Column('user_id', Integer, ForeignKey('users.id'), nullable=True, index=True)
    order_id = Column('order_id', Integer, ForeignKey('orders.id'), nullable=True, index=True)
    reserved_at = Column('reserved_at', DateTime, nullable=True)
    sold_at = Column('sold_at', DateTime, nullable=True)
    created_at = Column('created_at', DateTime, default=datetime.utcnow)


class User(Base):
    __tablename__ = 'users'

    id = Column(Integer, primary_key=True, index=True)
    phone = Column('phone', String(50), unique=True, index=True, nullable=False)
    balance = Column('balance', BigInteger, default=0)
    created_at = Column('created_at', DateTime, default=datetime.utcnow)


class Transaction(Base):
    __tablename__ = 'transactions'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column('user_id', Integer, index=True)
    amount = Column('amount', BigInteger)
    type = Column('type', String(20))
    balance_before = Column('balance_before', BigInteger, default=0)
    balance_after = Column('balance_after', BigInteger, default=0)
    reference_id = Column('reference_id', String(100), unique=True, index=True, nullable=True)
    status = Column('status', String(20), default='success')
    created_at = Column('created_at', DateTime, default=datetime.utcnow)


class Order(Base):
    __tablename__ = 'orders'

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column('user_id', Integer, index=True, nullable=False)
    card_id = Column('card_id', Integer, index=True, nullable=True)
    price = Column('price', BigInteger)
    reference_id = Column('reference_id', String(100), unique=True, index=True, nullable=True)
    status = Column('status', String(20), default='pending')
    created_at = Column('created_at', DateTime, default=datetime.utcnow)


class ApiKey(Base):
    __tablename__ = 'api_keys'

    id = Column(Integer, primary_key=True, index=True)
    key = Column('key', String(128), unique=True, index=True, nullable=False)
    name = Column('name', String(100), nullable=True)
    revoked = Column('revoked', Boolean, default=False)
    expires_at = Column('expires_at', DateTime, nullable=True)
    created_at = Column('created_at', DateTime, default=datetime.utcnow)
