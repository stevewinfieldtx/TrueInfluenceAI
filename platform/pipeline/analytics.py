"""
TrueInfluenceAI - Creator Intelligence Dashboard (STATISTICALLY ENHANCED)
=========================================================================
Now uses Z-Scores, Confidence Intervals, and P-Values to determine strategy.
Cloud-ready pipeline integration.
"""

import sys, os, json, time, statistics
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime
import requests

# --- FIX: FORCE PYTHON TO LOOK IN THE SCRIPT'S DIRECTORY ---
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
# -----------------------------------------------------------

try:
    from improved_statistics import StatisticalAnalyzer, TopicCategorizer
except ImportError:
    print("\n❌ CRITICAL ERROR: 'improved_statistics.py' not found.")
    print(f"   Make sure 'improved_statistics.py' is in this folder: {os.path.dirname(os.path.abspath(__file__))}")
    # We don't exit here so the server doesn't crash on import, but analysis will fail later if not fixed.

from dotenv import load_dotenv
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
ANALYSIS_MODEL = os.getenv("OPENROUTER_MODEL_ID", "google/gemini-2.5-flash-lite:online")

def load_bundle_data(bundle_dir):
    """Load bundle data helper."""
    bundle_path = Path(bundle_dir)
    with open(bundle_path / 'manifest.json', encoding='utf-8') as f: manifest = json.load(f)
    with open(bundle_path / 'sources.json', encoding='utf-8') as f: sources = json.load(f)
    
    # Handle chunks optionally if they exist (though analytics needs them)
    chunks = []
    if (bundle_path / 'chunks.json').exists():
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
    
    # Check if we already have topics to save money/time
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
    # Flatten stats for the dashboard legacy support
    flat_stats = {}
    for cat, items in categories.items():
        for item in items:
            flat_stats[item['topic']] = item['avg_views']
            
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

# --- THE KEY FUNCTION YOUR PIPELINE NEEDS ---
def run_analytics(bundle_dir):
    """
    Main entry point for the pipeline.
    Orchestrates the entire statistical analysis flow.
    """
    print(f"📦 Starting Analytics for: {bundle_dir}")
    try:
        bundle = load_bundle_data(bundle_dir)
        
        # 1. Extract Topics
        video_topics = extract_topics(bundle)
        if not video_topics:
            print("❌ No topics extracted. Aborting.")
            return
        
        # 2. Statistical Analysis
        categories, topic_prep = perform_statistical_analysis(video_topics, bundle)
        if not categories:
            print("❌ Statistical analysis failed (likely no views data).")
            return
            
        # 3. Generate Strategy
        recs = generate_strategic_recommendations(categories, bundle)
        
        # 4. Save
        save_report(bundle, video_topics, categories, recs, topic_prep)
        print("✅ Analytics Complete.")
        
    except Exception as e:
        print(f"❌ Analytics Pipeline Failed: {e}")
        import traceback
        traceback.print_exc()

# Allow standalone execution
if __name__ == '__main__':
    if len(sys.argv) > 1:
        run_analytics(sys.argv[1])
    else:
        print("Usage: python analytics.py <bundle_dir>")