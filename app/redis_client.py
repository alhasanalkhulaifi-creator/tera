import os
import time
from contextvars import ContextVar
from threading import Lock

from infrastructure.logger import logger

_CIRCUIT_BREAKER_SECONDS = float(os.getenv('REDIS_CIRCUIT_BREAKER_SECONDS', '5'))
_request_skip_redis = ContextVar('request_skip_redis', default=False)
_circuit_lock = Lock()
_redis_circuit_open_until = 0.0
redis_client = None


def reset_request_redis_state():
    _request_skip_redis.set(False)


def disable_redis_for_request():
    _request_skip_redis.set(True)


def open_redis_circuit(seconds: float = _CIRCUIT_BREAKER_SECONDS):
    global _redis_circuit_open_until

    open_until = time.monotonic() + seconds
    with _circuit_lock:
        if open_until > _redis_circuit_open_until:
            _redis_circuit_open_until = open_until


def redis_circuit_remaining() -> float:
    with _circuit_lock:
        remaining = _redis_circuit_open_until - time.monotonic()
    return remaining if remaining > 0 else 0.0


def redis_available() -> bool:
    return redis_client is not None and not _request_skip_redis.get() and redis_circuit_remaining() <= 0


def record_redis_failure(message: str, *, log_traceback: bool = False):
    disable_redis_for_request()
    open_redis_circuit()
    if log_traceback:
        logger.exception('%s; circuit open for %.1fs', message, _CIRCUIT_BREAKER_SECONDS)
    else:
        logger.warning('%s; circuit open for %.1fs', message, _CIRCUIT_BREAKER_SECONDS)


try:
    import redis

    REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
    REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
    REDIS_DB = int(os.getenv('REDIS_DB', '0'))
    REDIS_SOCKET_TIMEOUT = float(os.getenv('REDIS_SOCKET_TIMEOUT', '0.2'))
    REDIS_CONNECT_TIMEOUT = float(os.getenv('REDIS_CONNECT_TIMEOUT', '0.2'))
    REDIS_MAX_CONNECTIONS = int(os.getenv('REDIS_MAX_CONNECTIONS', '32'))
    _redis_pool = redis.ConnectionPool(
        host=REDIS_HOST,
        port=REDIS_PORT,
        db=REDIS_DB,
        max_connections=REDIS_MAX_CONNECTIONS,
        socket_timeout=REDIS_SOCKET_TIMEOUT,
        socket_connect_timeout=REDIS_CONNECT_TIMEOUT,
        decode_responses=True,
    )
    redis_client = redis.Redis(
        connection_pool=_redis_pool,
        decode_responses=True,
        retry=redis.retry.Retry(redis.backoff.NoBackoff(), 0),
    )
    try:
        redis_client.ping()
        logger.info('Connected to Redis at %s:%s', REDIS_HOST, REDIS_PORT)
    except Exception as e:
        open_redis_circuit()
        logger.warning('Redis ping failed at startup: %s; circuit open for %.1fs', e, _CIRCUIT_BREAKER_SECONDS)
except Exception as e:
    logger.warning('redis package not available: %s', e)
    redis_client = None
