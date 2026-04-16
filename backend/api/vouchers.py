from fastapi import APIRouter, Depends, HTTPException
from backend.schemas.schemas import VoucherImportRequest, VoucherUseRequest, StandardResponse
from infrastructure.database import get_db
from sqlalchemy.orm import Session
from services.voucher_service import import_vouchers, use_voucher

router = APIRouter(prefix="/api/vouchers", tags=["vouchers"])


@router.post("/import", response_model=StandardResponse)
def import_vouchers_endpoint(body: VoucherImportRequest, db: Session = Depends(get_db)):
    created = import_vouchers(db, [v.dict() for v in body.vouchers])
    return {"status": "ok", "detail": f"imported={created}"}


@router.post("/use", response_model=StandardResponse)
def use_voucher_endpoint(body: VoucherUseRequest, db: Session = Depends(get_db)):
    result = use_voucher(db, body.code, body.username)
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("reason"))
    return {"status": "ok", "detail": f"value={result.get('value')}"}
