from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class SessionOut(BaseModel):
    id: int
    card_number: Optional[str]
    ip: Optional[str]
    mac: Optional[str]
    download: int
    upload: int
    uptime: Optional[str]
    profile: Optional[str]
    active: Optional[bool]
    created_at: Optional[datetime]

    class Config:
        orm_mode = True


class CardImportIn(BaseModel):
    codes: list[str]
    category: str
    price: int


class CardBuyIn(BaseModel):
    category: str
    user_id: int
    user_phone: Optional[str] = None
    order_reference: str = Field(..., min_length=1, max_length=100)


class CardOut(BaseModel):
    id: int
    code: str
    category: str
    price: int
    status: str
    assigned_to: Optional[str] = None
    user_id: Optional[int]
    created_at: Optional[datetime]

    class Config:
        orm_mode = True


class TransactionOut(BaseModel):
    id: int
    user_id: int
    amount: int
    type: str
    balance_before: int
    balance_after: int
    reference_id: Optional[str]
    status: str
    created_at: Optional[datetime]

    class Config:
        orm_mode = True


class OrderOut(BaseModel):
    id: int
    user_id: int
    card_id: int
    price: int
    status: str
    created_at: Optional[datetime]

    class Config:
        orm_mode = True


class WalletDepositIn(BaseModel):
    phone: str
    amount: int
    reference_id: Optional[str] = None


class WalletOut(BaseModel):
    phone: str
    balance: int
    transactions: list[TransactionOut]

    class Config:
        orm_mode = True
