"""Short-lived, process-local replay protection for signed continuation tokens."""

from __future__ import annotations

import hashlib
import threading
import time
from contextvars import ContextVar
from contextlib import contextmanager
from collections.abc import Callable, Iterator

_OWNER: ContextVar[object | None] = ContextVar("continuation_token_owner", default=None)


def reserve(used: dict[str, float], pending: dict[str, tuple[float, object | None]], lock: threading.Lock,
            token: str, expires_at: float) -> str:
    key = hashlib.sha256(token.encode("ascii")).hexdigest()
    now = time.time()
    with lock:
        for old_key, expiry in list(used.items()):
            if expiry <= now:
                used.pop(old_key, None)
        for old_key, (expiry, _) in list(pending.items()):
            if expiry <= now:
                pending.pop(old_key, None)
        if key in used or key in pending or len(used) + len(pending) >= 4096:
            raise ValueError("Continuation state was already used or the state cache is full.")
        pending[key] = (expires_at, _OWNER.get())
    return key


def finish(used: dict[str, float], pending: dict[str, tuple[float, object | None]], lock: threading.Lock,
           token: str, *, commit: bool) -> None:
    key = hashlib.sha256(token.encode("ascii")).hexdigest()
    with lock:
        reservation = pending.get(key)
        if reservation is None or reservation[1] is not _OWNER.get():
            return
        expires_at, _ = pending.pop(key)
        if commit and expires_at is not None and expires_at > time.time():
            used[key] = expires_at


@contextmanager
def use(token: str | None, finish_token: Callable[..., None]) -> Iterator[None]:
    owner = _OWNER.set(object())
    try:
        try:
            yield
        except BaseException:
            finish_token(token, commit=False)
            raise
        else:
            finish_token(token, commit=True)
    finally:
        _OWNER.reset(owner)
