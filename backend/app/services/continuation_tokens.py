"""Short-lived, process-local replay protection for signed continuation tokens."""

from __future__ import annotations

import hashlib
import threading
import time
from contextlib import contextmanager
from collections.abc import Callable, Iterator


def reserve(used: dict[str, float], pending: dict[str, float], lock: threading.Lock,
            token: str, expires_at: float) -> str:
    key = hashlib.sha256(token.encode("ascii")).hexdigest()
    now = time.time()
    with lock:
        for cache in (used, pending):
            for old_key, expiry in list(cache.items()):
                if expiry <= now:
                    cache.pop(old_key, None)
        if key in used or key in pending or len(used) + len(pending) >= 4096:
            raise ValueError("Continuation state was already used or the state cache is full.")
        pending[key] = expires_at
    return key


def finish(used: dict[str, float], pending: dict[str, float], lock: threading.Lock,
           token: str, *, commit: bool) -> None:
    key = hashlib.sha256(token.encode("ascii")).hexdigest()
    with lock:
        expires_at = pending.pop(key, None)
        if commit and expires_at is not None and expires_at > time.time():
            used[key] = expires_at


@contextmanager
def use(token: str | None, finish_token: Callable[..., None]) -> Iterator[None]:
    try:
        yield
    except BaseException:
        finish_token(token, commit=False)
        raise
    else:
        finish_token(token, commit=True)
