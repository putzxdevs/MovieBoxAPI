"""
Basic usage example for MovieBoxAPI.

This script demonstrates the main features:
  - Home page
  - Movie browsing
  - Search
  - Detail
  - Dubs & audio language switching
  - Stream
"""

from movieboxapi import MovieBoxClient

# ── Initialize client ──────────────────────────────────────────────────────────
# region: "ID" (Indonesia), "IN" (India), "US", etc.
# proxy: "socks5://127.0.0.1:40000" (optional, for geo-blocked servers)
client = MovieBoxClient(region="ID")


def show_home():
    """Fetch and display homepage sections."""
    print("=" * 60)
    print("📺 HOMEPAGE")
    print("=" * 60)
    sections = client.get_home()
    for section in sections:
        count = len(section.items)
        print(f"\n  [{section.type.upper()}] {section.name} — {count} items")
        for item in section.items[:3]:
            print(f"    • {item.title} (⭐ {item.rating or 'N/A'})")
        if count > 3:
            print(f"    ... and {count - 3} more")


def show_movies():
    """Browse and display movie catalog."""
    print("\n" + "=" * 60)
    print("🎬 MOVIES (Page 1)")
    print("=" * 60)
    catalog = client.get_movies(page=1, sort="RECOMMEND")
    print(f"  Total: {catalog.total} | Pages: {catalog.total_page}")
    for item in catalog.items[:10]:
        year = f" ({item.year})" if item.year else ""
        print(f"  • {item.title}{year} — ⭐ {item.rating or 'N/A'}")


def show_search(query: str = "avengers"):
    """Search for a title."""
    print("\n" + "=" * 60)
    print(f"🔍 SEARCH: '{query}'")
    print("=" * 60)
    results = client.search(query)
    print(f"  Found {results.total} results")
    for item in results.items[:5]:
        year = f" ({item.year})" if item.year else ""
        print(f"  • {item.title}{year} — ID: {item.subject_id}")


def show_detail(slug: str):
    """Fetch and display full metadata."""
    print("\n" + "=" * 60)
    print(f"📄 DETAIL: {slug}")
    print("=" * 60)
    detail = client.get_detail(slug)
    print(f"  Title    : {detail.title}")
    print(f"  Year     : {detail.year}")
    print(f"  Rating   : ⭐ {detail.rating or 'N/A'}")
    print(f"  Duration : {detail.duration or 'N/A'}")
    print(f"  Country  : {detail.country or 'N/A'}")
    print(f"  Genres   : {', '.join(detail.genres) or 'N/A'}")
    print(f"  Synopsis : {detail.synopsis[:150]}...")
    print(f"  Seasons  : {len(detail.seasons)}")
    print(f"  Episodes : {detail.total_episodes}")
    print(f"  Cast     : {', '.join(c.name for c in detail.cast[:5]) or 'N/A'}")
    if detail.trailer:
        print(f"  Trailer  : {detail.trailer.url}")

    # Show dubs
    if detail.dubs:
        dubs = [d for d in detail.dubs if d.type == 0]
        subs = [d for d in detail.dubs if d.type == 1]
        if dubs:
            print(f"  Dubs ({len(dubs)}):")
            for d in dubs:
                marker = " [ORIGINAL]" if d.original else ""
                print(f"    • {d.lan_code}: {d.lan_name} (subjectId={d.subject_id}){marker}")
        if subs:
            print(f"  Subs ({len(subs)}):")
            for d in subs:
                print(f"    • {d.lan_code}: {d.lan_name} (subjectId={d.subject_id})")

    return detail


def show_dub_stream(detail):
    """Demonstrate dub switching — each dub has a different subject_id."""
    dubs = [d for d in detail.dubs if d.type == 0]
    if len(dubs) < 2:
        print("\n  Not enough dubs to demo switching.")
        return

    print("\n" + "=" * 60)
    print("🔊 DUB SWITCHING DEMO")
    print("=" * 60)

    # Original audio
    print(f"\n  ▶ Original: {dubs[0].lan_name} (subjectId={dubs[0].subject_id})")
    stream_orig = client.get_stream(subject_id=detail.subject_id, se=1, ep=1)
    print(f"    URL: {stream_orig.url[:80]}...")

    # Pick a different dub
    alt = dubs[1]
    print(f"\n  ▶ Alternative: {alt.lan_name} (subjectId={alt.subject_id})")
    stream_alt = client.get_stream(subject_id=alt.subject_id, se=1, ep=1)
    print(f"    URL: {stream_alt.url[:80]}...")
    print(f"    Same URL? {stream_orig.url == stream_alt.url}")


def show_stream(subject_id: str):
    """Fetch and display stream info."""
    print("\n" + "=" * 60)
    print(f"▶️  STREAM: subject_id={subject_id}")
    print("=" * 60)
    stream = client.get_stream(subject_id=subject_id, se=1, ep=1, resolution=1080)
    print(f"  Video URL   : {stream.url[:120]}...")
    print(f"  Subtitle    : {stream.subtitle_url[:120] if stream.subtitle_url else 'None'}...")
    print(f"  Resource ID : {stream.resource_id}")
    print("  Qualities:")
    for q in stream.qualities:
        marker = " ← current" if q.current else ""
        print(f"    • {q.label}{marker}")
    print("  Subtitles:")
    for s in stream.subtitles:
        print(f"    • [{s.lang}] {s.label}")


if __name__ == "__main__":
    show_home()
    show_movies()
    show_search("interstellar")

    # Detail — use a slug from search results or known slug
    results = client.search("interstellar")
    if results.items:
        detail = show_detail(results.items[0].detail_path)
        show_stream(detail.subject_id)

    # Dub switching demo — Avatar has many dubs
    print("\n\n")
    avatar_results = client.search("Avatar The Last Airbender")
    if avatar_results.items:
        avatar_detail = show_detail(avatar_results.items[0].detail_path)
        show_dub_stream(avatar_detail)
