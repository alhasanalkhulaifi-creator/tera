from fastapi import FastAPI
from backend.api.health import router as health_router
from backend.api.report import router as report_router
from backend.api.wallet import router as wallet_router
from backend.api.vouchers import router as vouchers_router
from infrastructure.database import init_db
from infrastructure.logger import logger

app = FastAPI(title="TERA Central Brain")

app.include_router(health_router)
app.include_router(report_router)
app.include_router(wallet_router)
app.include_router(vouchers_router)


@app.on_event("startup")
def on_startup():
    logger.info("Initializing database...")
    init_db()
    logger.info("Database ready")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000)
