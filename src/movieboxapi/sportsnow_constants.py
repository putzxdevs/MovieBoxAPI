"""
Constants for SportsNow API.

SportsNow (https://sportsnow.top) shares the aoneroom backend infrastructure
with MovieBox. The H5 API lives under the ``h5-sport-api.aoneroom.com`` host
and uses GET requests (not POST like some of the MovieBox V3 endpoints).

API host : ``h5-sport-api.aoneroom.com``
Base path: ``/wefeed-h5api-bff/live/``
"""

from __future__ import annotations

from typing import Optional

# ── SportsNow API ──────────────────────────────────────────────────────────
SPORTSNAW_API_BASE: str = "https://h5-sport-api.aoneroom.com"
SPORTSNAW_ORIGIN: str = "https://sportsnow.top"
SPORTSNAW_REFERER: str = "https://sportsnow.top/"

# Supported sport types
SPORT_TYPES: tuple[str, ...] = (
    "football",
    "basketball",
    "tennis",
    "cricket",
    "volleyball",
)

# Known status values for matches
class MatchStatus:
    """Match lifecycle status constants."""
    NOT_STARTED = "MatchNotStart"
    LIVING = "MatchLiving"
    ENDED = "MatchEnded"
    CANCELLED = "MatchCancelled"
    POSTPONED = "MatchPostponed"


def build_sportsnow_headers(
    extra: Optional[dict] = None,
) -> dict:
    """Default headers for SportsNow API requests.

    Mimics a real mobile browser visiting sportsnow.top so the aoneroom
    backend doesn't block us.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Linux; Android 13; Redmi Note 12) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Mobile Safari/537.36"
        ),
        "Accept": "application/json",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": SPORTSNAW_REFERER,
        "Origin": SPORTSNAW_ORIGIN,
    }
    if extra:
        headers.update(extra)
    return headers