from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from .database import engine
from .schemas import WalletDepositIn, WalletOut, TransactionOut
from datetime import datetime
from sqlalchemy.exc import IntegrityError
from infrastructure.logger import logger

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.post("/deposit")
def deposit(payload: WalletDepositIn):
    """Create user if needed, add amount to balance, record transaction atomically with idempotency."""
    if payload.amount <= 0:
        raise HTTPException(status_code=400, detail='Amount must be positive')

    with engine.begin() as conn:
        # ensure user exists
        conn.execute(text("INSERT INTO users (phone, balance, created_at) VALUES (:phone, 0, now()) ON CONFLICT (phone) DO NOTHING"), {'phone': payload.phone})
        # lock user row to serialize deposits for this user
        row = conn.execute(text("SELECT id, balance FROM users WHERE phone = :phone FOR UPDATE"), {'phone': payload.phone}).fetchone()
        if not row:
            raise HTTPException(status_code=500, detail='Failed to create or fetch user')
        user_id = row[0]
        balance_before = int(row[1] or 0)
        # idempotency: if reference provided, check if transaction already exists
        if payload.reference_id:
            existing = conn.execute(text("SELECT id, status, balance_after FROM transactions WHERE reference_id = :ref_id"), {'ref_id': payload.reference_id}).fetchone()
            if existing:
                tx_id, tx_status, tx_balance_after = existing
                logger.info(f"Idempotent deposit request: ref={payload.reference_id} exists status={tx_status}")
                return {'phone': payload.phone, 'balance': int(tx_balance_after or 0), 'idempotent': True}

        try:
            # update balance
            conn.execute(text("UPDATE users SET balance = balance + :amt WHERE id = :uid"), {'amt': payload.amount, 'uid': user_id})
            # fetch new balance
            new_row = conn.execute(text("SELECT balance FROM users WHERE id = :uid"), {'uid': user_id}).fetchone()
            balance_after = int(new_row[0] or 0)

            # record transaction with audit fields
            conn.execute(text("INSERT INTO transactions (user_id, amount, type, balance_before, balance_after, reference_id, status, created_at) VALUES (:uid, :amt, 'deposit', :bb, :ba, :ref_id, 'success', now())"), {
                'uid': user_id,
                'amt': payload.amount,
                'bb': balance_before,
                'ba': balance_after,
                'ref_id': payload.reference_id
            })
        except IntegrityError as e:
            # unique constraint on reference_id may trigger here for concurrent requests
            logger.warning(f"IntegrityError during deposit insert: {e}")
            existing = conn.execute(text("SELECT id, status, balance_after FROM transactions WHERE reference_id = :ref_id"), {'ref_id': payload.reference_id}).fetchone()
            if existing:
                return {'phone': payload.phone, 'balance': int(existing[2] or 0), 'idempotent': True}
            raise HTTPException(status_code=500, detail='Deposit failed due to integrity error')
        except Exception as e:
            logger.error(f"Deposit failed for phone={payload.phone}: {e}")
            # record failed transaction if reference_id is provided
            if payload.reference_id:
                try:
                    conn.execute(text("INSERT INTO transactions (user_id, amount, type, balance_before, balance_after, reference_id, status, created_at) VALUES (:uid, :amt, 'deposit', :bb, :ba, :ref_id, 'failed', now())"), {
                        'uid': user_id,
                        'amt': payload.amount,
                        'bb': balance_before,
                        'ba': balance_before,
                        'ref_id': payload.reference_id
                    })
                except Exception:
                    logger.exception('Failed recording failed deposit tx')
            raise HTTPException(status_code=500, detail=f'Deposit failed: {str(e)}')

    return {'phone': payload.phone, 'balance': balance_after}


@router.get("/{phone}")
def wallet_info(phone: str):
    with engine.connect() as conn:
        user = conn.execute(text("SELECT id, phone, balance FROM users WHERE phone = :phone"), {'phone': phone}).fetchone()
        if not user:
            raise HTTPException(status_code=404, detail='User not found')
        user_id = user[0]
        balance = int(user[2] or 0)
        txs = conn.execute(text("SELECT id, user_id, amount, type, balance_before, balance_after, reference_id, status, created_at FROM transactions WHERE user_id = :uid ORDER BY created_at DESC LIMIT 50"), {'uid': user_id}).mappings().all()

    return {'phone': phone, 'balance': balance, 'transactions': [dict(t) for t in txs]}
