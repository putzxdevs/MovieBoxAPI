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


# ── SportsNow models ──────────────────────────────────────────────────────


@dataclass
class SportTeam:
    """A team in a sport match."""
    id: str = ""
    name: str = ""
    score: str = "0"
    avatar: str = ""
    vote_count: str = "0"
    sport_type: str = ""
    abbreviation: str = ""
    regular_score: str = ""
    name_tag: str = ""


@dataclass
class SportTeamMatchInfo:
    """Extended match scoring info (cricket, etc.)."""
    score: str = "0"
    runs_scored: str = ""
    wickets_lost: str = ""
    overs: str = ""
    extra_balls: str = ""


@dataclass
class SportPlaySource:
    """A streaming channel / source for a match."""
    title: str = ""
    path: str = ""
    id: str = "0"
    cover: Optional[str] = None
    duration: str = "0"


@dataclass
class SportHighlight:
    """A highlight or replay video."""
    title: str = ""
    path: str = ""
    cover: Optional[str] = None
    duration: str = "0"


@dataclass
class SportNewsStats:
    """Engagement stats for a sports news article."""
    view_count: int = 0
    like_count: int = 0
    comment_count: int = 0
    share_count: int = 0


@dataclass
class SportNews:
    """A sports news article."""
    id: str = ""
    title: str = ""
    summary: str = ""
    status: int = 0
    media_type: str = ""
    created_at: str = ""
    updated_at: str = ""
    stat: SportNewsStats = field(default_factory=SportNewsStats)
    cover_url: str = ""
    detail_path: str = ""


@dataclass
class SportMatch:
    """A live/upcoming/ended sport match from SportsNow.

    Attributes
    ----------
    id : str
        Match ID.
    team1 / team2 : SportTeam
        The two competing teams.
    status : str
        ``"MatchNotStart"``, ``"MatchLiving"``, ``"MatchEnded"``, etc.
    play_path : str
        Primary HLS stream URL (m3u8).
    play_sources : list[SportPlaySource]
        Additional streaming channels (external embeds, etc.).
    league : str
        League name (e.g. ``"NBA"``, ``"Indian Premier League"``).
    sport_type : str
        ``"football"``, ``"basketball"``, ``"cricket"``, etc.
    start_time / end_time : str
        Unix timestamp in milliseconds (string).
    highlights : list[SportHighlight]
        Highlight videos for this match.
    replays : list[SportHighlight]
        Replay videos for this match.
    """
    id: str = ""
    team1: SportTeam = field(default_factory=SportTeam)
    team2: SportTeam = field(default_factory=SportTeam)
    status: str = ""
    play_type: str = ""
    play_path: str = ""
    start_time: str = "0"
    end_time: str = "0"
    sport_type: str = ""
    time_desc: str = ""
    play_sources: list[SportPlaySource] = field(default_factory=list)
    status_live: Any = ""
    league: str = ""
    live_device_id: str = ""
    team_match_info1: SportTeamMatchInfo = field(default_factory=SportTeamMatchInfo)
    team_match_info2: SportTeamMatchInfo = field(default_factory=SportTeamMatchInfo)
    match_result: str = ""
    match_round: str = ""
    replays: list[SportHighlight] = field(default_factory=list)
    highlights: list[SportHighlight] = field(default_factory=list)
    ext_country_code: str = ""
    league_id: str = ""
    is_collect: bool = False
    arranged_time: str = "0"
    season: str = ""

    @property
    def team1_name(self) -> str:
        return self.team1.name

    @property
    def team2_name(self) -> str:
        return self.team2.name

    @property
    def team1_score(self) -> str:
        return self.team1.score

    @property
    def team2_score(self) -> str:
        return self.team2.score

    @property
    def is_live(self) -> bool:
        return str(self.status_live).lower() in ("living", "1", "2", "true")

    @property
    def start_timestamp(self) -> float:
        """Match start as Unix timestamp in seconds."""
        try:
            return int(self.start_time) / 1000
        except (ValueError, TypeError):
            return 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SportOddsEntry:
    """A single odds entry (e.g. Home/Draw/Away)."""
    type: int = 0        # 1=Home/Team1, 2=Draw, 3=Away/Team2
    odds: float = 0.0

    @property
    def label(self) -> str:
        """Human-readable label for the odds type."""
        return {1: "Home", 2: "Draw", 3: "Away"}.get(self.type, f"Type{self.type}")


@dataclass
class SportOddsSource:
    """Odds from a single provider/source (e.g. bangbet, marketing)."""
    source: str = ""
    jump_url: str = ""
    entries: list[SportOddsEntry] = field(default_factory=list)

    @property
    def home(self) -> float:
        """Odds for home/team1 win."""
        for e in self.entries:
            if e.type == 1:
                return e.odds
        return 0.0

    @property
    def draw(self) -> float:
        """Odds for draw."""
        for e in self.entries:
            if e.type == 2:
                return e.odds
        return 0.0

    @property
    def away(self) -> float:
        """Odds for away/team2 win."""
        for e in self.entries:
            if e.type == 3:
                return e.odds
        return 0.0


@dataclass
class SportMatchDetail:
    """Full match detail from SportsNow match-detail endpoint.

    Extends the match-list data with highlights, replays, play sources,
    odds, league metadata, and more.
    """
    id: str = ""
    team1: SportTeam = field(default_factory=SportTeam)
    team2: SportTeam = field(default_factory=SportTeam)
    status: str = ""
    play_type: str = ""
    play_path: str = ""
    start_time: str = "0"
    end_time: str = "0"
    sport_type: str = ""
    time_desc: str = ""
    play_sources: list[SportPlaySource] = field(default_factory=list)
    status_live: Any = ""
    league: str = ""
    league_id: str = ""
    league_type: str = ""
    live_device_id: str = ""
    live_type: str = ""
    live_region: str = ""
    team_match_info1: SportTeamMatchInfo = field(default_factory=SportTeamMatchInfo)
    team_match_info2: SportTeamMatchInfo = field(default_factory=SportTeamMatchInfo)
    match_result: str = ""
    match_round: str = ""
    replays: list[SportHighlight] = field(default_factory=list)
    highlights: list[SportHighlight] = field(default_factory=list)
    ext_country_code: str = ""
    is_sub: bool = False
    start_time_tbd: bool = False
    season: str = ""
    season_id: str = ""
    season_kind: str = ""
    live_stream_id: str = ""
    delete_status: str = ""
    odds_info: Optional[SportOddsSource] = None
    odds_sources: list[SportOddsSource] = field(default_factory=list)
    # Extra match metadata
    score: str = ""
    bkt_status: str = ""
    ft_status: str = ""
    ft_kickoff_timestamp: str = ""
    has_ot: bool = False
    has_tf: bool = False
    round_info: dict = field(default_factory=dict)
    stage_mode: str = ""

    @property
    def team1_name(self) -> str:
        return self.team1.name

    @property
    def team2_name(self) -> str:
        return self.team2.name

    @property
    def team1_score(self) -> str:
        return self.team1.score

    @property
    def team2_score(self) -> str:
        return self.team2.score

    @property
    def is_live(self) -> bool:
        return str(self.status_live).lower() in ("living", "1", "2", "true")

    @property
    def start_timestamp(self) -> float:
        """Match start as Unix timestamp in seconds."""
        try:
            return int(self.start_time) / 1000
        except (ValueError, TypeError):
            return 0.0

    @property
    def highlight_urls(self) -> list[str]:
        """Convenience: list of highlight video URLs."""
        return [h.path for h in self.highlights if h.path]

    @property
    def replay_urls(self) -> list[str]:
        """Convenience: list of replay video URLs."""
        return [r.path for r in self.replays if r.path]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SportActivityConfig:
    """Activity configuration returned by the config endpoint."""
    activity_league_ids: list[str] = field(default_factory=list)
    betting_area_enabled: bool = False
    support_country_codes: list[str] = field(default_factory=list)
    match_list_bet_entry_enabled: bool = False
    detail_stay_popup_seconds: int = 5
    daily_checkin_vote_count: int = 1
    home_live_default_image: str = ""
    match_detail_bet_entry_enabled: bool = False
    betting_center_show: bool = False
