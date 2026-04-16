from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import text
from .database import engine
from datetime import datetime, timedelta
import secrets
from infrastructure.logger import logger

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post('/api_keys')
def create_api_key(payload: dict):
    name = payload.get('name')
    ttl = payload.get('ttl')
    key = secrets.token_urlsafe(32)
    expires_at = None
    if ttl:
        expires_at = datetime.utcnow() + timedelta(seconds=int(ttl))
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO api_keys (key, name, revoked, expires_at, created_at) VALUES (:key, :name, false, :expires_at, now())"), {'key': key, 'name': name, 'expires_at': expires_at})
    logger.info(f"Created api key name={name}")
    return {'key': key, 'name': name, 'expires_at': expires_at.isoformat() if expires_at else None}


@router.post('/api_keys/{key}/revoke')
def revoke_api_key(key: str):
    with engine.begin() as conn:
        res = conn.execute(text("UPDATE api_keys SET revoked = true WHERE key = :k RETURNING id"), {'k': key}).fetchone()
        if not res:
            raise HTTPException(status_code=404, detail='key not found')
    logger.info(f"Revoked api key {key}")
    return {'revoked': True}


@router.get('/api_keys')
def list_api_keys():
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT id, key, name, revoked, expires_at, created_at FROM api_keys ORDER BY id DESC LIMIT 100")).fetchall()
        out = []
        for r in rows:
            out.append({'id': r[0], 'key': r[1], 'name': r[2], 'revoked': r[3], 'expires_at': r[4].isoformat() if r[4] else None, 'created_at': r[5].isoformat() if r[5] else None})
    return out
