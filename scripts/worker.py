import time
from infrastructure.database import SessionLocal
from infrastructure.logger import logger


def run_worker(poll_interval: int = 10):
    logger.info("Worker started")
    db = SessionLocal()
    try:
        while True:
            logger.debug("Worker heartbeat")
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        logger.info("Worker stopped")
    finally:
        db.close()


if __name__ == "__main__":
    run_worker()
