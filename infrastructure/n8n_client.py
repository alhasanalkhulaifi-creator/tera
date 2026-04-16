import logging
import requests
from backend.config import settings

logger = logging.getLogger("n8n_client")


def send_event_to_n8n(event_type: str, payload: dict) -> bool:
    url = settings.n8n_webhook_url
    body = {"event_type": event_type, "payload": payload}
    try:
        resp = requests.post(url, json=body, timeout=5)
        resp.raise_for_status()
        logger.info("n8n event sent: %s", event_type)
        return True
    except Exception as exc:
        logger.exception("Failed to send event to n8n: %s", exc)
        return False
