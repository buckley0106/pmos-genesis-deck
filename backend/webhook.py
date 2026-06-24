"""Webhook fan-out engine. Reads webhook configs from MongoDB and POSTs JSON to each."""
import logging
import requests

logger = logging.getLogger(__name__)


def dispatch(url: str, payload: dict) -> dict:
    try:
        # Both Discord and Slack accept {"content": ...} or {"text": ...} respectively;
        # we send both for max compatibility plus the full structured payload.
        body = {
            "content": payload.get("summary", "PMOS event"),
            "text": payload.get("summary", "PMOS event"),
            "embeds": [{
                "title": payload.get("type", "event"),
                "description": payload.get("summary", ""),
                "color": 0x00F0FF,
            }],
            "pmos": payload,
        }
        r = requests.post(url, json=body, timeout=4)
        return {"status": r.status_code, "ok": r.status_code < 400}
    except Exception as exc:
        logger.warning(f"webhook dispatch failed: {exc}")
        return {"status": 0, "ok": False, "error": str(exc)}
