"""
TrueInfluenceAI - Cloud Enrichment Pipeline
=============================================
Enriches bundles with real YouTube Data API metrics.
Cloud-ready version of enrich.py.
"""

import os, json, time
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import requests

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
YT_API = "https://www.googleapis.com/youtube/v3"


def enrich_bundle(bundle_dir):
    """Enrich a bundle with YouTube Data API stats."""
    bundle_dir = Path(bundle_dir)
    sources = json.loads((bundle_dir / "sources.json").read_text(encoding="utf-8"))

    if not YOUTUBE_API_KEY:
        print("No YOUTUBE_API_KEY set - skipping enrichment, using scraped data")
        _build_metrics_from_scraped(bundle_dir, sources)
        return

    print(f"Enriching {len(sources)} videos with YouTube Data API...")

    video_ids = [s["source_id"] for s in sources]
    stats_map = {}

    # Batch fetch (50 per request)
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        try:
            resp = requests.get(f"{YT_API}/videos", params={
                "key": YOUTUBE_API_KEY,
                "id": ",".join(batch),
                "part": "statistics,snippet,contentDetails",
            }, timeout=15)
            resp.raise_for_status()
            for item in resp.json().get("items", []):
                vid = item["id"]
                stats = item.get("statistics", {})
                snippet = item.get("snippet", {})
                stats_map[vid] = {
                    "views": int(stats.get("viewCount", 0)),
                    "likes": int(stats.get("likeCount", 0)),
                    "comments": int(stats.get("commentCount", 0)),
                    "published_at": snippet.get("publishedAt", ""),
                    "description": snippet.get("description", "")[:500],
                    "tags": snippet.get("tags", [])[:20],
                }
        except Exception as e:
            print(f"   API batch failed: {e}")

    # Top comments per video
    comments_map = {}
    for vid in video_ids[:30]:  # Limit to avoid quota
        try:
            resp = requests.get(f"{YT_API}/commentThreads", params={
                "key": YOUTUBE_API_KEY,
                "videoId": vid,
                "part": "snippet",
                "order": "relevance",
                "maxResults": 5,
            }, timeout=10)
            if resp.status_code == 200:
                items = resp.json().get("items", [])
                comments_map[vid] = [
                    {
                        "text": it["snippet"]["topLevelComment"]["snippet"]["textDisplay"][:300],
                        "likes": it["snippet"]["topLevelComment"]["snippet"].get("likeCount", 0),
                        "author": it["snippet"]["topLevelComment"]["snippet"].get("authorDisplayName", ""),
                    }
                    for it in items
                ]
        except Exception:
            pass
        time.sleep(0.1)  # Rate limit

    # Update sources
    for s in sources:
        vid = s["source_id"]
        if vid in stats_map:
            s.update(stats_map[vid])

    (bundle_dir / "sources.json").write_text(
        json.dumps(sources, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Save comments
    (bundle_dir / "comments.json").write_text(
        json.dumps(comments_map, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Build channel metrics
    _build_channel_metrics(bundle_dir, sources, stats_map)
    print(f"   Enriched {len(stats_map)} videos, {len(comments_map)} comment threads")


def _build_metrics_from_scraped(bundle_dir, sources):
    """Build basic metrics from scraped data when no API key available."""
    views = [s.get("views", 0) for s in sources if s.get("views", 0) > 0]
    metrics = {
        "total_views": sum(views),
        "channel_avg_views": int(sum(views) / len(views)) if views else 0,
        "total_videos": len(sources),
        "channel_engagement_rate": 0,
        "enriched_with_api": False,
    }
    (bundle_dir / "channel_metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )


def _build_channel_metrics(bundle_dir, sources, stats_map):
    """Calculate channel-wide metrics."""
    views = [stats_map[v]["views"] for v in stats_map if stats_map[v]["views"] > 0]
    likes = [stats_map[v]["likes"] for v in stats_map]
    comments = [stats_map[v]["comments"] for v in stats_map]

    total_views = sum(views)
    total_likes = sum(likes)
    total_comments = sum(comments)

    engagement = 0
    if total_views > 0:
        engagement = round((total_likes + total_comments) / total_views * 100, 2)

    metrics = {
        "total_views": total_views,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "channel_avg_views": int(total_views / len(views)) if views else 0,
        "channel_avg_likes": int(total_likes / len(likes)) if likes else 0,
        "channel_engagement_rate": engagement,
        "total_videos": len(sources),
        "enriched_videos": len(stats_map),
        "enriched_with_api": True,
        "enriched_at": datetime.utcnow().isoformat(),
    }

    (bundle_dir / "channel_metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
