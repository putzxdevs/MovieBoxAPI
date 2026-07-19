# MovieBoxAPI

Unofficial Python client library for the **MovieBox** streaming platform.

MovieBox (powered by [aoneroom](https://aoneroom.com)) serves movies, TV series, and animations across multiple regions. This library wraps both the **H5 web API** (catalog/search/detail) and the **V3 mobile API** (signed streaming/subtitles) into a single, easy-to-use Python package.

> **⚠️ Disclaimer:** This is an unofficial, community-built library for educational and research purposes. It is not affiliated with, endorsed by, or connected to MovieBox or aoneroom in any way. Use at your own risk and respect the platform's Terms of Service.

---

## Features

- 🏠 **Homepage** — fetch banner, featured movies, TV series, animations, live sports
- 🎬 **Catalog browsing** — movies, TV series, animation with pagination and filters
- 🔍 **Search** — keyword search with pagination
- 📄 **Detail** — full metadata (cast, genres, seasons, episodes, trailer, dubs, ratings)
- ▶️ **Streaming** — playable video URLs with multi-quality and subtitle support
- 🌍 **Multi-region** — Indonesia (ID), India (IN), US, and more
- 🔐 **HMAC-MD5 signed requests** — full V3 mobile API signing implementation
- 📱 **Device fingerprint spoofing** — randomized Android device identities
- 🔄 **Host-pool failover** — automatic failover across multiple API hosts
- 🧦 **Proxy support** — SOCKS5/HTTP proxy for geo-blocked servers

---

## Architecture

```
MovieBoxAPI/
├── src/movieboxapi/
│   ├── __init__.py      # Public API exports
│   ├── client.py        # MovieBoxClient — main entry point
│   ├── constants.py     # API hosts, paths, region presets, device fingerprints
│   ├── crypto.py        # HMAC-MD5 signing, client tokens
│   ├── exceptions.py    # Custom exception hierarchy
│   ├── models.py        # Dataclasses (MediaItem, StreamResult, etc.)
│   └── utils.py         # Slug encoding, genre parsing, duration formatting
├── examples/
│   └── basic_usage.py   # Full usage demo
├── pyproject.toml       # Build config (hatchling)
├── LICENSE              # MIT
└── README.md
```

### Two API Layers

| Layer | Host | Auth | Purpose |
|-------|------|------|---------|
| **H5 (web)** | `h5-api.aoneroom.com` | Bearer token from `x-user` header | Home, catalog, search, detail metadata |
| **V3 (mobile)** | `api3-8.aoneroom.com` (+ SG variants) | HMAC-MD5 signed headers + Bearer | Streaming URLs, subtitles |

The client automatically manages tokens for both layers. V3 requests are signed with HMAC-MD5 using a canonical string (method, URL, body hash, timestamp) and the host pool provides automatic failover.

---

## Installation

```bash
git clone https://github.com/putzxdevs/MovieBoxAPI.git
cd MovieBoxAPI
pip install -e .
```

### Requirements

- Python ≥ 3.10
- [httpx[socks]](https://github.com/encode/httpx) ≥ 0.27.0

---

## Quick Start

```python
from movieboxapi import MovieBoxClient

# Initialize client (region: ID=Indonesia, IN=India, US=United States)
client = MovieBoxClient(region="ID")

# Optional: SOCKS5 proxy for geo-blocked servers
# client = MovieBoxClient(region="ID", proxy="socks5://127.0.0.1:40000")
```

### Homepage

```python
sections = client.get_home()
for section in sections:
    print(f"[{section.type}] {section.name}")
    for item in section.items[:5]:
        print(f"  • {item.title} (⭐ {item.rating or 'N/A'})")
```

### Browse Catalog

```python
# Movies
movies = client.get_movies(page=1, sort="RECOMMEND")
print(f"Total: {movies.total} movies, Page {movies.page}/{movies.total_page}")
for item in movies.items:
    print(f"  {item.title} ({item.year}) — ⭐ {item.rating}")

# TV Series
tv = client.get_tv_series(page=1)

# Animation
anime = client.get_animation(page=1)
```

### Search

```python
results = client.search("interstellar")
print(f"Found {results.total} results")
for item in results.items:
    print(f"  {item.title} — ID: {item.subject_id}")
```

### Detail

```python
detail = client.get_detail("/id/movie/interstellar-abc123")
print(f"Title    : {detail.title}")
print(f"Year     : {detail.year}")
print(f"Rating   : ⭐ {detail.rating}")
print(f"Genres   : {', '.join(detail.genres)}")
print(f"Synopsis : {detail.synopsis[:200]}")
print(f"Seasons  : {len(detail.seasons)}")
print(f"Episodes : {detail.total_episodes}")
print(f"Cast     : {', '.join(c.name for c in detail.cast[:5])}")

if detail.trailer:
    print(f"Trailer  : {detail.trailer.url}")
```

### Dubs & Audio Languages

Each dubbing language has its **own `subject_id`**. Use the `Dub` objects from
`detail.dubs` to switch audio languages:

```python
detail = client.get_detail("/id/tv/avatar-the-last-airbender-abc123")

# List available dubs
dubs = [d for d in detail.dubs if d.type == 0]   # type=0 → audio dub
subs = [d for d in detail.dubs if d.type == 1]    # type=1 → subtitle-only

for dub in dubs:
    marker = " (original)" if dub.original else ""
    print(f"  {dub.lan_code}: {dub.lan_name} — subjectId={dub.subject_id}{marker}")

# Stream original audio
stream = client.get_stream(subject_id=detail.subject_id, se=1, ep=1)

# Stream Indonesian dub (pass the dub's subject_id)
indonesian = next(d for d in dubs if d.lan_code == "id")
stream_id = client.get_stream(subject_id=indonesian.subject_id, se=1, ep=1)
print(stream_id.url)  # Different URL → different audio track
```

### Stream

```python
stream = client.get_stream(
    subject_id="12345",
    se=1,          # Season
    ep=1,          # Episode
    resolution=1080,
)
print(f"Video URL : {stream.url}")
print(f"Subtitle  : {stream.subtitle_url}")

# Available qualities
for q in stream.qualities:
    marker = " ← current" if q.current else ""
    print(f"  {q.label}{marker}")

# Available subtitles
for s in stream.subtitles:
    print(f"  [{s.lang}] {s.label} — {s.url}")
```

### Shorthand: Get Stream URL Only

```python
url = client.get_stream_url(subject_id="12345", se=1, ep=1, resolution=1080)
print(url)  # Direct .m3u8 URL
```

---

## Models

All models are `dataclasses` — no pydantic dependency. Convert to dict with `.to_dict()` or `dataclasses.asdict()`.

| Model | Description |
|-------|-------------|
| `MediaItem` | Catalog/search card (title, poster, rating, year) |
| `MediaDetail` | Full metadata (cast, seasons, episodes, dubs, trailer) |
| `StreamResult` | Playable stream (URL, qualities, subtitles) |
| `CatalogPage` | Paginated catalog response |
| `SearchResult` | Paginated search response |
| `HomeSection` | Homepage section (banner, featured, etc.) |
| `Quality` | Video quality option (360p–4K) |
| `Subtitle` | Subtitle track (lang, label, URL) |
| `Season` / `Episode` | Season and episode numbers |
| `CastMember` | Cast/crew member (Director, Actor, Writer) |
| `Dub` | Audio dub / subtitle variant (each has its own `subject_id`) |
| `Trailer` | Trailer video info |

---

## Exceptions

| Exception | When |
|-----------|------|
| `MovieBoxError` | Base exception for all errors |
| `APIError` | API returns an error response |
| `RateLimitError` | 429 Too Many Requests |
| `GeoBlockError` | 403 Geo-blocked / IP blocked |
| `StreamError` | No playable stream URL available |
| `TokenError` | Cannot acquire auth token |

```python
from movieboxapi import MovieBoxClient, GeoBlockError, StreamError

client = MovieBoxClient(region="ID", proxy="socks5://127.0.0.1:40000")
try:
    stream = client.get_stream(subject_id="12345", se=1, ep=1)
except GeoBlockError:
    print("Need a proxy for this region")
except StreamError as e:
    print(f"No stream available: {e}")
```

---

## Configuration

### Regions

Built-in presets: `ID` (Indonesia), `IN` (India), `US` (United States).

Each preset controls: locale, timezone, carrier code (`sp_code`), language, and content region.

### Proxy

If your server IP is geo-blocked, pass a proxy:

```python
client = MovieBoxClient(
    region="ID",
    proxy="socks5://127.0.0.1:40000",  # WARP, V2Ray, etc.
)
```

### HMAC Secret Rotation

V3 signing keys can be overridden via environment variables:

```bash
export MOVIEBOX_SECRET_KEY_DEFAULT="your_key_here"
export MOVIEBOX_SECRET_KEY_ALT="your_alt_key_here"
```

### Custom Timeout

```python
client = MovieBoxClient(region="ID", timeout=30.0)
```

---

## API Reference (Low-Level)

For advanced usage, you can access the signing and header utilities directly:

```python
from movieboxapi import (
    build_signed_headers,
    client_token,
    signature,
    build_h5_headers,
    generate_v3_client_identity,
)

# Generate V3 device identity
ua, ci = generate_v3_client_identity("ID")

# Build signed headers for custom V3 requests
headers = build_signed_headers(
    "GET",
    "https://api6.aoneroom.com/wefeed-mobile-bff/subject-api/resource?subjectId=123",
    client_info=ci,
    user_agent=ua,
)

# Client token
ct = client_token()  # "<timestamp>,<md5(reverse(timestamp))>"

# HMAC-MD5 signature
sig = signature("GET", "application/json", "application/json", url)
```

---

## How It Works

### Why Redmi Devices?

The V3 mobile API expects requests from the official Android app (`com.community.oneroom`). The library generates randomized **device fingerprints** using Redmi phone models. These are NOT mirrors or proxies — they are spoofed `User-Agent` and `X-Client-Info` headers that make requests look like they come from a real phone. This is necessary because the API rejects requests that don't match the expected app signature.

### Host Pool Failover

The V3 API has multiple backend hosts (`api3-8.aoneroom.com` + Singapore variants). If one host returns 403, 429, or 5xx, the client automatically tries the next host in the pool. This provides resilience against individual host failures or rate limiting.

### Request Signing

Every V3 request is signed with HMAC-MD5:
1. Build a canonical string: `METHOD\nAccept\nContent-Type\nBodyLength\nTimestamp\nBodyHash\nCanonicalURL`
2. HMAC-MD5 the canonical string with the shared secret (base64-decoded)
3. Encode the MAC as base64
4. Header: `x-tr-signature: "<timestamp>|2|<base64_mac>"`

---

## Development

```bash
# Clone
git clone https://github.com/putzxdevs/MovieBoxAPI.git
cd MovieBoxAPI

# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/

# Type check
mypy src/
```

---

## Related Projects

- [putzx-tv](https://github.com/Putzx/putzx-tv) — Web app that uses MovieBoxAPI for movie/TV streaming

## License

[MIT](LICENSE) © Putzx
