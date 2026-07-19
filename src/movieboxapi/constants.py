"""
Constants for MovieBoxAPI.

MovieBox is a multi-region streaming platform. The same backend (aoneroom)
powers several frontends:

  - https://h5.aoneroom.com/id
  - https://themoviebox.org/id
  - https://moviebox.pk/id
  - https://movieboxapp.in/id
  - https://moviebox.ph/id

H5 (web) API  → catalog / search / detail
V3 (mobile)   → signed streaming + subtitles
"""

from __future__ import annotations

import os
import random
import uuid
from enum import IntEnum
from typing import Optional

# ── H5 (web) API ──────────────────────────────────────────────────────────────
H5_API_BASE: str = "https://h5-api.aoneroom.com/wefeed-h5api-bff"
H5_HOST: str = "moviebox.ph"  # host query param; region path is separate

# Known public frontends (mirrors of the same product)
FRONTENDS: tuple[str, ...] = (
    "https://h5.aoneroom.com",
    "https://themoviebox.org",
    "https://moviebox.pk",
    "https://movieboxapp.in",
    "https://moviebox.ph",
)

# ── V3 (mobile) API host pool ─────────────────────────────────────────────────
# These are backend API hosts, NOT content mirrors. The client tries them in
# order and falls over on 403/429/5xx.
V3_HOST_POOL: list[str] = [
    "https://api8.aoneroom.com",
    "https://api7.aoneroom.com",
    "https://api6.aoneroom.com",
    "https://api5.aoneroom.com",
    "https://api4.aoneroom.com",
    "https://api4sg.aoneroom.com",
    "https://api3.aoneroom.com",
    "https://api6sg.aoneroom.com",
    "https://api.inmoviebox.com",
]

# ── V3 paths ──────────────────────────────────────────────────────────────────
V3_MAIN_PAGE_PATH: str = "/wefeed-mobile-bff/tab-operating"
V3_RESOURCE_PATH: str = "/wefeed-mobile-bff/subject-api/resource"
V3_CAPTIONS_PATH: str = "/wefeed-mobile-bff/subject-api/get-ext-captions"
V3_SUBJECT_GET_PATH: str = "/wefeed-mobile-bff/subject-api/get"
V3_SEASON_INFO_PATH: str = "/wefeed-mobile-bff/subject-api/season-info"
V3_PLAY_INFO_PATH: str = "/wefeed-mobile-bff/subject-api/play-info"
V3_SEARCH_PATH: str = "/wefeed-mobile-bff/subject-api/search"

# ── HMAC secrets (base64) used to sign V3 requests ────────────────────────────
# Overridable via env for future key rotation.
V3_SECRET_DEFAULT: str = (
    os.getenv("MOVIEBOX_SECRET_KEY_DEFAULT", "").strip()
    or "76iRl07s0xSN9jqmEWAt79EBJZulIQIsV64FZr2O"
)
V3_SECRET_ALT: str = (
    os.getenv("MOVIEBOX_SECRET_KEY_ALT", "").strip()
    or "Xqn2nnO41/L92o1iuXhSLHTbXvY4Z5ZZ62m8mSLA"
)

V3_SIGNATURE_BODY_MAX: int = 102_400
V3_RETRY_CODES: frozenset[int] = frozenset({403, 407, 429, 500, 502, 503, 504})

REQUEST_TIMEOUT: float = 25.0

# ── Catalog tab IDs (H5 subject/filter) ───────────────────────────────────────
class TabID(IntEnum):
    MOVIE = 2
    TV = 5
    ANIMATION = 8


# ── Region presets ────────────────────────────────────────────────────────────
# sp_code = MCC+MNC (mobile carrier code). The API uses this + locale/timezone
# to decide which dubs / catalog region to serve.
#
#   51010 = Telkomsel Indonesia  → Indonesian content
#   40401 = Airtel India         → Hindi content (default in movie-box-dl)
REGION_PRESETS: dict[str, dict] = {
    "ID": {
        "locale": "id_ID",
        "language": "id",
        "country": "ID",
        "timezone": "Asia/Jakarta",
        "sp_code": "51010",
        "accept_language": "id-ID,id;q=0.9,en;q=0.5",
        "referer_path": "/id",
        "system_language": "id",
        "region": "ID",
    },
    "IN": {
        "locale": "en_IN",
        "language": "en",
        "country": "IN",
        "timezone": "Asia/Kolkata",
        "sp_code": "40401",
        "accept_language": "en-IN,en;q=0.9",
        "referer_path": "/in",
        "system_language": "en",
        "region": "IN",
    },
    "US": {
        "locale": "en_US",
        "language": "en",
        "country": "US",
        "timezone": "America/New_York",
        "sp_code": "310260",
        "accept_language": "en-US,en;q=0.9",
        "referer_path": "/us",
        "system_language": "en",
        "region": "US",
    },
}

# ── Device fingerprint pool ───────────────────────────────────────────────────
# These are NOT mirrors. V3 API expects an Android app User-Agent + X-Client-Info
# that looks like the official "com.community.oneroom" app. We randomize from a
# small pool of real Redmi device models so requests look like normal mobile
# clients and are less likely to be rate-limited as bots.
_ANDROID_VERSIONS = [
    {"version": "9", "build": "PQ3A.190605.03081104"},
    {"version": "10", "build": "QP1A.191005.007.A3"},
    {"version": "11", "build": "RP1A.200720.011"},
    {"version": "12", "build": "S1B.220414.015"},
    {"version": "13", "build": "TQ2A.230405.003"},
]
_REDMI_DEVICES = [
    {"model": "23078RKD5C", "brand": "Redmi"},
    {"model": "2201117TY", "brand": "Redmi"},
    {"model": "2201117TG", "brand": "Redmi"},
    {"model": "22101316G", "brand": "Redmi"},
    {"model": "M2012K11AG", "brand": "Redmi"},
]
_VERSION_CODES = [50020042, 50020043, 50020044, 50020045, 50020046]


def generate_v3_client_identity(region: str = "ID") -> tuple[str, str]:
    """
    Build a (User-Agent, X-Client-Info) pair that spoofs the official Android app.

    The Redmi models are device fingerprints only — they do not affect which
    CDN/mirror serves the video. Region/sp_code is what controls content locale.
    """
    preset = REGION_PRESETS.get(region.upper(), REGION_PRESETS["ID"])
    android = random.choice(_ANDROID_VERSIONS)
    device = random.choice(_REDMI_DEVICES)
    vc = random.choice(_VERSION_CODES)
    gaid = str(uuid.uuid4())
    did = "".join(random.choices("0123456789abcdef", k=32))
    net = random.choice(["NETWORK_WIFI", "NETWORK_MOBILE"])

    user_agent = (
        f"com.community.oneroom/{vc} "
        f"(Linux; U; Android {android['version']}; {preset['locale']}; "
        f"{device['model']}; Build/{android['build']}; Cronet/135.0.7012.3)"
    )
    client_info = (
        f'{{"package_name":"com.community.oneroom","version_name":"3.0.03.0529.03",'
        f'"version_code":{vc},"os":"android","os_version":"{android["version"]}",'
        f'"install_ch":"ps","device_id":"{did}","install_store":"ps",'
        f'"gaid":"{gaid}","brand":"{device["brand"]}","model":"{device["model"]}",'
        f'"system_language":"{preset["system_language"]}","net":"{net}",'
        f'"region":"{preset["region"]}","timezone":"{preset["timezone"]}",'
        f'"sp_code":"{preset["sp_code"]}","X-Play-Mode":"2"}}'
    )
    return user_agent, client_info


def build_h5_headers(
    region: str = "ID",
    host: str = H5_HOST,
    extra: Optional[dict] = None,
) -> dict:
    """Default headers for H5 (web) API requests."""
    preset = REGION_PRESETS.get(region.upper(), REGION_PRESETS["ID"])
    headers = {
        "User-Agent": (
            f"Mozilla/5.0 (Linux; Android 13; {preset['locale']}; Redmi Note 12) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Mobile Safari/537.36"
        ),
        "Referer": f"https://{host}{preset['referer_path']}",
        "Origin": f"https://{host}",
        "X-Client-Info": (
            f'{{"timezone":"{preset["timezone"]}","locale":"{preset["locale"]}",'
            f'"country":"{preset["country"]}","language":"{preset["language"]}",'
            f'"sp_code":"{preset["sp_code"]}"}}'
        ),
        "X-Request-Lang": preset["language"],
        "Accept-Language": preset["accept_language"],
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    if extra:
        headers.update(extra)
    return headers


RES_LABELS: dict[int, str] = {
    360: "360p",
    480: "480p",
    720: "720p",
    1080: "1080p",
    1440: "1440p",
    2160: "4K",
}

LANG_LABELS: dict[str, str] = {
    "id": "ID",
    "in": "ID",
    "ms": "Melayu",
    "ind": "ID",
    "in_id": "ID",
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
