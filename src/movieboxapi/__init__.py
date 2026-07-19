"""
MovieBoxAPI — Python client for the MovieBox streaming platform.

Quick start::

    from movieboxapi import MovieBoxClient

    client = MovieBoxClient(region="ID")

    # Browse
    home = client.get_home()
    movies = client.get_movies(page=1)
    results = client.search("interstellar")

    # Detail
    detail = client.get_detail("/id/movie/interstellar-abc123")

    # Stream
    stream = client.get_stream(subject_id="12345", se=1, ep=1)
    print(stream.url)
"""

from __future__ import annotations

__version__ = "0.1.0"

from .client import MovieBoxClient
from .sportsnow import SportsNowClient
from .constants import (
    FRONTENDS,
    H5_API_BASE,
    H5_HOST,
    V3_HOST_POOL,
    REGION_PRESETS,
    TabID,
    build_h5_headers,
    generate_v3_client_identity,
)
from .crypto import build_signed_headers, client_token, signature
from .exceptions import (
    APIError,
    GeoBlockError,
    MovieBoxError,
    RateLimitError,
    StreamError,
    TokenError,
)
from .models import (
    CastMember,
    CatalogPage,
    Dub,
    Episode,
    HomeSection,
    MediaDetail,
    MediaItem,
    Quality,
    Season,
    SearchResult,
    SportActivityConfig,
    SportHighlight,
    SportMatch,
    SportMatchDetail,
    SportNews,
    SportNewsStats,
    SportOddsEntry,
    SportOddsSource,
    SportPlaySource,
    SportTeam,
    SportTeamMatchInfo,
    StreamResult,
    Subtitle,
    Trailer,
)
from .sportsnow_constants import (
    SPORT_TYPES,
    SPORTSNAW_API_BASE,
    MatchStatus,
    build_sportsnow_headers,
)
from .utils import decode_slug, encode_slug

__all__ = [
    # Clients
    "MovieBoxClient",
    "SportsNowClient",
    # MovieBox Models
    "MediaItem",
    "MediaDetail",
    "CatalogPage",
    "SearchResult",
    "HomeSection",
    "StreamResult",
    "Quality",
    "Subtitle",
    "Season",
    "Episode",
    "CastMember",
    "Dub",
    "Trailer",
    # SportsNow Models
    "SportMatch",
    "SportMatchDetail",
    "SportTeam",
    "SportTeamMatchInfo",
    "SportPlaySource",
    "SportHighlight",
    "SportNews",
    "SportNewsStats",
    "SportOddsEntry",
    "SportOddsSource",
    "SportActivityConfig",
    # Exceptions
    "MovieBoxError",
    "APIError",
    "RateLimitError",
    "GeoBlockError",
    "StreamError",
    "TokenError",
    # MovieBox Constants
    "FRONTENDS",
    "H5_API_BASE",
    "H5_HOST",
    "V3_HOST_POOL",
    "REGION_PRESETS",
    "TabID",
    # SportsNow Constants
    "SPORTSNAW_API_BASE",
    "SPORT_TYPES",
    "MatchStatus",
    "build_sportsnow_headers",
    # Crypto
    "build_h5_headers",
    "generate_v3_client_identity",
    "build_signed_headers",
    "client_token",
    "signature",
    # Utils
    "encode_slug",
    "decode_slug",
    # Meta
    "__version__",
]
