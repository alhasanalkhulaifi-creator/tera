import logging
import os
from logging.handlers import RotatingFileHandler
from backend.config import settings

BASE_DIR = os.path.dirname(os.path.dirname(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "tera.log")


def setup_logger(name: str = "tera") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    fh = RotatingFileHandler(LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    return logger


logger = setup_logger()
