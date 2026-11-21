"""Sections 7.3, 11: mail that must not slow or fail the request that asked for it. The send goes
to a small thread pool after the transaction commits; a failure is logged with the correlation id
only, never the address or the body, which may carry a token."""

import logging
from concurrent.futures import Future, ThreadPoolExecutor, wait
from contextvars import copy_context
from threading import Lock

from django.core.mail import EmailMessage
from django.db import transaction

logger = logging.getLogger("drlibre.mail")

WORKER_COUNT = 2
_pool = ThreadPoolExecutor(max_workers=WORKER_COUNT, thread_name_prefix="background-mail")
_pending: set[Future[None]] = set()
_pending_lock = Lock()


def send_after_commit(message: EmailMessage) -> None:
    """The send runs in a copy of the request context, so its log line keeps the correlation id."""
    transaction.on_commit(lambda: _submit(message))


def wait_until_idle() -> None:
    with _pending_lock:
        outstanding = set(_pending)
    wait(outstanding)


def _submit(message: EmailMessage) -> None:
    future = _pool.submit(copy_context().run, _send, message)
    with _pending_lock:
        _pending.add(future)
    future.add_done_callback(_forget)


def _forget(future: Future[None]) -> None:
    with _pending_lock:
        _pending.discard(future)


def _send(message: EmailMessage) -> None:
    try:
        message.send()
    except Exception:  # noqa: BLE001 - the error text can carry the address, so it is not logged
        logger.error("background mail not sent")
