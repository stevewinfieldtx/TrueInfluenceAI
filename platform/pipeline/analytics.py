"""
TrueInfluenceAI - Creator Intelligence Dashboard (STATISTICALLY ENHANCED)
=========================================================================
Now uses Z-Scores, Confidence Intervals, and P-Values to determine strategy.
"""

import sys, os, json, time, statistics
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
import requests

# --- FIX: FORCE PYTHON TO LOOK IN THE SCRIPT'S DIRECTORY ---
# This ensures we can import improved_statistics regardless of where we run from
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# -----------------------------------------------------------

try:
    from improved_statistics import StatisticalAnalyzer, TopicCategorizer
except ImportError:
    print("\n❌ CRITICAL ERROR: 'improved_statistics.py' not found.")
    print(f"   Make sure 'improved_statistics.py' is in this folder: {os.path.dirname(os.path.abspath(__file__))}")
    sys.exit(1)

from dotenv import load_dotenv
# Load .env from multiple potential locations
load_dotenv(Path(r"C:\Users\steve\Documents\.env"))
load_dotenv(Path(r"C:\Users\steve\Documents\TruePlatformAI\.env"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
ANALYSIS_MODEL = "google/gemini-2.5-flash-lite:online"
# Point to the bundles directory (Up two levels from pipeline, then into bundles)
BUNDLE_DIR = Path(r"C:\Users\steve\Documents\TrueInfluenceAI\bundles")

def find_latest_bundle():
    if not BUNDLE_DIR.exists():
        return None
    bundles = sorted(BUNDLE_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for b in bundles:
        if (b / 'ready.flag').exists(): return b
    return None

def load_bundle(bundle_path):
    bundle_path = Path(bundle_path)
    with open(bundle_path / 'manifest.json', encoding='utf-8') as f: manifest = json.load(f)
    with open(bundle_path / 'sources.json', encoding='utf-8') as f: sources = json.load(f)
    with open(bundle_path / 'chunks.json', encoding='utf-8') as f: chunks = json.load(f)
    return {
        'manifest': manifest,
        'sources': {s['source_id']: s for s in sources},
        'sources_list': sources,
        'chunks': chunks,
        'channel': manifest.get('channel', 'Unknown'),
        'bundle_path': bundle_path,
    }

def extract_topics(bundle):
    """Ask LLM to tag each video."""
    print("\n🏷️  Extracting topics per video...")
    video_text = defaultdict(list)
    for c in bundle['chunks']:
        video_text[c['source_id']].append(c['text'])

    video_summaries = []
    for vid, texts in video_text.items():
        title = bundle['sources'].get(vid, {}).get('title', 'Unknown')
        snippet = ' '.join((' '.join(texts)).split()[:400])
        video_summaries.append(f"VIDEO_ID: {vid}\nTITLE: {title}\nSNIPPET: {snippet}")

    all_topics = {}
    batch_size = 10
    
    # Check if we already have topics in a previous run to save money
    prev_report = bundle['bundle_path'] / 'analytics_report.json'
    if prev_report.exists():
        try:
            with open(prev_report, encoding='utf-8') as f:
                old_data = json.load(f)
                if old_data.get('video_topics'):
                    print("  ♻️  Loaded existing topics from previous run.")
                    return old_data['video_topics']
        except: pass

    for i in range(0, len(video_summaries), batch_size):
        batch = video_summaries[i:i + batch_size]
        prompt = f"""You are a content strategist. Extract 3-5 topic tags per video.
Tags must be specific but reusable (e.g. "YouTube SEO", "Mindset", "Sales").
Return ONLY valid JSON: [ {{"video_id": "...", "topics": ["T1", "T2"]}}, ... ]
VIDEOS:
{chr(10).join(batch)}"""

        try:
            resp = requests.post(
                'https://openrouter.ai/api/v1/chat/completions',
                headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
                json={'model': ANALYSIS_MODEL, 'messages': [{"role": "user", "content": prompt}], 'max_tokens': 2000}
            )
            if resp.status_code == 200:
                text = resp.json()['choices'][0]['message']['content'].strip().replace('```json','').replace('```','')
                for r in json.loads(text):
                    if r.get('video_id'): all_topics[r['video_id']] = r.get('topics', [])
            print(f"  {min(i + batch_size, len(video_summaries))}/{len(video_summaries)} videos tagged")
        except Exception as e:
            print(f"  ⚠️ Batch error: {e}")

    return all_topics

def perform_statistical_analysis(video_topics, bundle):
    """Run the improved statistical engine."""
    print("\n🧮 Running Statistical Analysis (Z-Scores, CI, Trends)...")
    
    # 1. Calculate Channel Baseline
    views_list = [s.get('views', 0) for s in bundle['sources_list'] if s.get('views', 0) > 0]
    if not views_list:
        print("  ❌ No view data found. Cannot perform analysis.")
        return None, None
        
    channel_avg = statistics.mean(views_list)
    channel_std = statistics.stdev(views_list) if len(views_list) > 1 else channel_avg * 0.5
    print(f"  Channel Baseline: Avg={channel_avg:,.0f}, StdDev={channel_std:,.0f}")
    
    analyzer = StatisticalAnalyzer(channel_avg, channel_std)
    categorizer = TopicCategorizer(analyzer)
    
    # 2. Prepare Data for Categorizer
    topic_prep = defaultdict(lambda: {'views': [], 'dates': [], 'videos': []})
    
    for vid, topics in video_topics.items():
        src = bundle['sources'].get(vid, {})
        v_views = src.get('views', 0)
        v_date_str = src.get('published_at', '') or datetime.now().strftime('%Y-%m-%d')
        
        for t in topics:
            t_clean = t.strip().title()
            topic_prep[t_clean]['views'].append(v_views)
            topic_prep[t_clean]['dates'].append(v_date_str)
            topic_prep[t_clean]['videos'].append({
                'title': src.get('title', 'Unknown'),
                'views': v_views,
                'published': src.get('published_text', ''),
                'url': src.get('url', '')
            })
            
    # 3. Categorize
    categories = categorizer.categorize_all(topic_prep)
    
    # Print summary
    print("\n📊 STATISTICAL CATEGORIZATION:")
    for cat, items in categories.items():
        print(f"  {cat.upper().replace('_', ' ')}: {len(items)} topics")
        for item in items[:3]:
            print(f"    - {item['topic']} (Z={item['z_score']:.2f}, Conf={item['confidence_level']})")
            
    return categories, topic_prep

def generate_strategic_recommendations(categories, bundle):
    """Generate strategy using statistical insights."""
    print("\n🧠 Generating AI Strategy with Statistical Context...")
    
    # Extract top insights
    dd = [f"{t['topic']} (Z={t['z_score']:.1f})" for t in categories['double_down'][:5]]
    ut = [f"{t['topic']} (High Potential, Z={t['z_score']:.1f})" for t in categories['untapped'][:5]]
    rs = [f"{t['topic']} (Declining Trend)" for t in categories['resurface'][:5]]
    sm = [f"{t['topic']} (Z={t['z_score']:.1f})" for t in categories['stop_making'][:5]]
    
    prompt = f"""You are a high-level strategic advisor for "{bundle['channel']}".
I have performed a RIGOROUS STATISTICAL ANALYSIS of their content performance.

STATISTICAL FINDINGS (Z-Scores indicate deviations from channel average):
1. DOUBLE DOWN (Proven, Consistent, High Z-Score): {', '.join(dd)}
2. UNTAPPED OPPORTUNITIES (High Performance, Low Sample Size): {', '.join(ut)}
3. DECLINING/STALE (Statistically significant downtrend): {', '.join(rs)}
4. UNDERPERFORMING (Consistent low Z-Score): {', '.join(sm)}

Based ONLY on this data (do not hallucinate):
1. **The "North Star" Strategy**: What is the ONE clear direction the data is screaming for?
2. **The "Low Hanging Fruit"**: Which 'Untapped' topic is the safest bet to scale immediately?
3. **The "Pivot"**: What topic is dying (Declining/Underperforming) that they need to kill or completely reinvent?
4. **5 Specific Video Titles**: Generate titles that align with the 'Double Down' or 'Untapped' categories.
"""

    try:
        resp = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
            json={'model': ANALYSIS_MODEL, 'messages': [{"role": "user", "content": prompt}], 'max_tokens': 1500}
        )
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        return f"Strategy generation failed: {e}"

def save_report(bundle, video_topics, categories, recommendations, topic_prep):
    # Flatten stats for the dashboard
    flat_stats = {}
    for cat, items in categories.items():
        for item in items:
            flat_stats[item['topic']] = item['avg_views'] # Backward compatibility
            
    # Timeline data for dashboard (reconstruct from topic_prep)
    timeline_data = {}
    for topic, data in topic_prep.items():
        timeline_data[topic] = {'videos': data['videos']}

    report = {
        'channel': bundle['channel'],
        'generated': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'video_topics': video_topics,
        'topic_frequency': {t: len(d['views']) for t, d in topic_prep.items()},
        'topic_performance': flat_stats, 
        'topic_categories': categories,  # NEW RICH DATA
        'topic_timeline': timeline_data,
        'recommendations': recommendations,
    }

    report_path = bundle['bundle_path'] / 'analytics_report.json'
    with open(report_path, 'w', encoding='utf-8') as f: json.dump(report, f, indent=2)
    print(f"\n📄 Report saved: {report_path}")

def main():
    if len(sys.argv) > 1:
        bp = Path(sys.argv[1])
        if not bp.is_absolute(): bp = BUNDLE_DIR / bp
    else: bp = find_latest_bundle()

    if not bp or not bp.exists():
        print(f"❌ No bundle found in {BUNDLE_DIR}"); sys.exit(1)

    print(f"📦 Loading: {bp.name}")
    bundle = load_bundle(bp)
    
    video_topics = extract_topics(bundle)
    if not video_topics: sys.exit(1)
    
    categories, topic_prep = perform_statistical_analysis(video_topics, bundle)
    if not categories: sys.exit(1)
    
    recs = generate_strategic_recommendations(categories, bundle)
    save_report(bundle, video_topics, categories, recs, topic_prep)

if __name__ == '__main__':
    main()