"""
Lightweight data models returned by MovieBoxAPI.

These are plain dataclasses (no pydantic dependency) so the package stays
minimal. Callers can convert to dict via ``dataclasses.asdict``.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional


@dataclass
class MediaItem:
    """A movie / TV show / animation card from catalog or search."""

    subject_id: str = ""
    title: str = ""
    poster: str = ""
    detail_path: str = ""
    rating: Optional[str] = None
    year: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Episode:
    ep: int = 1


@dataclass
class Season:
    season: int = 1
    title: str = "Season 1"
    episodes: list[Episode] = field(default_factory=list)


@dataclass
class CastMember:
    name: str = ""
    character: str = ""
    type: int = 0  # 1=Director, 2=Actor, 3=Writer
    type_label: str = ""
    avatar: str = ""


@dataclass
class Dub:
    """A dubbing / subtitle variant for a title.

    Each dub has its own ``subject_id`` and ``detail_path`` — use these to
    fetch the stream for that specific language variant.

    Attributes
    ----------
    subject_id : str
        Unique ID for this language variant. Pass to :meth:`MovieBoxClient.get_stream`.
    lan_name : str
        Human-readable name (e.g. ``"Indonesian dub"``, ``"English sub"``).
    lan_code : str
        ISO language code (e.g. ``"id"``, ``"en"``, ``"ar"``).
    detail_path : str
        Slug path for the variant's detail page.
    type : int
        0 = dub (audio), 1 = sub (subtitle / soft-sub only).
    original : bool
        True if this is the original audio track.
    """

    subject_id: str = ""
    lan_name: str = ""
    lan_code: str = ""
    detail_path: str = ""
    type: int = 0  # 0=dub, 1=sub
    original: bool = False


@dataclass
class Trailer:
    url: str = ""
    cover: Optional[str] = None
    duration: Optional[Any] = None
    definition: Optional[Any] = None


@dataclass
class MediaDetail:
    """Full metadata for a single title."""

    subject_id: Optional[str] = None
    title: str = ""
    rating: Optional[str] = None
    year: Optional[str] = None
    country: Optional[str] = None
    duration: Optional[str] = None
    genres: list[str] = field(default_factory=list)
    synopsis: str = ""
    seasons: list[Season] = field(default_factory=list)
    total_episodes: int = 0
    poster: Optional[str] = None
    trailer: Optional[Trailer] = None
    cast: list[CastMember] = field(default_factory=list)
    dubs: list[Dub] = field(default_factory=list)
    content_rating: str = ""
    aka: str = ""
    viewers: int = 0
    want_to_see: int = 0
    have_seen: int = 0
    subtitles: list = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Quality:
    resolution: int
    label: str
    current: bool = False


@dataclass
class Subtitle:
    lang: str
    label: str
    url: str


@dataclass
class StreamResult:
    """Playable stream + available qualities / subtitles."""

    url: str = ""
    subtitle_url: str = ""
    resource_id: str = ""
    qualities: list[Quality] = field(default_factory=list)
    subtitles: list[Subtitle] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class HomeSection:
    type: str  # banner | movie | tv | animation | sport_live
    name: str
    items: list = field(default_factory=list)
    sport_url: str = ""


@dataclass
class CatalogPage:
    items: list[MediaItem] = field(default_factory=list)
    page: int = 1
    per_page: int = 24
    total: int = 0
    total_page: int = 1

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SearchResult:
    query: str = ""
    page: int = 1
    total: int = 0
    items: list[MediaItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
