from fastapi import APIRouter, Depends
from backend.schemas.schemas import ReportIn, StandardResponse
from infrastructure.database import get_db
from sqlalchemy.orm import Session
from services.usage_service import record_usage

router = APIRouter()


@router.post("/api/report", response_model=StandardResponse)
def report_endpoint(report: ReportIn, db: Session = Depends(get_db)):
    result = record_usage(db, report)
    return {"status": "ok", "detail": f"recorded: {result}"}
