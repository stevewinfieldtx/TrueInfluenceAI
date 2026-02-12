"""
TrueInfluenceAI - Creator Intelligence Dashboard
==================================================
Analyzes a creator's content bundle to reveal:
  - Topic clusters & frequency WITH performance data
  - Topic relationships (what goes with what)
  - Timeline trends (rising, declining, dormant topics)
  - Strategic recommendations

Usage:
  py analytics.py                          (latest bundle)
  py analytics.py SunnyLenarduzzi_20260211_164612
"""

import sys, os, json, time
import numpy as np
import requests
from pathlib import Path
from collections import Counter, defaultdict

from dotenv import load_dotenv
load_dotenv(Path(r"C:\Users\steve\Documents\.env"))
load_dotenv(Path(r"C:\Users\steve\Documents\TruePlatformAI\.env"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen/qwen3-embedding-8b")
ANALYSIS_MODEL = "google/gemini-2.5-flash-lite:online"
BUNDLE_DIR = Path(r"C:\Users\steve\Documents\TrueInfluenceAI\bundles")


def find_latest_bundle():
    bundles = sorted(BUNDLE_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for b in bundles:
        if (b / 'ready.flag').exists():
            return b
    return None


def load_bundle(bundle_path):
    bundle_path = Path(bundle_path)
    with open(bundle_path / 'manifest.json') as f:
        manifest = json.load(f)
    with open(bundle_path / 'sources.json') as f:
        sources = json.load(f)
    with open(bundle_path / 'chunks.json') as f:
        chunks = json.load(f)

    valid_chunks = [c for c in chunks if c.get('embedding')]
    embeddings = np.array([c['embedding'] for c in valid_chunks], dtype=np.float32)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embeddings = embeddings / norms

    return {
        'manifest': manifest,
        'sources': {s['source_id']: s for s in sources},
        'sources_list': sources,
        'chunks': valid_chunks,
        'embeddings': embeddings,
        'channel': manifest.get('channel', 'Unknown'),
        'bundle_path': bundle_path,
    }


# ─── Step 1: Extract topics per video via LLM ────────────────────────

def extract_topics(bundle):
    """Ask LLM to tag each video with 3-5 topics based on its chunks."""
    print("\n🏷️  Extracting topics per video...")

    video_text = defaultdict(list)
    for c in bundle['chunks']:
        video_text[c['source_id']].append(c['text'])

    video_summaries = []
    vid_order = []
    for vid, texts in video_text.items():
        title = bundle['sources'].get(vid, {}).get('title', 'Unknown')
        combined = ' '.join(texts)
        snippet = ' '.join(combined.split()[:400])
        video_summaries.append(f"VIDEO_ID: {vid}\nTITLE: {title}\nSNIPPET: {snippet}")
        vid_order.append(vid)

    all_topics = {}
    batch_size = 10

    for i in range(0, len(video_summaries), batch_size):
        batch = video_summaries[i:i + batch_size]

        prompt = f"""You are a content strategist. For each video below, extract 3-5 topic tags.
Tags should be specific but reusable across videos (e.g. "YouTube SEO", "Course Launches", 
"Email Marketing", "Content Strategy", "Mindset", "Monetization", "Social Media Growth").

Return ONLY valid JSON — a list of objects:
[
  {{"video_id": "...", "topics": ["Topic1", "Topic2", "Topic3"]}},
  ...
]

No markdown fences. Standardize similar topics to the same tag name.

VIDEOS:
{chr(10).join(batch)}"""

        try:
            resp = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={
                    'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                    'Content-Type': 'application/json',
                },
                json={
                    'model': ANALYSIS_MODEL,
                    'messages': [{"role": "user", "content": prompt}],
                    'max_tokens': 2000,
                    'temperature': 0.2,
                },
                timeout=60
            )

            if resp.status_code == 200:
                text = resp.json()['choices'][0]['message']['content'].strip()
                if text.startswith('```'):
                    text = text.split('\n', 1)[1]
                if text.endswith('```'):
                    text = text.rsplit('```', 1)[0]
                text = text.strip()

                results = json.loads(text)
                for r in results:
                    vid = r.get('video_id', '')
                    topics = r.get('topics', [])
                    if vid and topics:
                        all_topics[vid] = topics

            print(f"  {min(i + batch_size, len(video_summaries))}/{len(video_summaries)} videos tagged")
            time.sleep(1)

        except Exception as e:
            print(f"  ⚠️ Batch error: {e}")

    print(f"  ✅ Tagged {len(all_topics)}/{len(video_text)} videos")
    return all_topics


# ─── Step 2: Topic Frequency + Performance ────────────────────────────

def analyze_topic_performance(video_topics, bundle):
    """Topic frequency WITH recency-weighted average views per topic.
    Recent videos contribute more to a topic's performance score,
    reflecting current audience interest rather than historical."""
    from recency_utils import rank_sources_by_date, compute_recency_weight, weighted_average
    
    print("\n📊 Topic Performance Analysis (recency-weighted)")
    print("=" * 70)

    # Build recency weights per source
    source_ranks = rank_sources_by_date(bundle['sources_list'])
    total_sources = len(bundle['sources_list'])

    topic_counter = Counter()
    topic_views = defaultdict(list)       # (views, weight) pairs
    topic_videos = defaultdict(list)

    for vid, topics in video_topics.items():
        source = bundle['sources'].get(vid, {})
        title = source.get('title', 'Unknown')
        views = source.get('views', 0)
        position = source.get('position', 0)
        rank = source_ranks.get(vid, total_sources - 1)
        weight = compute_recency_weight(rank, total_sources)

        for t in topics:
            t_clean = t.strip().title()
            topic_counter[t_clean] += 1
            topic_views[t_clean].append((views, weight))
            topic_videos[t_clean].append({
                'title': title,
                'views': views,
                'position': position,
                'vid': vid,
                'recency_weight': weight,
            })

    # Calculate recency-weighted avg views
    topic_avg_views = {}
    for topic, vw_pairs in topic_views.items():
        views_list = [v for v, w in vw_pairs]
        weights_list = [w for v, w in vw_pairs]
        topic_avg_views[topic] = int(weighted_average(views_list, weights_list)) if vw_pairs else 0

    # Overall recency-weighted avg for comparison
    all_vw = []
    for s in bundle['sources_list']:
        v = s.get('views', 0)
        if v > 0:
            rank = source_ranks.get(s['source_id'], total_sources - 1)
            w = compute_recency_weight(rank, total_sources)
            all_vw.append((v, w))
    channel_avg = int(weighted_average([v for v, w in all_vw], [w for v, w in all_vw])) if all_vw else 0

    has_views = channel_avg > 0

    if has_views:
        print(f"\n  Channel average views: {channel_avg:,}")
        print(f"\n{'TOPIC':<30} {'VIDEOS':>6}  {'AVG VIEWS':>10}  {'vs AVG':>8}  {'PERFORMANCE':>12}")
        print("-" * 70)
        # Sort by avg views descending
        for topic, count in sorted(topic_counter.items(), key=lambda x: topic_avg_views.get(x[0], 0), reverse=True):
            avg = topic_avg_views.get(topic, 0)
            ratio = avg / channel_avg if channel_avg > 0 else 0
            indicator = "🔥" if ratio > 1.3 else ("✅" if ratio > 0.8 else "⬇️")
            bar = "█" * min(int(ratio * 5), 20)
            print(f"  {topic:<28} {count:>4}    {avg:>9,}  {ratio:>6.1f}x   {indicator} {bar}")
    else:
        # No view data — frequency only
        print(f"\n  ℹ️  No view data in this bundle. Re-ingest to capture views.")
        total = len(video_topics)
        print(f"\n{'TOPIC':<35} {'VIDEOS':>6}  {'% OF CONTENT':>12}")
        print("-" * 60)
        for topic, count in topic_counter.most_common(20):
            pct = (count / total) * 100
            bar = "█" * int(pct / 3)
            print(f"  {topic:<33} {count:>4}    {pct:>5.1f}%  {bar}")

    return topic_counter, topic_videos, topic_avg_views


# ─── Step 3: Topic Timeline (Rising / Declining / Dormant) ───────────

def analyze_topic_timeline(video_topics, bundle):
    """Analyze WHEN topics were discussed. Detect trends."""
    print("\n\n📅 Topic Timeline & Trends")
    print("=" * 70)

    # Sort all source video IDs by published_at date (newest first)
    # Fall back to position if dates unavailable
    sorted_vids = sorted(
        bundle['sources'].keys(),
        key=lambda vid: bundle['sources'][vid].get('published_at', '') or '',
        reverse=True  # newest first
    )

    # Build a rank map: vid -> position (0 = newest)
    vid_rank = {vid: idx for idx, vid in enumerate(sorted_vids)}

    total_videos = len(sorted_vids)
    third = max(total_videos // 3, 1)

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

    # Classify trends
    rising = []
    declining = []
    dormant = []
    steady = []

    for topic, eras in topic_by_era.items():
        r, m, o = eras['recent'], eras['middle'], eras['older']
        total = r + m + o

        if total < 2:
            continue

        if r > o and r > m:
            rising.append((topic, r, m, o))
        elif o > r and o > m:
            declining.append((topic, r, m, o))
        elif o > 0 and r == 0:
            dormant.append((topic, r, m, o))
        else:
            steady.append((topic, r, m, o))

    # Show publish text for context
    recent_pub = bundle['sources_list'][0].get('published_text', '?') if bundle['sources_list'] else '?'
    oldest_pub = bundle['sources_list'][-1].get('published_text', '?') if bundle['sources_list'] else '?'
    print(f"\n  Range: newest = {recent_pub}  →  oldest = {oldest_pub}")
    print(f"  Split: Recent (newest {third}) | Middle ({third}) | Older (oldest {third})")

    if rising:
        print(f"\n  🚀 RISING TOPICS (more frequent in recent content)")
        print(f"  {'Topic':<30} {'Recent':>7} {'Middle':>7} {'Older':>7}  {'Trend':>10}")
        print(f"  {'-'*65}")
        for topic, r, m, o in sorted(rising, key=lambda x: x[1], reverse=True):
            trend = "▲▲▲" if r >= o + 3 else ("▲▲" if r >= o + 2 else "▲")
            print(f"  {topic:<30} {r:>5}   {m:>5}   {o:>5}    {trend}")

    if declining:
        print(f"\n  📉 DECLINING TOPICS (less frequent in recent content)")
        print(f"  {'Topic':<30} {'Recent':>7} {'Middle':>7} {'Older':>7}")
        print(f"  {'-'*55}")
        for topic, r, m, o in sorted(declining, key=lambda x: x[3], reverse=True):
            print(f"  {topic:<30} {r:>5}   {m:>5}   {o:>5}")

    if dormant:
        print(f"\n  💤 DORMANT TOPICS (appeared before but stopped)")
        print(f"  {'Topic':<30} {'Recent':>7} {'Middle':>7} {'Older':>7}")
        print(f"  {'-'*55}")
        for topic, r, m, o in sorted(dormant, key=lambda x: x[2] + x[3], reverse=True):
            print(f"  {topic:<30} {r:>5}   {m:>5}   {o:>5}")

    if steady:
        print(f"\n  ⚖️  STEADY TOPICS (consistent across all eras)")
        for topic, r, m, o in sorted(steady, key=lambda x: sum(x[1:]), reverse=True)[:8]:
            print(f"    {topic}: {r}/{m}/{o}")

    return topic_by_era


# ─── Step 4: Topic Relationships ─────────────────────────────────────

def analyze_topic_relationships(video_topics):
    """Find which topics frequently appear together."""
    print("\n\n🔗 Topic Relationships (frequently paired)")
    print("=" * 60)

    pair_counter = Counter()
    for vid, topics in video_topics.items():
        clean = sorted(set(t.strip().title() for t in topics))
        for i in range(len(clean)):
            for j in range(i + 1, len(clean)):
                pair_counter[(clean[i], clean[j])] += 1

    print(f"\n{'TOPIC PAIR':<50} {'TIMES PAIRED':>12}")
    print("-" * 60)
    for (t1, t2), count in pair_counter.most_common(15):
        if count >= 2:
            print(f"  {t1} ↔ {t2:<35} {count:>5}")

    return pair_counter


# ─── Step 5: Embedding Clusters ──────────────────────────────────────

def cluster_topics(bundle, n_clusters=8):
    """Cluster chunks by embedding similarity."""
    print("\n\n🧩 Embedding-Based Content Clusters")
    print("=" * 60)

    try:
        from sklearn.cluster import KMeans
    except ImportError:
        print("  ⚠️ Install scikit-learn: pip install scikit-learn")
        return {}, []

    embeddings = bundle['embeddings']
    n_clusters = min(n_clusters, len(embeddings) // 5)

    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    labels = kmeans.fit_predict(embeddings)

    clusters = defaultdict(list)
    for i, label in enumerate(labels):
        chunk = bundle['chunks'][i]
        source = bundle['sources'].get(chunk['source_id'], {})
        clusters[label].append({
            'text': chunk['text'][:150],
            'title': source.get('title', 'Unknown'),
            'views': source.get('views', 0),
        })

    for label in sorted(clusters.keys()):
        items = clusters[label]
        titles = list(set(item['title'] for item in items))
        views_list = [item['views'] for item in items if item['views'] > 0]
        avg_views = int(np.mean(views_list)) if views_list else 0

        views_str = f" | avg views: {avg_views:,}" if avg_views > 0 else ""
        print(f"\n  Cluster {label + 1} ({len(items)} chunks, {len(titles)} videos{views_str})")

        for t in titles[:4]:
            print(f"    📹 {t}")
        if len(titles) > 4:
            print(f"    ... and {len(titles) - 4} more")

        center = kmeans.cluster_centers_[label]
        center_norm = center / (np.linalg.norm(center) + 1e-8)
        dists = embeddings @ center_norm
        closest = np.argmax(dists)
        print(f"    💬 \"{bundle['chunks'][closest]['text'][:120]}...\"")

    return clusters, labels


# ─── Step 6: Strategic Recommendations ───────────────────────────────

def generate_recommendations(topic_counter, topic_pairs, topic_avg_views, topic_timeline, video_topics, bundle):
    """LLM-powered strategic recommendations with performance + timing context."""
    print("\n\n💡 Strategic Recommendations")
    print("=" * 60)

    # Build rich context
    top_by_views = sorted(topic_avg_views.items(), key=lambda x: x[1], reverse=True)[:10]
    top_by_freq = topic_counter.most_common(10)
    top_pairs = topic_pairs.most_common(10)

    # Timeline summary
    rising = []
    declining = []
    dormant = []
    for topic, eras in topic_timeline.items():
        r, m, o = eras['recent'], eras['middle'], eras['older']
        if r > o and r > m:
            rising.append(topic)
        elif o > r and o > m:
            declining.append(topic)
        elif o > 0 and r == 0:
            dormant.append(topic)

    channel_avg = int(np.mean([s.get('views', 0) for s in bundle['sources_list'] if s.get('views', 0) > 0])) if any(s.get('views', 0) > 0 for s in bundle['sources_list']) else 0

    prompt = f"""You are a content strategist analyzing {bundle['channel']}'s YouTube channel ({len(video_topics)} videos analyzed).

IMPORTANT CONTEXT: Performance data below is RECENCY-WEIGHTED. Recent videos count ~5x more
than old videos in the averages. This reflects the creator's CURRENT direction and audience.
Topics they've moved away from (declining/dormant) represent deliberate strategic shifts,
not mistakes. Respect their evolution — don't recommend going backward unless the data 
strongly supports a revival.

CHANNEL AVERAGE VIEWS (recency-weighted): {channel_avg:,}

TOP TOPICS BY PERFORMANCE (recency-weighted avg views):
{json.dumps([(t, f"{v:,} views") for t, v in top_by_views], indent=2)}

TOP TOPICS BY FREQUENCY:
{json.dumps([(t, c) for t, c in top_by_freq], indent=2)}

RISING TOPICS (more frequent recently — this is where the creator is heading): {', '.join(rising[:8]) if rising else 'None detected'}
DECLINING TOPICS (less frequent recently — creator is deliberately moving away): {', '.join(declining[:8]) if declining else 'None detected'}
DORMANT TOPICS (stopped covering entirely): {', '.join(dormant[:5]) if dormant else 'None detected'}

MOST COMMON TOPIC PAIRS:
{json.dumps([(f"{a} + {b}", c) for (a, b), c in top_pairs], indent=2)}

Provide analysis:

1. HIGHEST-ROI CONTENT: Which topics perform best AND are trending up? These are the sweet spot.
   Focus on what's working NOW, not what worked historically.

2. HIDDEN GEMS: Topics with high recent performance but low frequency — she should make MORE of these.

3. STRATEGIC EVOLUTION: What does the shift from declining→rising topics tell us about where
   the creator is heading? How can we accelerate that transition?

4. RISING BETS: Topics she's leaning into — are they paying off in views?

5. TOPIC COMBOS: What pairings drive the best results? What new combos should she try?

6. SPECIFIC CONTENT IDEAS: 5 specific video ideas that align with her CURRENT direction
   (rising topics), not her past focus (declining topics). Each with a rationale.

Be specific. Reference actual numbers. Think like a strategist who understands creators evolve."""

    try:
        resp = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': ANALYSIS_MODEL,
                'messages': [{"role": "user", "content": prompt}],
                'max_tokens': 2500,
                'temperature': 0.4,
            },
            timeout=120
        )

        if resp.status_code == 200:
            analysis = resp.json()['choices'][0]['message']['content']
            print(f"\n{analysis}")
            return analysis
        else:
            print(f"  ⚠️ API error: {resp.status_code}")
            return None
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return None


# ─── Save Report ──────────────────────────────────────────────────────

def save_report(bundle, video_topics, topic_counter, topic_pairs, topic_avg_views, topic_timeline, recommendations):
    """Save analytics report to bundle."""
    report = {
        'channel': bundle['channel'],
        'generated': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'videos_analyzed': len(video_topics),
        'video_topics': video_topics,
        'topic_frequency': dict(topic_counter.most_common(30)),
        'topic_performance': {t: v for t, v in sorted(topic_avg_views.items(), key=lambda x: x[1], reverse=True)[:30]},
        'topic_pairs': {f"{a} + {b}": c for (a, b), c in topic_pairs.most_common(20)},
        'topic_timeline': {t: dict(eras) for t, eras in topic_timeline.items()},
        'recommendations': recommendations,
    }

    report_path = bundle['bundle_path'] / 'analytics_report.json'
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)

    print(f"\n📄 Report saved: {report_path}")
    return report_path


# ─── Main ─────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) > 1:
        bundle_path = Path(sys.argv[1])
        if not bundle_path.is_absolute():
            bundle_path = BUNDLE_DIR / bundle_path
    else:
        bundle_path = find_latest_bundle()

    if not bundle_path or not bundle_path.exists():
        print("❌ No bundle found. Run fast_ingest.py first.")
        sys.exit(1)

    print(f"📦 Loading bundle: {bundle_path.name}")
    bundle = load_bundle(bundle_path)
    print(f"   {bundle['manifest']['total_videos']} videos, {len(bundle['chunks'])} chunks")
    print(f"   Channel: {bundle['channel']}")

    t_start = time.time()

    # Step 1: Extract topics
    video_topics = extract_topics(bundle)
    if not video_topics:
        print("❌ Topic extraction failed.")
        sys.exit(1)

    # Step 2: Performance analysis
    topic_counter, topic_videos, topic_avg_views = analyze_topic_performance(video_topics, bundle)

    # Step 3: Timeline trends
    topic_timeline = analyze_topic_timeline(video_topics, bundle)

    # Step 4: Relationships
    topic_pairs = analyze_topic_relationships(video_topics)

    # Step 5: Embedding clusters
    clusters, labels = cluster_topics(bundle)

    # Step 6: Strategic recommendations
    recommendations = generate_recommendations(topic_counter, topic_pairs, topic_avg_views, topic_timeline, video_topics, bundle)

    # Save
    save_report(bundle, video_topics, topic_counter, topic_pairs, topic_avg_views, topic_timeline, recommendations)

    print(f"\n🏁 Analytics complete in {time.time() - t_start:.1f}s")


if __name__ == '__main__':
    main()
