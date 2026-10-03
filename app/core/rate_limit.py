import time
from collections import defaultdict

from fastapi import HTTPException

# Explicitly a placeholder, per build_docs/01-development-roadmap.md Stage 2/8's own
# framing: in-process, per-worker — resets on restart, and doesn't share state across
# more than one process. Real rate limiting waits for Redis at Stage 11; this exists
# so a single runaway client can't hammer the LLM in the meantime.
_WINDOW_SECONDS = 60
_MAX_REQUESTS = 20
_hits: dict[str, list[float]] = defaultdict(list)


def check_rate_limit(key: str) -> None:
    now = time.monotonic()
    window_start = now - _WINDOW_SECONDS
    hits = [t for t in _hits[key] if t > window_start]
    if len(hits) >= _MAX_REQUESTS:
        raise HTTPException(status_code=429, detail="Too many requests, slow down.")
    hits.append(now)
    _hits[key] = hits
