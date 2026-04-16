import time
from infrastructure.database import SessionLocal
from backend.models.models import UsageLog
from infrastructure.logger import logger


def run_monitor(poll_interval: int = 30):
    logger.info("Monitor started")
    db = SessionLocal()
    try:
        while True:
            count = db.query(UsageLog).count()
            logger.info("Total usage logs: %d", count)
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        logger.info("Monitor stopped")
    finally:
        db.close()


if __name__ == "__main__":
    run_monitor()
