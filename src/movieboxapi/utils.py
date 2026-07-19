"""
Utility helpers for MovieBoxAPI.

Slug (detailPath) encoding: MovieBox detail paths contain slashes
(``/id/movie/title-slug``) which break URL routing in frameworks like Flask.
We base64-urlsafe encode them so they can be safely embedded in URL segments.
"""

from __future__ import annotations

import base64
import re
import math
from typing import Any, Optional


def encode_slug(slug: str) -> str:
    """Base64-urlsafe encode a detailPath so it's safe in URL segments."""
    if not slug:
        return ""
    return base64.urlsafe_b64encode(slug.encode()).decode().rstrip("=")


def decode_slug(encoded: str) -> str:
    """Decode a base64-urlsafe encoded detailPath back to the original string.

    Falls back to returning *encoded* as-is if decoding fails (backward compat).
    """
    if not encoded:
        return ""
    try:
        padded = encoded + "=" * ((4 - len(encoded) % 4) % 4)
        return base64.urlsafe_b64decode(padded.encode()).decode()
    except Exception:
        return encoded


def format_duration(seconds: Any) -> Optional[str]:
    """Convert seconds (int/float) to a human-readable ``Xh Ym`` or ``Xm`` string."""
    if not seconds or not isinstance(seconds, (int, float)):
        return None
    # API sometimes returns milliseconds
    mins = int(seconds // 60) if seconds > 1000 else int(seconds)
    if mins >= 60:
        return f"{mins // 60}h {mins % 60}m"
    return f"{mins}m"


def parse_genres(raw: Any) -> list[str]:
    """Normalise genres from string / list-of-dicts / list-of-strings."""
    if not raw:
        return []
    if isinstance(raw, str):
        return [g.strip() for g in raw.split(",") if g.strip()]
    if isinstance(raw, list):
        return [g.get("name", g) if isinstance(g, dict) else str(g) for g in raw]
    return []


def total_pages(total_items: int, per_page: int) -> int:
    """Calculate total page count."""
    if per_page <= 0:
        return 1
    return max(1, math.ceil(total_items / per_page))


def derive_title_from_slug(slug: str) -> str:
    """Derive a readable title from a slug like ``movie-title-abC123def``."""
    if not slug:
        return "Untitled"
    return re.sub(r"-[A-Za-z0-9]{8,}$", "", slug).replace("-", " ").title()