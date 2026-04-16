import asyncio
import os
import time
from threading import Lock
from typing import Optional, Tuple

from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text

from .database import init_db, SessionLocal, engine
from .redis_client import record_redis_failure, redis_available, redis_client, reset_request_redis_state
from infrastructure.logger import logger
from .schemas import SessionOut
from sqlalchemy.orm import Session
from . import models
from .usermanager import sync_sessions
from .cards import router as cards_router
from .wallet import router as wallet_router
from .admin import router as admin_router

app = FastAPI()

_API_KEY_CACHE_LOCK = Lock()
_API_KEY_CACHE_VALID: dict[str, Tuple[float, Tuple[int, Optional[str]]]] = {}
_API_KEY_CACHE_NEGATIVE: dict[str, float] = {}
_API_KEY_TTL_VALID = float(os.getenv("API_KEY_CACHE_TTL_VALID", "120"))
_API_KEY_TTL_INVALID = float(os.getenv("API_KEY_CACHE_TTL_INVALID", "15"))
_ACCESS_LOG = os.getenv("TERA_ACCESS_LOG", "0").lower() in ("1", "true", "yes")


def _lookup_api_key_row(key: str):
    with engine.connect() as conn:
        return conn.execute(
            text(
                "SELECT id, name FROM api_keys WHERE key = :k AND revoked = false "
                "AND (expires_at IS NULL OR expires_at > now())"
            ),
            {'k': key},
        ).fetchone()


@app.on_event("startup")
def on_startup():
    init_db()


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    reset_request_redis_state()

    # allow some open endpoints
    open_paths = {"/docs", "/openapi.json", "/health", "/metrics"}
    if request.url.path in open_paths:
        return await call_next(request)

    auth = request.headers.get("authorization")
    if not auth or not auth.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"error": "unauthorized"})
    key = auth.split(" ", 1)[1]

    now = time.monotonic()
    api_key_id = None
    api_key_name = None

    with _API_KEY_CACHE_LOCK:
        hit = _API_KEY_CACHE_VALID.get(key)
        if hit and hit[0] > now:
            api_key_id, api_key_name = hit[1]
        else:
            neg_until = _API_KEY_CACHE_NEGATIVE.get(key)
            if neg_until and neg_until > now:
                return JSONResponse(status_code=401, content={"error": "unauthorized"})

    if api_key_id is None:
        row = await asyncio.to_thread(_lookup_api_key_row, key)
        if not row:
            with _API_KEY_CACHE_LOCK:
                _API_KEY_CACHE_NEGATIVE[key] = now + _API_KEY_TTL_INVALID
            return JSONResponse(status_code=401, content={"error": "unauthorized"})
        api_key_id, api_key_name = row[0], row[1]
        with _API_KEY_CACHE_LOCK:
            _API_KEY_CACHE_VALID[key] = (now + _API_KEY_TTL_VALID, (api_key_id, api_key_name))
            _API_KEY_CACHE_NEGATIVE.pop(key, None)

    t_req0 = time.perf_counter_ns()
    response = await call_next(request)
    duration_ms = int((time.perf_counter_ns() - t_req0) / 1_000_000)

    if _ACCESS_LOG:
        try:
            logger.info(
                "req api_key=%s path=%s method=%s status=%s duration_ms=%s",
                api_key_name or api_key_id,
                request.url.path,
                request.method,
                response.status_code,
                duration_ms,
            )
        except Exception:
            pass

    try:
        if redis_available():
            pipe = redis_client.pipeline()
            pipe.incr('metrics:requests:total')
            pipe.incrby('metrics:responses:sum_ms', duration_ms)
            pipe.incr('metrics:responses:count')
            pipe.execute()
    except Exception:
        record_redis_failure('Failed updating metrics in Redis', log_traceback=True)

    return response




@app.on_event("startup")
async def start_order_expirer():
    async def expire_orders():
        while True:
            try:
                with engine.begin() as conn:
                    conn.execute(
                        text("UPDATE orders SET status = 'expired' WHERE status = 'pending' AND created_at < now() - interval '30 seconds'")
                    )
            except Exception:
                pass
            await asyncio.sleep(5)

    asyncio.create_task(expire_orders())


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.get("/sessions", response_model=list[SessionOut])
def read_sessions(db: Session = Depends(get_db)):
    # Serve from DB only (no MikroTik calls)
    items = db.query(models.Session).order_by(models.Session.created_at.desc()).limit(500).all()
    return items


@app.post("/sync/sessions")
def post_sync_sessions(db: Session = Depends(get_db)):
    """Trigger data collection from MikroTik and store into DB (bulk insert)."""
    result = sync_sessions(db)
    return result


# include cards API
app.include_router(cards_router)
app.include_router(wallet_router)
app.include_router(admin_router)


@app.get('/health')
def health():
    # check DB
    db_ok = True
    redis_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
    except Exception:
        db_ok = False
    try:
        if redis_available():
            redis_client.ping()
            redis_ok = True
    except Exception:
        record_redis_failure('Failed checking Redis health', log_traceback=True)
        redis_ok = False
    status = 'ok' if db_ok else 'db_error'
    return {'status': status, 'db': db_ok, 'redis': redis_ok}


@app.get('/metrics')
def metrics():
    data = {'total_requests': 0, 'responses_avg_ms': None, 'total_orders': 0, 'failed_orders': 0}
    try:
        if redis_available():
            total = redis_client.get('metrics:requests:total') or 0
            sum_ms = float(redis_client.get('metrics:responses:sum_ms') or 0)
            count = int(redis_client.get('metrics:responses:count') or 0)
            data['total_requests'] = int(total)
            data['responses_avg_ms'] = (sum_ms / count) if count > 0 else None
            data['total_orders'] = int(redis_client.get('metrics:orders:total') or 0)
            data['failed_orders'] = int(redis_client.get('metrics:orders:failed') or 0)
        else:
            # fallback to DB counts
            with engine.connect() as conn:
                r = conn.execute(text("SELECT COUNT(*) FROM orders")).fetchone()
                data['total_orders'] = int(r[0] or 0)
                r2 = conn.execute(text("SELECT COUNT(*) FROM orders WHERE status = 'failed' OR status='expired'")).fetchone()
                data['failed_orders'] = int(r2[0] or 0)
    except Exception:
        record_redis_failure('Failed reading metrics from Redis', log_traceback=True)
        with engine.connect() as conn:
            r = conn.execute(text("SELECT COUNT(*) FROM orders")).fetchone()
            data['total_orders'] = int(r[0] or 0)
            r2 = conn.execute(text("SELECT COUNT(*) FROM orders WHERE status = 'failed' OR status='expired'")).fetchone()
            data['failed_orders'] = int(r2[0] or 0)
    return data
