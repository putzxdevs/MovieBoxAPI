"""
MovieBoxAPI client — sync HTTP client for the MovieBox streaming platform.

Two API layers:

  **H5 API** (``h5-api.aoneroom.com``)
    Web-facing BFF — home page, catalog browsing, search, detail metadata.
    Authenticated via a bearer token obtained from the home endpoint.

  **V3 Mobile API** (``api*.aoneroom.com``)
    Android-app API — signed (HMAC-MD5) requests for streaming URLs and
    subtitles.  Host-pool failover: if one host returns 4xx/5xx the client
    automatically tries the next.

Usage::

    from movieboxapi import MovieBoxClient

    client = MovieBoxClient(region="ID")

    # Home page
    home = client.get_home()

    # Browse movies
    movies = client.get_movies(page=1)

    # Search
    results = client.search("avengers")

    # Detail
    detail = client.get_detail("/id/movie/some-slug")

    # Stream
    stream = client.get_stream(subject_id="12345", se=1, ep=1)
    print(stream.url)
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional
from urllib.parse import urlencode

import httpx

from .constants import (
    H5_API_BASE,
    H5_HOST,
    REQUEST_TIMEOUT,
    V3_CAPTIONS_PATH,
    V3_HOST_POOL,
    V3_MAIN_PAGE_PATH,
    V3_RESOURCE_PATH,
    V3_RETRY_CODES,
    build_h5_headers,
    generate_v3_client_identity,
)
from .crypto import build_signed_headers, client_token, signature
from .exceptions import APIError, GeoBlockError, RateLimitError, StreamError, TokenError
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
    StreamResult,
    Subtitle,
    Trailer,
)
from .utils import (
    decode_slug,
    derive_title_from_slug,
    encode_slug,
    format_duration,
    parse_genres,
    total_pages,
)

logger = logging.getLogger("movieboxapi")

# Language label mapping for subtitle display
LANG_LABELS: dict[str, str] = {
    "id": "Indonesian",
    "in": "Indonesian",
    "ms": "Malay",
    "ind": "Indonesian",
    "in_id": "Indonesian",
    "en": "English",
    "zh": "中文",
    "ja": "日本語",
    "ko": "한국어",
    "es": "Español",
    "fr": "Français",
    "pt": "Português",
    "ar": "العربية",
    "th": "ไทย",
    "vi": "Tiếng Việt",
    "hi": "हिन्दी",
}

# Resolution labels
RES_LABELS: dict[int, str] = {
    360: "360p",
    480: "480p",
    720: "720p",
    1080: "1080p",
    1440: "1440p",
    2160: "4K",
}


class MovieBoxClient:
    """Synchronous MovieBox API client.

    Parameters
    ----------
    region : str
        Region code (``"ID"``, ``"IN"``, ``"US"``). Controls content locale.
    host : str
        Frontend hostname for H5 API Referer/Origin headers.
    proxy : str or None
        Optional SOCKS5/HTTP proxy URL (e.g. ``"socks5://127.0.0.1:40000"``).
        Useful when your server IP is geo-blocked.
    timeout : float
        HTTP request timeout in seconds.
    """

    def __init__(
        self,
        region: str = "ID",
        host: str = H5_HOST,
        proxy: Optional[str] = None,
        timeout: float = REQUEST_TIMEOUT,
    ) -> None:
        self._region = region.upper()
        self._host = host
        self._proxy = proxy
        self._timeout = timeout

        # H5 bearer token
        self._bearer_token: Optional[str] = None

        # V3 auth token
        self._v3_token: Optional[str] = None

        # V3 device fingerprint (generated once per client instance)
        self._v3_ua, self._v3_ci = generate_v3_client_identity(self._region)

    # ── HTTP plumbing ─────────────────────────────────────────────────────────

    def _http(self) -> httpx.Client:
        """Create a new httpx client (context-managed by callers)."""
        return httpx.Client(
            follow_redirects=True,
            timeout=self._timeout,
            proxy=self._proxy,
        )

    def _extract_token(self, headers: httpx.Headers) -> Optional[str]:
        """Extract bearer token from ``x-user`` response header."""
        x_user = headers.get("x-user", "")
        if x_user:
            try:
                return json.loads(x_user).get("token") or None
            except Exception:
                pass
        return None

    # ── H5 API (web) ─────────────────────────────────────────────────────────

    def _get_bearer_token(self) -> str:
        """Acquire a bearer token from the H5 home endpoint."""
        if self._bearer_token:
            return self._bearer_token
        try:
            headers = build_h5_headers(region=self._region, host=self._host)
            with self._http() as http:
                resp = http.get(
                    f"{H5_API_BASE}/home?host={self._host}/{self._region.lower()}",
                    headers=headers,
                )
                token = self._extract_token(resp.headers)
                if token:
                    self._bearer_token = token
                    return token
                # Cookie fallback
                m = re.search(r"token=([^;]+)", resp.headers.get("set-cookie", ""))
                if m:
                    self._bearer_token = m.group(1)
        except Exception:
            logger.exception("Failed to acquire H5 bearer token")
        return self._bearer_token or ""

    def _h5_request(
        self,
        url: str,
        method: str = "GET",
        payload: Optional[dict] = None,
        extra_headers: Optional[dict] = None,
    ) -> dict:
        """Make an authenticated H5 API request."""
        token = self._get_bearer_token()
        headers = build_h5_headers(
            region=self._region,
            host=self._host,
            extra=extra_headers,
        )
        if token:
            headers["Authorization"] = f"Bearer {token}"

        with self._http() as http:
            if method == "POST":
                resp = http.post(url, headers=headers, json=payload)
            else:
                resp = http.get(url, headers=headers)

            # Refresh token if present
            new_token = self._extract_token(resp.headers)
            if new_token:
                self._bearer_token = new_token

            if resp.status_code == 429:
                raise RateLimitError(
                    "H5 rate limited", status_code=429, url=url
                )
            if resp.status_code == 403:
                raise GeoBlockError(
                    "H5 geo-blocked (403)", status_code=403, url=url
                )
            resp.raise_for_status()
            return resp.json()

    # ── V3 API (mobile) ──────────────────────────────────────────────────────

    def _v3_bootstrap_token(self) -> Optional[str]:
        """Get an auth token from the V3 mobile API."""
        if self._v3_token:
            return self._v3_token
        for base in V3_HOST_POOL:
            try:
                url = f"{base}{V3_MAIN_PAGE_PATH}?page=1&tabId=0&version="
                headers = build_signed_headers(
                    "GET", url,
                    client_info=self._v3_ci,
                    user_agent=self._v3_ua,
                )
                with self._http() as http:
                    resp = http.get(url, headers=headers)
                token = self._extract_token(resp.headers)
                if token:
                    self._v3_token = token
                    return token
                try:
                    t = (resp.json().get("data") or {}).get("token")
                    if t:
                        self._v3_token = t
                        return t
                except Exception:
                    pass
            except Exception:
                logger.debug("V3 token bootstrap failed on %s", base)
        return None

    def _v3_request(
        self,
        path: str,
        params: Optional[dict] = None,
        include_play_mode: bool = False,
    ) -> Optional[Any]:
        """Make a signed V3 request with host-pool failover."""
        token = self._v3_bootstrap_token()
        qs = ""
        if params:
            qs = "?" + urlencode(params)

        for base in V3_HOST_POOL:
            try:
                full_url = f"{base}{path}{qs}"
                headers = build_signed_headers(
                    "GET",
                    full_url,
                    include_play_mode=include_play_mode,
                    auth_token=token,
                    client_info=self._v3_ci,
                    user_agent=self._v3_ua,
                )
                with self._http() as http:
                    resp = http.get(full_url, headers=headers)

                new_token = self._extract_token(resp.headers)
                if new_token:
                    self._v3_token = new_token
                    token = new_token

                if resp.status_code in V3_RETRY_CODES:
                    logger.debug(
                        "V3 host %s returned %s, trying next", base, resp.status_code
                    )
                    continue

                resp.raise_for_status()
                body = resp.json()
                return body.get("data") if "data" in body else body
            except Exception as exc:
                logger.debug("V3 request error on %s: %s", base, exc)

        logger.warning("V3 all hosts exhausted for path=%s", path)
        return None

    # ── Public: Home ──────────────────────────────────────────────────────────

    def get_home(self) -> list[HomeSection]:
        """Fetch the homepage and return a list of :class:`HomeSection`.

        Each section contains a ``type`` (banner / movie / tv / animation /
        sport_live) and a list of items.
        """
        try:
            data = self._h5_request(f"{H5_API_BASE}/home?host={self._host}/{self._region.lower()}")
        except (APIError, RateLimitError, GeoBlockError):
            raise
        except Exception as exc:
            raise APIError(f"get_home failed: {exc}") from exc

        sections: list[HomeSection] = []
        for op in (data.get("data", {}) or {}).get("operatingList", []) or []:
            op_type = op.get("type")
            title = op.get("title") or "Featured"

            if op_type == "BANNER":
                items = []
                for item in op.get("banner", {}).get("items", []) or []:
                    subject = item.get("subject") or {}
                    name = item.get("title") or subject.get("title")
                    if not name or "Communities" in name:
                        continue
                    raw_slug = item.get("detailPath") or subject.get("detailPath") or ""
                    items.append(
                        MediaItem(
                            subject_id=str(subject.get("subjectId") or ""),
                            title=name,
                            poster=(
                                (item.get("image") or {}).get("url")
                                or (subject.get("cover") or {}).get("url")
                                or ""
                            ),
                            detail_path=raw_slug,
                            rating=subject.get("imdbRatingValue"),
                        )
                    )
                sections.append(HomeSection(type="banner", name="Banner", items=items))

            elif op_type == "SPORT_LIVE":
                matches: list[dict] = []
                for match in op.get("liveList") or []:
                    t1 = match.get("team1") or {}
                    t2 = match.get("team2") or {}
                    matches.append({
                        "match_id": match.get("matchId"),
                        "team1_name": (t1.get("nameI18n") or {}).get("id") or t1.get("name", ""),
                        "team1_score": t1.get("score", "0"),
                        "team1_avatar": t1.get("avatar", ""),
                        "team1_abbr": t1.get("abbreviation", ""),
                        "team2_name": (t2.get("nameI18n") or {}).get("id") or t2.get("name", ""),
                        "team2_score": t2.get("score", "0"),
                        "team2_avatar": t2.get("avatar", ""),
                        "team2_abbr": t2.get("abbreviation", ""),
                        "status": match.get("status", ""),
                        "start_ms": match.get("startTime"),
                        "url": match.get("url", ""),
                        "image": (match.get("image") or {}).get("url", ""),
                    })
                sections.append(
                    HomeSection(
                        type="sport_live",
                        name=title,
                        items=matches,
                        sport_url=op.get("url", ""),
                    )
                )

            elif op_type in ("SUBJECTS_MOVIE", "SUBJECTS_TV", "SUBJECTS_ANIMATION"):
                type_key = {
                    "SUBJECTS_MOVIE": "movie",
                    "SUBJECTS_TV": "tv",
                    "SUBJECTS_ANIMATION": "animation",
                }[op_type]
                items = [
                    MediaItem(
                        subject_id=str(sub.get("subjectId") or ""),
                        title=sub.get("title") or "",
                        poster=(sub.get("cover") or {}).get("url") or "",
                        detail_path=sub.get("detailPath") or "",
                        rating=sub.get("imdbRatingValue"),
                        year=(sub.get("releaseDate") or "")[:4] or None,
                    )
                    for sub in op.get("subjects", []) or []
                ]
                sections.append(HomeSection(type=type_key, name=title, items=items))

        return sections

    # ── Public: Catalog ───────────────────────────────────────────────────────

    def _fetch_catalog(
        self, tab_id: int, page: int = 1, per_page: int = 24, sort: str = "RECOMMEND"
    ) -> CatalogPage:
        """Fetch a catalog page for the given tab ID."""
        try:
            payload = {
                "tabId": tab_id,
                "filter": {
                    "sort": sort,
                    "genre": "ALL",
                    "country": "ALL",
                    "year": "ALL",
                    "language": "ALL",
                },
                "page": page,
                "perPage": per_page,
            }
            data = self._h5_request(f"{H5_API_BASE}/subject/filter", method="POST", payload=payload)
            inner = data.get("data", {}) or {}
            raw = inner.get("items", inner.get("subjects", [])) or []
            items = [
                MediaItem(
                    subject_id=str(sub.get("subjectId") or ""),
                    title=sub.get("title") or "",
                    poster=(sub.get("cover") or {}).get("url") or "",
                    detail_path=sub.get("detailPath") or "",
                    rating=sub.get("imdbRatingValue"),
                    year=(sub.get("releaseDate") or "")[:4] or None,
                )
                for sub in raw
            ]
            pager = inner.get("pager", {}) or {}
            tot = pager.get("totalCount") or inner.get("total") or len(items)
            return CatalogPage(
                items=items,
                page=page,
                per_page=per_page,
                total=tot,
                total_page=total_pages(tot, per_page),
            )
        except (APIError, RateLimitError, GeoBlockError):
            raise
        except Exception as exc:
            raise APIError(f"Catalog fetch failed (tab_id={tab_id}): {exc}") from exc

    def get_movies(self, page: int = 1, sort: str = "RECOMMEND") -> CatalogPage:
        """Browse movies catalog."""
        return self._fetch_catalog(tab_id=2, page=page, sort=sort)

    def get_tv_series(self, page: int = 1, sort: str = "RECOMMEND") -> CatalogPage:
        """Browse TV series catalog."""
        return self._fetch_catalog(tab_id=5, page=page, sort=sort)

    def get_animation(self, page: int = 1, sort: str = "RECOMMEND") -> CatalogPage:
        """Browse animation catalog."""
        return self._fetch_catalog(tab_id=8, page=page, sort=sort)

    # ── Public: Search ────────────────────────────────────────────────────────

    def search(self, query: str, page: int = 1, per_page: int = 20) -> SearchResult:
        """Search for movies / TV shows by keyword."""
        try:
            data = self._h5_request(
                f"{H5_API_BASE}/subject/search",
                method="POST",
                payload={"keyword": query, "page": page, "perPage": per_page},
            )
            inner = data.get("data", {}) or {}
            raw = inner.get("items", inner.get("list", [])) or []
            items: list[MediaItem] = []
            for sub in raw:
                node = sub.get("subject", sub) if isinstance(sub, dict) else {}
                items.append(
                    MediaItem(
                        subject_id=str(node.get("subjectId") or ""),
                        title=node.get("title") or "",
                        poster=(node.get("cover") or {}).get("url") or "",
                        detail_path=node.get("detailPath") or "",
                        rating=node.get("imdbRatingValue"),
                        year=(node.get("releaseDate") or "")[:4] or None,
                    )
                )
            pager = inner.get("pager", {}) or {}
            tot = pager.get("totalCount") or inner.get("total") or len(items)
            return SearchResult(query=query, page=page, total=tot, items=items)
        except (APIError, RateLimitError, GeoBlockError):
            raise
        except Exception as exc:
            logger.exception("Search failed for %r", query)
            return SearchResult(query=query, page=page, total=0, items=[])

    # ── Public: Detail ────────────────────────────────────────────────────────

    def get_detail(
        self, slug: str, subject_id: Optional[str] = None
    ) -> MediaDetail:
        """Fetch full metadata for a title.

        Parameters
        ----------
        slug : str
            The ``detailPath`` (e.g. ``/id/movie/title-slug``).
            If it looks base64-encoded, it will be decoded automatically.
        subject_id : str, optional
            Numeric MovieBox subjectId; used as fallback when the H5 detail
            endpoint returns 404 (stale slug).
        """
        # Auto-decode if caller passes encoded slug
        if slug and not slug.startswith("/"):
            slug = decode_slug(slug)

        inner: dict = {}
        subject: dict = {}

        try:
            data = self._h5_request(f"{H5_API_BASE}/detail?detailPath={slug}")
            inner = data.get("data", {}) or {}
            subject = inner.get("subject", inner) or {}
            if not subject_id:
                subject_id = str(subject.get("subjectId") or "")
        except Exception as exc:
            is_404 = "404" in str(exc)
            if is_404 and subject_id:
                logger.warning(
                    "H5 detail 404 for %r — using V3 fallback (subject_id=%s)",
                    slug, subject_id,
                )
            else:
                raise APIError(f"get_detail failed for {slug!r}: {exc}") from exc

        # Parse genres
        genres = parse_genres(subject.get("genre") or subject.get("genres"))

        # Duration
        duration = format_duration(
            subject.get("durationSeconds") or subject.get("duration")
        )

        # Seasons — primary source: inner["resource"]["seasons"]
        resource = inner.get("resource") or {}
        resource_seasons = resource.get("seasons") or []
        seasons: list[Season] = []

        if resource_seasons:
            for s in resource_seasons:
                se_num = s.get("se") or 1
                max_ep = s.get("maxEp") or 0
                eps = (
                    [Episode(ep=i) for i in range(1, max_ep + 1)]
                    if max_ep > 0
                    else [Episode(ep=1)]
                )
                seasons.append(Season(season=se_num, title=f"Season {se_num}", episodes=eps))
        else:
            # Legacy fallback
            for season in inner.get("seasons", []) or subject.get("seasons", []) or []:
                eps = [
                    Episode(ep=ep.get("se") or ep.get("ep") or idx + 1)
                    for idx, ep in enumerate(season.get("episodes", []) or [])
                ] or [Episode(ep=1)]
                seasons.append(
                    Season(
                        season=season.get("season") or season.get("se") or 1,
                        title=season.get("title") or f"Season {season.get('season', 1)}",
                        episodes=eps,
                    )
                )

        # Trailer
        trailer_raw = subject.get("trailer") or {}
        trailer: Optional[Trailer] = None
        if isinstance(trailer_raw, dict):
            va = trailer_raw.get("VideoAddress") or trailer_raw.get("videoAddress") or {}
            cover = trailer_raw.get("cover") or {}
            trailer_url = va.get("url") if isinstance(va, dict) else None
            trailer_cover = cover.get("url") if isinstance(cover, dict) else None
            if trailer_url:
                trailer = Trailer(
                    url=trailer_url,
                    cover=trailer_cover,
                    duration=va.get("duration") if isinstance(va, dict) else None,
                    definition=va.get("definition") if isinstance(va, dict) else None,
                )

        # Cast
        cast: list[CastMember] = []
        for staff in subject.get("staffList") or subject.get("staff_list") or []:
            if isinstance(staff, dict):
                st = staff.get("staffType", 0)
                cast.append(
                    CastMember(
                        name=staff.get("name", ""),
                        character=staff.get("character", ""),
                        type=st,
                        type_label=(
                            "Director" if st == 1
                            else "Actor" if st == 2
                            else "Writer" if st == 3
                            else "Other"
                        ),
                        avatar=staff.get("avatarUrl") or staff.get("avatar_url") or "",
                    )
                )

        # Dubs — each dub/sub variant has its own subjectId + detailPath
        dubs: list[Dub] = []
        for d in subject.get("dubs") or []:
            if isinstance(d, dict):
                dubs.append(
                    Dub(
                        subject_id=str(d.get("subjectId") or ""),
                        lan_name=d.get("lanName") or d.get("lan_name") or "",
                        lan_code=d.get("lanCode") or d.get("lan_code") or "",
                        detail_path=d.get("detailPath") or d.get("detail_path") or "",
                        type=d.get("type", 0),
                        original=bool(d.get("original", False)),
                    )
                )

        total_eps = sum(len(s.episodes) for s in seasons)
        title_fallback = derive_title_from_slug(slug) if slug else "Untitled"

        # V3 supplemental metadata
        if subject_id:
            try:
                v3_meta = self._v3_request(
                    V3_RESOURCE_PATH,
                    params={"subjectId": subject_id, "page": 1, "perPage": 1},
                )
                if v3_meta and isinstance(v3_meta, dict):
                    if not subject.get("title") and v3_meta.get("subjectTitle"):
                        subject["title"] = v3_meta["subjectTitle"]
                    if not subject.get("description") and v3_meta.get("description"):
                        subject["description"] = v3_meta["description"]
                    if not subject.get("countryName") and v3_meta.get("countryName"):
                        subject["countryName"] = v3_meta["countryName"]
                    if not subject.get("releaseDate") and v3_meta.get("releaseDate"):
                        subject["releaseDate"] = v3_meta["releaseDate"]
                    if not subject.get("genre") and v3_meta.get("genre"):
                        subject["genre"] = v3_meta["genre"]
                    if not subject.get("cover") and v3_meta.get("cover"):
                        subject["cover"] = v3_meta["cover"]
                    if not subject.get("durationSeconds") and v3_meta.get("durationSeconds"):
                        subject["durationSeconds"] = v3_meta["durationSeconds"]
                    if not subject.get("imdbRatingValue") and v3_meta.get("imdbRatingValue"):
                        subject["imdbRatingValue"] = v3_meta["imdbRatingValue"]
                    v3_total = v3_meta.get("totalEpisode") or 0
                    if not seasons and v3_total > 0:
                        seasons = [
                            Season(
                                season=1,
                                title="Season 1",
                                episodes=[Episode(ep=i) for i in range(1, v3_total + 1)],
                            )
                        ]
                        total_eps = v3_total
                    # Re-parse if we just set them
                    if not genres and subject.get("genre"):
                        genres = parse_genres(subject.get("genre"))
                    if not duration and subject.get("durationSeconds"):
                        duration = format_duration(subject["durationSeconds"])
            except Exception:
                pass

        return MediaDetail(
            subject_id=subject_id or str(subject.get("subjectId") or ""),
            title=subject.get("title") or title_fallback,
            rating=subject.get("imdbRatingValue"),
            year=(subject.get("releaseDate") or "")[:4] or None,
            country=subject.get("countryName"),
            duration=duration,
            genres=genres,
            synopsis=subject.get("description") or subject.get("intro") or "",
            seasons=seasons,
            total_episodes=total_eps,
            poster=(subject.get("cover") or {}).get("url"),
            trailer=trailer,
            cast=cast,
            dubs=dubs,
            content_rating=subject.get("contentRating") or subject.get("content_rating") or "",
            aka=subject.get("aka") or "",
            viewers=subject.get("viewers") or 0,
            want_to_see=subject.get("wantToSeeCount") or subject.get("want_to_see_count") or 0,
            have_seen=subject.get("haveSeenCount") or subject.get("have_seen_count") or 0,
            subtitles=subject.get("subtitles") or [],
        )

    # ── Public: Streaming ─────────────────────────────────────────────────────

    def get_stream(
        self,
        subject_id: str,
        se: int = 1,
        ep: int = 1,
        resolution: int = 1080,
        lan: Optional[str] = None,
    ) -> StreamResult:
        """Get a playable stream URL with qualities and subtitles.

        Parameters
        ----------
        subject_id : str
            The MovieBox subject ID (from :meth:`get_detail`).
        se : int
            Season number.
        ep : int
            Episode number.
        resolution : int
            Preferred resolution (e.g. 360, 480, 720, 1080).
        lan : str, optional
            Preferred audio language code.

        Returns
        -------
        StreamResult
            Contains ``url``, ``subtitle_url``, ``resource_id``,
            ``qualities``, and ``subtitles``.
        """
        if not subject_id:
            raise StreamError("subject_id is required")

        params: dict[str, Any] = {
            "subjectId": subject_id,
            "resolution": resolution,
            "page": 1,
            "perPage": 20,
        }
        if se > 0 or ep > 0:
            params["se"] = se
            params["ep"] = ep
        if lan:
            params["lan"] = lan

        logger.info(
            "V3 resource request subject_id=%s se=%s ep=%s res=%s",
            subject_id, se, ep, resolution,
        )

        data = self._v3_request(V3_RESOURCE_PATH, params=params, include_play_mode=True)
        if not data:
            raise StreamError(f"No stream data for subject_id={subject_id}")

        # Parse response
        collection_resolutions: list = []
        if isinstance(data, dict):
            collection_resolutions = data.get("collectionResolutions") or []

        items: list = []
        if isinstance(data, list):
            items = data
        elif isinstance(data, dict):
            items = data.get("list", data.get("items", [])) or []

        if not items:
            raise StreamError(f"No stream items for subject_id={subject_id}")

        # Find target episode
        target = None
        for item in items:
            if (se, ep) == (item.get("se", 0), item.get("ep", 0)):
                target = item
                break
        if target is None:
            target = max(items, key=lambda x: x.get("resolution", 0))

        video_url = str(target.get("resourceLink") or target.get("sourceUrl") or "")
        resource_id = str(target.get("resourceId") or "")
        if not video_url:
            raise StreamError("Stream URL is empty in API response")

        # Build quality list
        qualities: list[Quality] = []
        if collection_resolutions:
            for r in sorted(collection_resolutions, key=lambda x: x.get("resolution", 0)):
                res = r.get("resolution", 0)
                if res:
                    qualities.append(
                        Quality(
                            resolution=res,
                            label=RES_LABELS.get(res, f"{res}p"),
                            current=(res == resolution),
                        )
                    )

        if not qualities and items:
            seen: set[int] = set()
            for it in items:
                res = it.get("resolution", 0)
                if res and res not in seen:
                    seen.add(res)
                    qualities.append(
                        Quality(
                            resolution=res,
                            label=RES_LABELS.get(res, f"{res}p"),
                            current=(res == resolution),
                        )
                    )
            qualities.sort(key=lambda q: q.resolution)

        # Subtitles
        inline_captions = target.get("extCaptions") or []
        dedicated_captions = self._fetch_captions(subject_id, resource_id)

        all_captions = list(inline_captions)
        seen_ids = {id(c) for c in all_captions}
        for cap in dedicated_captions:
            if id(cap) not in seen_ids:
                all_captions.append(cap)

        seen_langs: set[str] = set()
        subtitles: list[Subtitle] = []
        for cap in all_captions:
            lc = (cap.get("lan") or cap.get("language") or "").lower()
            url = cap.get("url") or ""
            if lc and url and lc not in seen_langs:
                seen_langs.add(lc)
                subtitles.append(
                    Subtitle(
                        lang=lc,
                        label=LANG_LABELS.get(lc, lc.upper()),
                        url=url,
                    )
                )

        # Prefer Indonesian subtitle
        subtitle_url = self._find_preferred_subtitle(
            all_captions, subject_id, resource_id
        )
        if not subtitle_url and subtitles:
            subtitle_url = subtitles[0].url

        return StreamResult(
            url=video_url,
            subtitle_url=subtitle_url or "",
            resource_id=resource_id,
            qualities=qualities,
            subtitles=subtitles,
        )

    def _fetch_captions(self, subject_id: str, resource_id: str) -> list[dict]:
        """Fetch dedicated captions from V3 captions endpoint."""
        if not resource_id:
            return []
        try:
            data = self._v3_request(
                V3_CAPTIONS_PATH,
                params={"subjectId": subject_id, "resourceId": resource_id},
            )
            if not data:
                return []
            if isinstance(data, dict):
                return data.get("extCaptions", data.get("captions", [])) or []
            if isinstance(data, list):
                return data
            return []
        except Exception:
            logger.debug("Dedicated captions fetch failed for resource_id=%s", resource_id)
            return []

    @staticmethod
    def _find_preferred_subtitle(
        captions: list[dict],
        subject_id: str = "",
        resource_id: str = "",
    ) -> Optional[str]:
        """Find the best subtitle URL, preferring Indonesian."""
        exact_indonesian = {"id", "ind", "in_id"}
        all_indonesian = {"id", "in", "ms", "ind"}

        for cap in captions:
            lc = (cap.get("lan") or cap.get("language") or "").lower()
            if lc in exact_indonesian or lc.startswith("in_") or lc.startswith("id"):
                url = cap.get("url") or ""
                if url:
                    return str(url)

        for cap in captions:
            lc = (cap.get("lan") or cap.get("language") or "").lower()
            if lc in all_indonesian or lc.startswith("in"):
                url = cap.get("url") or ""
                if url:
                    return str(url)

        return None

    # ── Convenience ───────────────────────────────────────────────────────────

    def get_stream_url(
        self,
        subject_id: str,
        se: int = 1,
        ep: int = 1,
        resolution: int = 1080,
    ) -> str:
        """Shorthand: return just the video URL string."""
        result = self.get_stream(subject_id, se=se, ep=ep, resolution=resolution)
        return result.url