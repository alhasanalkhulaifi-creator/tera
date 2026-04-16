from typing import Optional, List
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


class ReportIn(BaseModel):
    username: str
    mac: str
    bytes_in: int
    bytes_out: int
    uptime: Optional[str] = None


class WalletResponse(BaseModel):
    username: str
    balance: float


class WalletModify(BaseModel):
    username: str
    amount: float


class VoucherImportItem(BaseModel):
    code: str
    value: float


class VoucherImportRequest(BaseModel):
    vouchers: List[VoucherImportItem]


class VoucherUseRequest(BaseModel):
    code: str
    username: str


class StandardResponse(BaseModel):
    status: str
    detail: Optional[str] = None
