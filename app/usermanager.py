from .mikrotik import fetch_usermanager_data
from . import models
from sqlalchemy.orm import Session
from datetime import datetime
import logging


def sync_sessions(db: Session, limit: int = 1000):
    """
    Fetch sessions from MikroTik and bulk-insert into DB with deduplication.
    Returns dict: {fetched: int, inserted: int}
    """
    users, sessions, limits = fetch_usermanager_data()
    rows = []
    for s in sessions[-limit:]:
        username = s.get('user')
        user_data = next((u for u in users if u.get('username') == username), None)
        profile = user_data.get('actual-profile') if user_data else None
        try:
            d = int(s.get('download') or 0)
        except Exception:
            d = 0
        try:
            u = int(s.get('upload') or 0)
        except Exception:
            u = 0
        active = True if s.get('active') in ['true', True] else False

        rows.append({
            'card': username,
            'ip': s.get('user-ip'),
            'mac': s.get('calling-station-id'),
            'download': d,
            'upload': u,
            'uptime': s.get('uptime'),
            'profile': profile,
            'active': active,
            'from_time': s.get('from-time'),
            'created_at': datetime.utcnow(),
        })

    fetched = len(rows)
    if fetched == 0:
        logging.info("sync_sessions: no sessions fetched")
        return {'fetched': 0, 'inserted': 0}

    # bulk insert with ON CONFLICT DO NOTHING using PostgreSQL dialect
    from app.database import engine
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    stmt = pg_insert(models.Session.__table__).values(rows).on_conflict_do_nothing(
        index_elements=['card', 'ip', 'mac', 'from_time']
    ).returning(models.Session.id)

    with engine.begin() as conn:
        result = conn.execute(stmt)
        inserted_rows = result.fetchall()

    inserted = len(inserted_rows)
    logging.info(f"sync_sessions: fetched={fetched} inserted={inserted}")
    return {'fetched': fetched, 'inserted': inserted}

