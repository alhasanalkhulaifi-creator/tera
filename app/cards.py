from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import text
from .database import SessionLocal, engine
from . import models
from .schemas import CardImportIn, CardBuyIn, CardOut
from datetime import datetime
from typing import Optional
import time
from collections import defaultdict, deque
from threading import Lock
from sqlalchemy.dialects.postgresql import insert as pg_insert
from infrastructure.logger import logger
from .redis_client import record_redis_failure, redis_available, redis_client


class _TimedConn:
    """Wraps a SQLAlchemy connection to accumulate conn.execute wall time (seconds)."""

    __slots__ = ("_conn", "_query_s")

    def __init__(self, conn, query_seconds: list):
        self._conn = conn
        self._query_s = query_seconds

    def execute(self, *args, **kwargs):
        t = time.perf_counter()
        try:
            return self._conn.execute(*args, **kwargs)
        finally:
            self._query_s[0] += time.perf_counter() - t

router = APIRouter(prefix="/cards", tags=["cards"])

# simple in-memory per-user rate limiter (raised for load testing; tune down in production)
_RATE_LIMIT = 200
_RATE_PERIOD = 1.0
_rate_data = defaultdict(deque)
_rate_lock = Lock()


def _rate_limit_exceeded():
    return JSONResponse(status_code=429, content={"error": "rate_limit_exceeded"})


def _use_in_memory_rate_limiter(user_phone: str) -> bool:
    now = time.time()
    with _rate_lock:
        q = _rate_data[user_phone]
        while q and q[0] <= now - _RATE_PERIOD:
            q.popleft()
        if len(q) >= _RATE_LIMIT:
            return True
        q.append(now)
    return False


def _try_increment_order_metric(key: str, failure_message: str):
    if not redis_available():
        return

    try:
        redis_client.incr(key)
    except Exception:
        record_redis_failure(failure_message, log_traceback=True)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/import")
def import_cards(payload: CardImportIn):
    """Bulk import a list of card codes as available cards."""
    rows = []
    now = datetime.utcnow()
    for code in payload.codes:
        rows.append({
            'code': code,
            'category': payload.category,
            'price': payload.price,
            'status': 'available',
            'assigned_to': None,
            'created_at': now,
        })

    stmt = pg_insert(models.Card.__table__).values(rows).on_conflict_do_nothing(
        index_elements=['code']
    ).returning(models.Card.id)

    with engine.begin() as conn:
        result = conn.execute(stmt)
        inserted = len(result.fetchall())

    return {'requested': len(payload.codes), 'inserted': inserted}


@router.post("/buy", response_model=CardOut)
def buy_card(payload: CardBuyIn):
    """Order-based purchase flow (single DB transaction on the hot path for new orders)."""
    if not payload.category or not payload.user_id:
        return JSONResponse(status_code=400, content={"error": "category_and_user_id_required"})

    t_req0 = time.perf_counter()
    rate_key = payload.user_phone or str(payload.user_id)

    use_redis_rate_limiter = redis_available()
    if use_redis_rate_limiter:
        try:
            bucket_key = f"rate:{rate_key}:{int(time.time())}"
            pipe = redis_client.pipeline()
            pipe.incr(bucket_key)
            pipe.expire(bucket_key, int(_RATE_PERIOD) + 1)
            results = pipe.execute()
            cnt = int(results[0])
            if cnt > _RATE_LIMIT:
                return _rate_limit_exceeded()
        except Exception:
            record_redis_failure("Redis failed -> fallback in-memory", log_traceback=True)
            use_redis_rate_limiter = False

    if not use_redis_rate_limiter and _use_in_memory_rate_limiter(rate_key):
        return _rate_limit_exceeded()

    _q_s = [0.0]
    total_ms = 0.0
    txn_ms = 0.0
    dbq_ms = 0.0
    try:
        txn_t0 = time.perf_counter()
        with engine.begin() as _raw:
            conn = _TimedConn(_raw, _q_s)

            # 1. Lock user row
            urow = conn.execute(
                text("SELECT balance FROM users WHERE id = :id FOR UPDATE"),
                {'id': payload.user_id},
            ).fetchone()
            if not urow:
                return JSONResponse(status_code=404, content={"error": "user_not_found"})
            balance_before = int(urow[0] or 0)

            # 2. Lock one available card (no retry loop)
            card_row = conn.execute(
                text(
                    "SELECT id, code, price FROM cards "
                    "WHERE status = 'available' AND category = :category "
                    "ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 1"
                ),
                {'category': payload.category},
            ).fetchone()
            if not card_row:
                return JSONResponse(status_code=400, content={"error": "no_cards_available_for_category"})

            card_id = card_row[0]
            card_price = int(card_row[2] or 0)

            # 3. Validate balance (after both locks are held)
            if balance_before < card_price:
                return JSONResponse(status_code=400, content={"error": "insufficient_balance"})

            # 4. Deduct balance
            conn.execute(
                text("UPDATE users SET balance = balance - :amount WHERE id = :id"),
                {'amount': card_price, 'id': payload.user_id},
            )
            balance_after = balance_before - card_price

            # 5. Mark card as sold
            card_res = conn.execute(
                text(
                    "UPDATE cards SET status = 'sold', user_id = :uid, sold_at = now() "
                    "WHERE id = :cid "
                    "RETURNING id, code, category, price, status, user_id, created_at"
                ),
                {'uid': payload.user_id, 'cid': card_id},
            ).fetchone()

            # 6. Record transaction
            conn.execute(
                text(
                    "INSERT INTO transactions (user_id, amount, type, balance_before, balance_after, "
                    "reference_id, status, created_at) VALUES (:uid, :amt, 'purchase', :bb, :ba, :ref, "
                    "'success', now())"
                ),
                {
                    'uid': payload.user_id,
                    'amt': -card_price,
                    'bb': balance_before,
                    'ba': balance_after,
                    'ref': payload.order_reference,
                },
            )

            out = dict(card_res._mapping)
            out.setdefault('assigned_to', None)
            txn_ms = (time.perf_counter() - txn_t0) * 1000
            return out
    except HTTPException:
        raise
    except Exception as e:
        logger.exception('Unexpected error in buy flow')
        raise HTTPException(status_code=500, detail=f'Purchase failed: {e}')
    finally:
        total_ms = (time.perf_counter() - t_req0) * 1000
        dbq_ms = _q_s[0] * 1000
        logger.debug(
            "buy_card timing total_ms=%.3f txn_ms=%.3f db_query_ms=%.3f",
            total_ms,
            txn_ms,
            dbq_ms,
        )


@router.get("/", response_model=list[CardOut])
def list_cards(status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(models.Card)
    if status:
        q = q.filter(models.Card.status == status)
    items = q.order_by(models.Card.created_at.desc()).limit(1000).all()
    return items


@router.get("/orders/{reference_id}")
def get_order(reference_id: str):
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT id, reference_id, user_id, card_id, price, status, created_at "
                "FROM orders WHERE reference_id = :ref"
            ),
            {'ref': reference_id},
        ).fetchone()
        if not row:
            return JSONResponse(status_code=404, content={"error": "order_not_found"})
        return {
            'id': row[0],
            'reference_id': row[1],
            'user_id': row[2],
            'card_id': row[3],
            'price': int(row[4] or 0),
            'status': row[5],
            'created_at': row[6].isoformat() if row[6] else None
        }
