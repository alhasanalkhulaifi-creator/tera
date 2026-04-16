from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime
from infrastructure.database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    mac = Column(String, unique=True, index=True, nullable=True)
    balance = Column(Float, default=0.0, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class UsageLog(Base):
    __tablename__ = "usage_logs"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True, nullable=False)
    bytes_in = Column(Integer, default=0, nullable=False)
    bytes_out = Column(Integer, default=0, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)


class Voucher(Base):
    __tablename__ = "vouchers"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String, unique=True, index=True, nullable=False)
    value = Column(Float, default=0.0, nullable=False)
    status = Column(String, default="unused", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    used_at = Column(DateTime, nullable=True)


class Transaction(Base):
    __tablename__ = "transactions"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True, nullable=False)
    amount = Column(Float, nullable=False)
    type = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
