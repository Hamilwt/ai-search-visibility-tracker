"""In-memory sliding-window rate limiting for run creation.

Per-instance memory: resets on restart and does not coordinate across
instances. Right-sized for a free-tier single instance; Redis would be
the follow-up if this ever scales horizontally.
"""

import time

from fastapi import Request

WINDOW_S = 3600.0

_hits: dict[str, list[float]] = {}


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is not None:
        return request.client.host
    return "unknown"


def check_rate_limit(ip: str, limit: int, now: float | None = None) -> float | None:
    """Record a hit; return retry-after seconds when over the limit."""
    current = time.monotonic() if now is None else now
    fresh = [mark for mark in _hits.get(ip, []) if mark > current - WINDOW_S]
    if len(fresh) >= limit:
        _hits[ip] = fresh
        return (fresh[0] + WINDOW_S) - current
    fresh.append(current)
    _hits[ip] = fresh
    return None


def reset_rate_limits() -> None:
    _hits.clear()
