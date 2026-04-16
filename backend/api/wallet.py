from fastapi import APIRouter, Depends, HTTPException
from backend.schemas.schemas import WalletResponse, WalletModify, StandardResponse
from infrastructure.database import get_db
from sqlalchemy.orm import Session
from services.wallet_service import get_balance, deposit, deduct

router = APIRouter(prefix="/api/wallet", tags=["wallet"])


@router.get("/{username}", response_model=WalletResponse)
def wallet_get(username: str, db: Session = Depends(get_db)):
    balance = get_balance(db, username)
    return {"username": username, "balance": balance}


@router.post("/deposit", response_model=StandardResponse)
def wallet_deposit(body: WalletModify, db: Session = Depends(get_db)):
    ok, balance = deposit(db, body.username, body.amount)
    if not ok:
        raise HTTPException(status_code=400, detail="Invalid deposit")
    return {"status": "ok", "detail": f"new_balance: {balance}"}


@router.post("/deduct", response_model=StandardResponse)
def wallet_deduct(body: WalletModify, db: Session = Depends(get_db)):
    ok, balance = deduct(db, body.username, body.amount)
    if not ok:
        raise HTTPException(status_code=400, detail="Insufficient funds or invalid amount")
    return {"status": "ok", "detail": f"new_balance: {balance}"}
