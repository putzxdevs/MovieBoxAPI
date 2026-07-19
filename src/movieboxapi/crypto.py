"""
V3 request signing: HMAC-MD5, client token, signed headers.

The mobile API rejects unsigned requests. Every V3 call needs:

  X-Client-Token  = "<ts>,<md5(reverse(ts))>"
  x-tr-signature  = "<ts>|2|<base64(hmac-md5(canonical, secret))>"
  X-Client-Info   = JSON device fingerprint
  Authorization   = Bearer <token>   (after bootstrap)
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import time
from typing import Optional
from urllib.parse import parse_qs, urlparse

from .constants import V3_SECRET_ALT, V3_SECRET_DEFAULT, V3_SIGNATURE_BODY_MAX


def md5_hex(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


def b64_decode(value: str) -> bytes:
    padding = (4 - len(value) % 4) % 4
    return base64.b64decode(value + "=" * padding)


def b64_encode(data: bytes) -> str:
    return base64.b64encode(data).decode()


def client_token(timestamp_ms: Optional[int] = None) -> str:
    """``X-Client-Token`` = ``"<ts>,<md5(reverse(ts))>"``."""
    ts = str(timestamp_ms if timestamp_ms is not None else int(time.time() * 1000))
    return f"{ts},{md5_hex(ts[::-1].encode())}"


def _sorted_query_string(url: str) -> str:
    parsed = urlparse(url)
    qs = parse_qs(parsed.query, keep_blank_values=True)
    if not qs:
        return ""
    parts: list[str] = []
    for key in sorted(qs.keys()):
        for value in qs[key]:
            parts.append(f"{key}={value}")
    return "&".join(parts)


def canonical_string(
    method: str,
    accept: Optional[str],
    content_type: Optional[str],
    url: str,
    body: Optional[str],
    timestamp_ms: int,
) -> str:
    parsed = urlparse(url)
    path = parsed.path or ""
    query = _sorted_query_string(url)
    canonical_url = f"{path}?{query}" if query else path

    if body is not None:
        body_bytes = body.encode("utf-8")
        body_hash = md5_hex(body_bytes[:V3_SIGNATURE_BODY_MAX])
        body_length = str(len(body_bytes))
    else:
        body_hash = ""
        body_length = ""

    return (
        f"{method.upper()}\n"
        f"{accept or ''}\n"
        f"{content_type or ''}\n"
        f"{body_length}\n"
        f"{timestamp_ms}\n"
        f"{body_hash}\n"
        f"{canonical_url}"
    )


def signature(
    method: str,
    accept: Optional[str],
    content_type: Optional[str],
    url: str,
    body: Optional[str] = None,
    use_alt_key: bool = False,
    timestamp_ms: Optional[int] = None,
) -> str:
    """
    ``x-tr-signature`` value:
    ``"<ts>|2|<base64(hmac-md5(canonical, secret))>"``
    """
    ts = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
    canonical = canonical_string(method, accept, content_type, url, body, ts)
    secret_b64 = V3_SECRET_ALT if use_alt_key else V3_SECRET_DEFAULT
    mac = hmac.new(b64_decode(secret_b64), canonical.encode("utf-8"), hashlib.md5)
    return f"{ts}|2|{b64_encode(mac.digest())}"


def build_signed_headers(
    method: str,
    url: str,
    *,
    accept: str = "application/json",
    content_type: str = "application/json",
    body: Optional[str] = None,
    include_play_mode: bool = False,
    auth_token: Optional[str] = None,
    client_info: str = "",
    user_agent: str = "",
) -> dict[str, str]:
    """Full set of signed headers for a V3 mobile API request."""
    ts = int(time.time() * 1000)
    headers: dict[str, str] = {
        "User-Agent": user_agent,
        "Accept": accept,
        "Content-Type": content_type,
        "Connection": "keep-alive",
        "X-Client-Token": client_token(ts),
        "x-tr-signature": signature(
            method, accept, content_type, url, body, False, ts
        ),
        "X-Client-Info": client_info,
        "X-Client-Status": "0",
    }
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    if include_play_mode:
        headers["X-Play-Mode"] = "2"
    return headers
