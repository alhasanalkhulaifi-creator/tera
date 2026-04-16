from sqlalchemy.orm import Session
from backend.schemas.schemas import ReportIn
from backend.models.models import UsageLog
from services.user_service import get_or_create_user
from infrastructure.n8n_client import send_event_to_n8n
from sqlalchemy import func
from datetime import datetime

# Simulated threshold (bytes)
THRESHOLD_BYTES = 1_000_000


def record_usage(db: Session, report: ReportIn) -> dict:
    # ensure user exists and mac is updated
    get_or_create_user(db, report.username, report.mac)

    log = UsageLog(username=report.username, bytes_in=report.bytes_in, bytes_out=report.bytes_out, timestamp=datetime.utcnow())
    db.add(log)
    db.commit()

    total_in = db.query(func.sum(UsageLog.bytes_in)).filter(UsageLog.username == report.username).scalar() or 0
    total_out = db.query(func.sum(UsageLog.bytes_out)).filter(UsageLog.username == report.username).scalar() or 0
    total_usage = int((total_in or 0) + (total_out or 0))

    near_limit = total_usage >= int(THRESHOLD_BYTES * 0.8)
    if near_limit:
        # best-effort notify n8n
        try:
            send_event_to_n8n("usage_near_limit", {"username": report.username, "total_usage": total_usage})
        except Exception:
            pass

    return {"total_usage": total_usage, "near_limit": near_limit}
