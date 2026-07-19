"""
SportsNow API client — integrated into MovieBoxAPI.

SportsNow (https://sportsnow.top) is a live sports streaming platform powered
by the same aoneroom/MovieBox backend infrastructure. This module provides
clean Python access to its API endpoints, bypassing the ad-heavy web frontend.

Supported sports: football, basketball, tennis, cricket, volleyball, etc.

Quick start::

    from movieboxapi import SportsNowClient

    client = SportsNowClient()

    # Get live/upcoming matches
    for match in client.get_matches(sport_type="football"):
        print(f"{match.team1_name} vs {match.team2_name}")
        print(f"  Status: {match.status}, League: {match.league}")

    # Get activity config
    config = client.get_activity_config()
    print(config)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

from .exceptions import APIError
from .models import (
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
)
from .sportsnow_constants import (
    SPORTSNAW_API_BASE,
    SPORTSNAW_ORIGIN,
    build_sportsnow_headers,
)

__all__ = ["SportsNowClient"]

_log = logging.getLogger(__name__)


class SportsNowClient:
    """Thin wrapper around the SportsNow API.

    Parameters
    ----------
    timeout : float
        HTTP timeout in seconds (default 25).
    """

    def __init__(self, timeout: float = 25.0) -> None:
        import httpx

        self._timeout = timeout
        self._client = httpx.Client(
            headers=build_sportsnow_headers(),
            timeout=timeout,
            follow_redirects=True,
        )

    # ── context manager ────────────────────────────────────────────────────
    def get_match_detail(
        self,
        match_id: str,
        sport_type: str = "football",
    ) -> SportMatchDetail:
        """Get full match detail including highlights, replays, play sources, odds, etc.

        Parameters
        ----------
        match_id : str
            The match ID (from match-list or detail page).
        sport_type : str
            Sport type filter (default ``"football"``).

        Returns
        -------
        SportMatchDetail
            Full match detail with odds, highlights, replays, league info, etc.
        """
        raw = self._get(
            "/wefeed-h5api-bff/live/match-detail",
            {"id": match_id, "sportType": sport_type},
        )
        return _parse_match_detail(raw)

    def get_match_detail_raw(
        self,
        match_id: str,
        sport_type: str = "football",
    ) -> dict[str, Any]:
        """Get raw match detail dict (unparsed) from the API.

        Use this if you need the raw JSON structure for advanced processing.
        """
        return self._get(
            "/wefeed-h5api-bff/live/match-detail",
            {"id": match_id, "sportType": sport_type},
        )

    def get_match_odds(
        self,
        match_id: str,
        sport_type: str = "football",
    ) -> list[SportOddsSource]:
        """Convenience: return only the odds sources for a match.

        Each source has ``home``, ``draw``, ``away`` properties for quick access.

        Returns
        -------
        list[SportOddsSource]
            Odds from different providers (bangbet, marketing, etc.).
        """
        detail = self.get_match_detail(match_id, sport_type)
        return detail.odds_sources

    def get_highlight_urls(
        self,
        match_id: str,
        sport_type: str = "football",
    ) -> list[str]:
        """Convenience: return only the highlight video URLs (HLS) for a match."""
        detail = self.get_match_detail(match_id, sport_type)
        return detail.highlight_urls

    def get_replay_urls(
        self,
        match_id: str,
        sport_type: str = "football",
    ) -> list[str]:
        """Convenience: return only the replay video URLs (HLS) for a match."""
        detail = self.get_match_detail(match_id, sport_type)
        return detail.replay_urls

    def close(self) -> None:
        """Close the underlying HTTP client."""
        self._client.close()

    def __enter__(self) -> SportsNowClient:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ── internal helpers ───────────────────────────────────────────────────
    def _get(self, path: str, params: Optional[dict] = None) -> dict:
        """Make a GET request to the SportsNow API."""
        url = f"{SPORTSNAW_API_BASE}{path}"
        _log.debug("GET %s params=%s", url, params)
        resp = self._client.get(url, params=params)
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") != 0:
            raise APIError(
                f"SportsNow API error: {body.get('message', 'unknown')}",
                code=body.get("code"),
            )
        return body.get("data", {})

    # ── public API ─────────────────────────────────────────────────────────
    def get_activity_config(self, sport_type: str = "football") -> dict[str, Any]:
        """Get activity configuration (league IDs, feature flags, etc.).

        Returns the raw API response data dict.
        """
        return self._get("/wefeed-h5api-bff/live/activity/config", {"sportType": sport_type})

    def get_matches(
        self,
        sport_type: str = "football",
        tag_id: str = "0",
        page: int = 1,
    ) -> list[SportMatch]:
        """Get live and upcoming matches for a sport.

        Parameters
        ----------
        sport_type : str
            Sport type: ``"football"``, ``"basketball"``, ``"tennis"``,
            ``"cricket"``, ``"volleyball"``, etc.
        tag_id : str
            League / tag filter. ``"0"`` means all leagues.
        page : int
            Page number for pagination (default 1).

        Returns
        -------
        list[SportMatch]
            List of match objects.
        """
        params = {
            "sportType": sport_type,
            "currentTagId": tag_id,
        }
        if page > 1:
            params["page"] = str(page)

        data = self._get("/wefeed-h5api-bff/live/match-list", params)
        raw_list = data.get("list") or []
        return [_parse_match(m) for m in raw_list]

    def get_all_matches(
        self,
        sport_type: str = "football",
        tag_id: str = "0",
    ) -> list[SportMatch]:
        """Get all matches (auto-paginate through all pages).

        Parameters
        ----------
        sport_type : str
            Sport type filter.
        tag_id : str
            League / tag filter.

        Returns
        -------
        list[SportMatch]
            All matches across all pages.
        """
        all_matches: list[SportMatch] = []
        page = 1
        while True:
            data = self._get(
                "/wefeed-h5api-bff/live/match-list",
                {"sportType": sport_type, "currentTagId": tag_id, "page": str(page)},
            )
            raw_list = data.get("list") or []
            if not raw_list:
                break
            all_matches.extend(_parse_match(m) for m in raw_list)
            if not data.get("hasMore", False):
                break
            page += 1
        return all_matches


# ── Parser helpers ─────────────────────────────────────────────────────────


def _parse_team(raw: Optional[dict]) -> SportTeam:
    """Parse a team object from API response."""
    if not raw:
        return SportTeam()
    name_i18n = raw.get("nameI18n") or {}
    return SportTeam(
        id=str(raw.get("id", "")),
        name=name_i18n.get("id") or raw.get("name", ""),
        score=str(raw.get("score", "0")),
        avatar=raw.get("avatar", ""),
        vote_count=str(raw.get("voteCount", "0")),
        sport_type=raw.get("type", ""),
        abbreviation=raw.get("abbreviation", ""),
        regular_score=raw.get("regularScore", ""),
        name_tag=raw.get("nameTag", ""),
    )


def _parse_team_match_info(raw: Optional[dict]) -> SportTeamMatchInfo:
    """Parse team match info from API response."""
    if not raw:
        return SportTeamMatchInfo()
    return SportTeamMatchInfo(
        score=str(raw.get("score", "0")),
        runs_scored=raw.get("crtRunsScored", ""),
        wickets_lost=raw.get("crtWicketsLost", ""),
        overs=raw.get("crtOvers", ""),
        extra_balls=raw.get("crtOversExtraBalls", ""),
    )


def _parse_play_source(raw: Optional[dict]) -> SportPlaySource:
    """Parse a play source/channel entry."""
    if not raw:
        return SportPlaySource()
    return SportPlaySource(
        title=raw.get("title", ""),
        path=raw.get("path", ""),
        id=str(raw.get("id", "0")),
        cover=raw.get("cover"),
        duration=str(raw.get("duration", "0")),
    )


def _parse_highlight(raw: Optional[dict]) -> SportHighlight:
    """Parse a highlight video entry."""
    if not raw:
        return SportHighlight()
    return SportHighlight(
        title=raw.get("title", ""),
        path=raw.get("path", ""),
        cover=raw.get("cover"),
        duration=str(raw.get("duration", "0")),
    )


def _parse_news(raw: Optional[dict]) -> SportNews:
    """Parse a sports news entry."""
    if not raw:
        return SportNews()

    cover_raw = raw.get("cover") or {}
    stat_raw = raw.get("stat") or {}

    return SportNews(
        id=str(raw.get("id", "")),
        title=raw.get("title", ""),
        summary=raw.get("summary", ""),
        status=int(raw.get("status", 0)),
        media_type=raw.get("mediaType", ""),
        created_at=str(raw.get("createdAt", "")),
        updated_at=str(raw.get("updatedAt", "")),
        stat=SportNewsStats(
            view_count=int(stat_raw.get("viewCount", 0)),
            like_count=int(stat_raw.get("likeCount", 0)),
            comment_count=int(stat_raw.get("commentCount", 0)),
            share_count=int(stat_raw.get("shareCount", 0)),
        ),
        cover_url=cover_raw.get("url", ""),
        detail_path=raw.get("detailPath", ""),
    )


def _parse_odds_entry(raw: dict) -> SportOddsEntry:
    """Parse a single odds entry (type + odds value)."""
    return SportOddsEntry(
        type=int(raw.get("type", 0)),
        odds=float(raw.get("odds", 0)),
    )


def _parse_odds_source(raw: dict) -> SportOddsSource:
    """Parse an odds source (e.g. bangbet, marketing) with its entries."""
    entries = [_parse_odds_entry(e) for e in (raw.get("oddsList") or [])]
    return SportOddsSource(
        source=raw.get("source", ""),
        jump_url=raw.get("jumpUrl", ""),
        entries=entries,
    )


def _parse_match_detail(raw: dict) -> SportMatchDetail:
    """Parse a full match detail from the match-detail endpoint."""
    play_sources = [_parse_play_source(ps) for ps in (raw.get("playSource") or [])]
    highlights = [_parse_highlight(h) for h in (raw.get("highlights") or [])]
    replays = [_parse_highlight(r) for r in (raw.get("replay") or [])]

    # Parse odds: oddsInfo is a single source, oddsList is multiple sources
    odds_info = None
    if raw.get("oddsInfo"):
        odds_info = _parse_odds_source(raw["oddsInfo"])

    odds_sources = []
    for src in (raw.get("oddsList") or []):
        odds_sources.append(_parse_odds_source(src))

    # Parse leagueItem if present
    league_item = raw.get("leagueItem") or {}

    return SportMatchDetail(
        id=str(raw.get("id", "")),
        team1=_parse_team(raw.get("team1")),
        team2=_parse_team(raw.get("team2")),
        status=raw.get("status", ""),
        play_type=raw.get("playType", ""),
        play_path=raw.get("playPath", ""),
        start_time=str(raw.get("startTime", "0")),
        end_time=str(raw.get("endTime", "0")),
        sport_type=raw.get("type", ""),
        time_desc=raw.get("timeDesc", ""),
        play_sources=play_sources,
        status_live=raw.get("statusLive", ""),
        league=raw.get("league", ""),
        league_id=raw.get("leagueId", ""),
        league_type=raw.get("leagueType", ""),
        live_device_id=raw.get("liveDeviceId", ""),
        live_type=raw.get("liveType", ""),
        live_region=raw.get("liveRegion", ""),
        team_match_info1=_parse_team_match_info(raw.get("teamMatchInfo1")),
        team_match_info2=_parse_team_match_info(raw.get("teamMatchInfo2")),
        match_result=raw.get("matchResult", ""),
        match_round=raw.get("matchRound", ""),
        replays=replays,
        highlights=highlights,
        ext_country_code=raw.get("extCountryCode", ""),
        is_sub=bool(raw.get("isSub", False)),
        start_time_tbd=bool(raw.get("startTimeTbd", False)),
        season=raw.get("season", ""),
        season_id=raw.get("seasonId", ""),
        season_kind=raw.get("seasonKind", ""),
        live_stream_id=raw.get("liveStreamId", ""),
        delete_status=raw.get("deleteStatus", ""),
        odds_info=odds_info,
        odds_sources=odds_sources,
        score=str(raw.get("score", "")),
        bkt_status=raw.get("bktStatus", ""),
        ft_status=raw.get("ftStatus", ""),
        ft_kickoff_timestamp=str(raw.get("ftKickoffTimestamp", "")),
        has_ot=bool(raw.get("hasOt", False)),
        has_tf=bool(raw.get("hasTf", False)),
        round_info=raw.get("round") or {},
        stage_mode=raw.get("stageMode", ""),
    )


def _parse_match(raw: dict) -> SportMatch:
    """Parse a match entry from the API match-list response."""
    play_sources = [_parse_play_source(ps) for ps in (raw.get("playSource") or [])]
    highlights = [_parse_highlight(h) for h in (raw.get("highlights") or [])]
    replays = [_parse_highlight(r) for r in (raw.get("replay") or [])]

    return SportMatch(
        id=str(raw.get("id", "")),
        team1=_parse_team(raw.get("team1")),
        team2=_parse_team(raw.get("team2")),
        status=raw.get("status", ""),
        play_type=raw.get("playType", ""),
        play_path=raw.get("playPath", ""),
        start_time=str(raw.get("startTime", "0")),
        end_time=str(raw.get("endTime", "0")),
        sport_type=raw.get("type", ""),
        time_desc=raw.get("timeDesc", ""),
        play_sources=play_sources,
        status_live=raw.get("statusLive", ""),
        league=raw.get("league", ""),
        live_device_id=raw.get("liveDeviceId", ""),
        team_match_info1=_parse_team_match_info(raw.get("teamMatchInfo1")),
        team_match_info2=_parse_team_match_info(raw.get("teamMatchInfo2")),
        match_result=raw.get("matchResult", ""),
        match_round=raw.get("matchRound", ""),
        replays=replays,
        highlights=highlights,
        ext_country_code=raw.get("extCountryCode", ""),
        league_id=raw.get("leagueId", ""),
        is_collect=bool(raw.get("isCollect", False)),
        arranged_time=str(raw.get("arrangedTime", "0")),
        season=raw.get("season", ""),
    )
