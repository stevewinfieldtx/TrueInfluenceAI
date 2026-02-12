"""
TrueInfluenceAI - Bundle Enrichment with YouTube Data API
==========================================================
Enriches existing bundles with REAL performance data:
  - View counts, like counts, comment counts per video
  - Top comments per video (audience sentiment)
  - Channel-wide averages for comparison
  - Exact publish dates

Usage:
  py enrich.py                          (latest bundle)
  py enrich.py SunnyLenarduzzi_20260211_164612
"""

import sys, os, json, time
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
import requests
from pathlib import Path
from collections import defaultdict

SCRIPT_DIR = Path(__file__).parent
_LOG = open(SCRIPT_DIR / '_enrich_log.txt', 'w', encoding='utf-8')
def log(msg):
    print(msg)
    _LOG.write(msg + '\n')
    _LOG.flush()

from dotenv import load_dotenv
load_dotenv(Path(r"C:\Users\steve\Documents\.env"))
load_dotenv(Path(r"C:\Users\steve\Documents\TruePlatformAI\.env"))

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
BUNDLE_DIR = Path(r"C:\Users\steve\Documents\TrueInfluenceAI\bundles")


def find_latest_bundle():
    bundles = sorted(BUNDLE_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for b in bundles:
        if (b / 'ready.flag').exists():
            return b
    return None


def get_video_stats(video_ids):
    stats = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i+50]
        ids_str = ','.join(batch)
        url = 'https://www.googleapis.com/youtube/v3/videos'
        params = {'part': 'statistics,snippet', 'id': ids_str, 'key': YOUTUBE_API_KEY}
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 403:
                log(f"  [ERROR] API 403 Forbidden.")
                log(f"  Your YouTube Data API v3 may not be enabled.")
                log(f"  Go to: https://console.cloud.google.com/apis/library/youtube.googleapis.com")
                log(f"  Response: {resp.text[:300]}")
                return None
            if resp.status_code != 200:
                log(f"  [WARN] API error {resp.status_code}: {resp.text[:200]}")
                continue
            data = resp.json()
            for item in data.get('items', []):
                vid = item['id']
                s = item.get('statistics', {})
                snip = item.get('snippet', {})
                stats[vid] = {
                    'views': int(s.get('viewCount', 0)),
                    'likes': int(s.get('likeCount', 0)),
                    'comments': int(s.get('commentCount', 0)),
                    'published_at': snip.get('publishedAt', ''),
                    'description': snip.get('description', '')[:500],
                    'tags': snip.get('tags', [])[:15],
                }
            log(f"  {min(i+50, len(video_ids))}/{len(video_ids)} video stats fetched")
        except Exception as e:
            log(f"  [WARN] Error: {e}")
    return stats


def get_video_comments(video_id, max_comments=20):
    url = 'https://www.googleapis.com/youtube/v3/commentThreads'
    params = {
        'part': 'snippet', 'videoId': video_id, 'maxResults': max_comments,
        'order': 'relevance', 'textFormat': 'plainText', 'key': YOUTUBE_API_KEY,
    }
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code != 200:
            return []
        data = resp.json()
        comments = []
        for item in data.get('items', []):
            snip = item['snippet']['topLevelComment']['snippet']
            comments.append({
                'text': snip.get('textDisplay', '')[:500],
                'likes': snip.get('likeCount', 0),
                'author': snip.get('authorDisplayName', ''),
            })
        return comments
    except Exception:
        return []


def enrich_bundle(bundle_path):
    bundle_path = Path(bundle_path)
    with open(bundle_path / 'sources.json') as f:
        sources = json.load(f)

    video_ids = [s['source_id'] for s in sources]
    log(f"\n[STATS] Fetching stats for {len(video_ids)} videos...")
    stats = get_video_stats(video_ids)

    if stats is None:
        return False
    if not stats:
        log("  [ERROR] No stats returned. Check API key.")
        return False

    all_views = [s['views'] for s in stats.values() if s['views'] > 0]
    all_likes = [s['likes'] for s in stats.values() if s['likes'] > 0]
    all_comments = [s['comments'] for s in stats.values() if s['comments'] > 0]

    channel_avg_views = int(sum(all_views) / len(all_views)) if all_views else 0
    channel_avg_likes = int(sum(all_likes) / len(all_likes)) if all_likes else 0
    channel_avg_comments = int(sum(all_comments) / len(all_comments)) if all_comments else 0

    total_eng = sum(s['likes'] + s['comments'] for s in stats.values())
    total_views = sum(s['views'] for s in stats.values())
    avg_engagement_rate = (total_eng / total_views * 100) if total_views > 0 else 0

    log(f"\n  Channel Averages:")
    log(f"     Views:    {channel_avg_views:,}")
    log(f"     Likes:    {channel_avg_likes:,}")
    log(f"     Comments: {channel_avg_comments:,}")
    log(f"     Engagement Rate: {avg_engagement_rate:.2f}%")

    for source in sources:
        vid = source['source_id']
        if vid in stats:
            source['views'] = stats[vid]['views']
            source['likes'] = stats[vid]['likes']
            source['comment_count'] = stats[vid]['comments']
            source['published_at'] = stats[vid]['published_at']
            source['tags'] = stats[vid]['tags']
            source['engagement_rate'] = round(
                ((stats[vid]['likes'] + stats[vid]['comments']) / stats[vid]['views'] * 100)
                if stats[vid]['views'] > 0 else 0, 2
            )

    log(f"\n[COMMENTS] Fetching comments...")
    sorted_by_comments = sorted(
        [(s['source_id'], stats.get(s['source_id'], {}).get('comments', 0)) for s in sources],
        key=lambda x: x[1], reverse=True
    )

    all_comments_data = {}
    fetch_count = min(20, len(sorted_by_comments))
    for i, (vid, count) in enumerate(sorted_by_comments[:fetch_count]):
        if count == 0:
            continue
        comments = get_video_comments(vid)
        if comments:
            all_comments_data[vid] = comments
        if (i + 1) % 5 == 0:
            log(f"  {i+1}/{fetch_count} videos comments fetched")
            time.sleep(0.5)

    log(f"  Got comments for {len(all_comments_data)} videos")

    with open(bundle_path / 'sources.json', 'w') as f:
        json.dump(sources, f, indent=2)
    with open(bundle_path / 'comments.json', 'w') as f:
        json.dump(all_comments_data, f, indent=2)

    metrics = {
        'channel_avg_views': channel_avg_views,
        'channel_avg_likes': channel_avg_likes,
        'channel_avg_comments': channel_avg_comments,
        'channel_engagement_rate': round(avg_engagement_rate, 2),
        'total_videos': len(video_ids),
        'total_views': total_views,
        'enriched_at': time.strftime('%Y-%m-%dT%H:%M:%S'),
    }
    with open(bundle_path / 'channel_metrics.json', 'w') as f:
        json.dump(metrics, f, indent=2)

    sorted_sources = sorted(sources, key=lambda x: x.get('views', 0), reverse=True)
    log(f"\n  Top 5 Videos by Views:")
    for s in sorted_sources[:5]:
        ratio = s.get('views', 0) / channel_avg_views if channel_avg_views > 0 else 0
        log(f"     {s.get('views',0):>10,} views ({ratio:.1f}x avg)  {s['title'][:60]}")

    log(f"\n  Most Discussed (by comment count):")
    sorted_cmt = sorted(sources, key=lambda x: x.get('comment_count', 0), reverse=True)
    for s in sorted_cmt[:5]:
        log(f"     {s.get('comment_count',0):>6,} comments  {s['title'][:60]}")

    log(f"\n  Lowest Performers:")
    for s in sorted_sources[-3:]:
        ratio = s.get('views', 0) / channel_avg_views if channel_avg_views > 0 else 0
        log(f"     {s.get('views',0):>10,} views ({ratio:.1f}x avg)  {s['title'][:60]}")

    return True


def main():
    if not YOUTUBE_API_KEY:
        log("[ERROR] No YOUTUBE_API_KEY found in .env")
        sys.exit(1)

    log(f"[KEY] YouTube API Key: {YOUTUBE_API_KEY[:8]}...{YOUTUBE_API_KEY[-4:]}")

    if len(sys.argv) > 1:
        bp = Path(sys.argv[1])
        if not bp.is_absolute():
            bp = BUNDLE_DIR / bp
    else:
        bp = find_latest_bundle()

    if not bp or not bp.exists():
        log("[ERROR] No bundle found.")
        sys.exit(1)

    log(f"[BUNDLE] Enriching: {bp.name}")
    success = enrich_bundle(bp)

    if success:
        log(f"\n[DONE] Bundle enriched! Now re-run:")
        log(f"   py analytics.py {bp.name}")
        log(f"   py dashboard.py {bp.name}")
    else:
        log(f"\n[FAIL] Enrichment failed. Check API key status.")

    _LOG.close()


if __name__ == '__main__':
    main()
