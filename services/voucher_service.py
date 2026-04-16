from typing import List, Dict
from datetime import datetime
from sqlalchemy.orm import Session
from backend.models.models import Voucher
from services.user_service import get_or_create_user
from services.wallet_service import deposit as wallet_deposit


def import_vouchers(db: Session, vouchers: List[Dict]) -> int:
    created = 0
    for item in vouchers:
        code = item.get("code")
        value = float(item.get("value", 0))
        if not code:
            continue
        existing = db.query(Voucher).filter(Voucher.code == code).one_or_none()
        if existing:
            continue
        v = Voucher(code=code, value=value, status="unused", created_at=datetime.utcnow())
        db.add(v)
        created += 1
    db.commit()
    return created


def use_voucher(db: Session, code: str, username: str) -> Dict:
    voucher = db.query(Voucher).filter(Voucher.code == code).one_or_none()
    if not voucher:
        return {"ok": False, "reason": "not_found"}
    if voucher.status != "unused":
        return {"ok": False, "reason": "already_used"}
    voucher.status = "used"
    voucher.used_at = datetime.utcnow()
    db.add(voucher)
    # ensure user exists
    get_or_create_user(db, username)
    # credit wallet
    wallet_deposit(db, username, float(voucher.value))
    db.commit()
    return {"ok": True, "value": float(voucher.value)}
