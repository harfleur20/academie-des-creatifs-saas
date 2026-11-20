"""Queued e-mails leave within the minute, from the web process itself.

The hourly cron (billing-lifecycle.yml) still drains the queue too, as a safety net. Several
processes may run this loop: each message is claimed in the database before it is sent
(process_communication_outbox), so none goes out twice.
"""
from __future__ import annotations

import logging
import threading

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.communication_delivery import process_communication_outbox

INTERVAL_SECONDS = 30
logger = logging.getLogger(__name__)
_stop = threading.Event()
_thread: threading.Thread | None = None


def _drain_once() -> None:
    db = SessionLocal()
    try:
        process_communication_outbox(db)
    except Exception:  # a provider or database hiccup must not stop the loop
        logger.exception("Envoi des communications interrompu ; nouvel essai au prochain passage.")
        db.rollback()
    finally:
        db.close()


def _loop() -> None:
    while not _stop.wait(INTERVAL_SECONDS):
        _drain_once()


def start_communication_worker() -> bool:
    """Start the loop once per process, when enabled (production by default)."""
    global _thread
    if not settings.communication_worker_enabled or (_thread is not None and _thread.is_alive()):
        return False
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="communication-outbox", daemon=True)
    _thread.start()
    return True


def stop_communication_worker() -> None:
    global _thread
    _stop.set()
    if _thread is not None:
        _thread.join(timeout=5)
    _thread = None
