"""Exponential backoff with jitter for transient LLM failures."""

import time
import random
import logging
from typing import TypeVar, Callable

from .errors import AIAuthError, AITimeoutError

logger = logging.getLogger(__name__)
T = TypeVar("T")


def with_retry(
    fn: Callable[[], T],
    *,
    max_retries: int = 2,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
) -> T:
    """Retry *fn* with exponential backoff + jitter.

    Does NOT retry on:
    - ``AIAuthError``  — bad credentials won't fix themselves
    - ``AITimeoutError`` — already timed out, retrying makes it worse
    """
    last_err: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            return fn()
        except (AIAuthError, AITimeoutError):
            raise
        except Exception as exc:
            last_err = exc
            if attempt < max_retries:
                delay = min(
                    base_delay * (2**attempt) + random.uniform(0, 1),
                    max_delay,
                )
                logger.warning(
                    "AI call failed (attempt %d/%d), retrying in %.1fs: %s",
                    attempt + 1,
                    max_retries + 1,
                    delay,
                    exc,
                )
                time.sleep(delay)

    assert last_err is not None
    raise last_err
