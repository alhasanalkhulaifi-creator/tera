from fastapi import APIRouter
from backend.schemas.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health_check():
    return {"status": "ok"}
