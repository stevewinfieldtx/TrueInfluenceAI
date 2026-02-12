"""Quick fix: recalculate timeline from existing analytics_report using published_at dates."""
import json
from pathlib import Path
from collections import defaultdict

BUNDLE_DIR = Path(r"C:\Users\steve\Documents\TrueInfluenceAI\bundles")

def find_latest_bundle():
    bundles = sorted(BUNDLE_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for b in bundles:
        if (b / 'ready.flag').exists():
            return b
    return None

bp = find_latest_bundle()
print(f"Bundle: {bp.name}")

with open(bp / 'sources.json') as f:
    sources = json.load(f)
with open(bp / 'analytics_report.json') as f:
    report = json.load(f)

source_map = {s['source_id']: s for s in sources}
video_topics = report['video_topics']

# Sort videos by published_at date (newest first)
sorted_vids = sorted(
    source_map.keys(),
    key=lambda vid: source_map[vid].get('published_at', '') or '',
    reverse=True
)
vid_rank = {vid: idx for idx, vid in enumerate(sorted_vids)}

total = len(sorted_vids)
third = max(total // 3, 1)

print(f"Total videos: {total}, third = {third}")
print(f"Recent: rank 0-{third-1} ({sorted_vids[0] if sorted_vids else '?'} to {sorted_vids[third-1] if len(sorted_vids)>=third else '?'})")
print(f"Middle: rank {third}-{third*2-1}")
print(f"Older:  rank {third*2}+")

# Show date ranges
for label, start, end in [('Recent', 0, third-1), ('Middle', third, third*2-1), ('Older', third*2, total-1)]:
    if start < total and end < total:
        d1 = source_map.get(sorted_vids[start], {}).get('published_at', '?')
        d2 = source_map.get(sorted_vids[min(end, total-1)], {}).get('published_at', '?')
        print(f"  {label}: {d1[:10]} to {d2[:10]}")

topic_by_era = defaultdict(lambda: {'recent': 0, 'middle': 0, 'older': 0})

for vid, topics in video_topics.items():
    rank = vid_rank.get(vid, 0)
    if rank < third:
        era = 'recent'
    elif rank < third * 2:
        era = 'middle'
    else:
        era = 'older'
    for t in topics:
        t_clean = t.strip().title()
        topic_by_era[t_clean][era] += 1

# Patch the report
report['topic_timeline'] = {t: dict(eras) for t, eras in topic_by_era.items()}

with open(bp / 'analytics_report.json', 'w') as f:
    json.dump(report, f, indent=2)

print("\nFixed timeline:")
for topic, eras in sorted(topic_by_era.items(), key=lambda x: x[1]['recent']+x[1]['middle']+x[1]['older'], reverse=True)[:15]:
    print(f"  {topic:<30} R={eras['recent']}  M={eras['middle']}  O={eras['older']}")

print("\n[OK] analytics_report.json patched")
