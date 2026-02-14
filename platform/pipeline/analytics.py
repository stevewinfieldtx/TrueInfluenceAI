"""
TrueInfluenceAI - Cloud Analytics Pipeline
============================================
Topic extraction, timeline analysis, performance scoring.
Cloud-ready version of analytics.py with recency weighting.
"""

import sys, os, json, time, statistics
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import requests

# -------------------------------------------------------------------------
# 1. ROBUST IMPORT LOGIC
# -------------------------------------------------------------------------
try:
    from improved_statistics import StatisticalAnalyzer, TopicCategorizer
    print("✅ Loaded stats engine (local import)")
except ImportError:
    try:
        from pipeline.improved_statistics import StatisticalAnalyzer, TopicCategorizer
        print("✅ Loaded stats engine (package import)")
    except ImportError:
        current_dir = os.path.dirname(os.path.abspath(__file__))
        if current_dir not in sys.path:
            sys.path.append(current_dir)
        try:
            from improved_statistics import StatisticalAnalyzer, TopicCategorizer
            print("✅ Loaded stats engine (path patched)")
        except ImportError as e:
            print(f"\n❌ CRITICAL: Could not load improved_statistics.py. Details: {e}")
            class StatisticalAnalyzer:
                def __init__(self, *args, **kwargs): pass
            class TopicCategorizer:
                def __init__(self, *args, **kwargs): pass
                def categorize_all(self, *args, **kwargs): return {}
# -------------------------------------------------------------------------

from dotenv import load_dotenv
load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
ANALYSIS_MODEL = os.getenv("OPENROUTER_MODEL_ID", "google/gemini-2.5-flash-lite:online")

def load_bundle_data(bundle_dir):
    bundle_path = Path(bundle_dir)
    with open(bundle_path / 'manifest.json', encoding='utf-8') as f: manifest = json.load(f)
    with open(bundle_path / 'sources.json', encoding='utf-8') as f: sources = json.load(f)
    
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
    print("\n🏷️  Extracting topics per video...")
    video_text = defaultdict(list)
    
    # --- FIX: Handle missing 'source_id' key in chunks ---
    # Chunks from ingest.py usually have 'video_id', sources use 'source_id'
    for c in bundle['chunks']:
        vid = c.get('video_id') or c.get('source_id')
        if vid and 'text' in c:
            video_text[vid].append(c['text'])
    # -----------------------------------------------------

    video_summaries = []
    for vid, texts in video_text.items():
        # Only analyze videos we have metadata for
        if vid not in bundle['sources']:
            continue
            
        title = bundle['sources'][vid].get('title', 'Unknown')
        snippet = ' '.join((' '.join(texts)).split()[:400])
        video_summaries.append(f"VIDEO_ID: {vid}\nTITLE: {title}\nSNIPPET: {snippet}")

    all_topics = {}
    
    # Check for existing report to save API costs
    prev_report = bundle['bundle_path'] / 'analytics_report.json'
    if prev_report.exists():
        try:
            with open(prev_report, encoding='utf-8') as f:
                old_data = json.load(f)
                if old_data.get('video_topics'):
                    print("  ♻️  Loaded existing topics from previous run.")
                    return old_data['video_topics']
        except: pass

    batch_size = 10
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
                try:
                    for r in json.loads(text):
                        if r.get('video_id'): all_topics[r['video_id']] = r.get('topics', [])
                except: pass
            print(f"  {min(i + batch_size, len(video_summaries))}/{len(video_summaries)} videos tagged")
        except Exception as e:
            print(f"  ⚠️ Batch error: {e}")

    return all_topics

def perform_statistical_analysis(video_topics, bundle):
    print("\n🧮 Running Statistical Analysis...")
    
    views_list = [s.get('views', 0) for s in bundle['sources_list'] if s.get('views', 0) > 0]
    if not views_list:
        print("  ❌ No view data found. Skipping stats.")
        return {}, {}
        
    channel_avg = statistics.mean(views_list)
    channel_std = statistics.stdev(views_list) if len(views_list) > 1 else channel_avg * 0.5
    
    analyzer = StatisticalAnalyzer(channel_avg, channel_std)
    categorizer = TopicCategorizer(analyzer)
    
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
            
    categories = categorizer.categorize_all(topic_prep)
    return categories, topic_prep

def generate_strategic_recommendations(categories, bundle):
    print("\n🧠 Generating AI Strategy...")
    
    if not categories:
        return "Not enough data for strategy."

    dd = [f"{t['topic']} (Z={t.get('z_score', 0):.1f})" for t in categories.get('double_down', [])[:5]]
    ut = [f"{t['topic']} (Z={t.get('z_score', 0):.1f})" for t in categories.get('untapped', [])[:5]]
    
    prompt = f"""You are a high-level strategic advisor for "{bundle['channel']}".
I have performed a RIGOROUS STATISTICAL ANALYSIS of their content.

FINDINGS:
1. DOUBLE DOWN: {', '.join(dd)}
2. UNTAPPED: {', '.join(ut)}

Based ONLY on this data:
1. **North Star Strategy**: One clear direction?
2. **Low Hanging Fruit**: Safest bet to scale?
3. **5 Video Titles**: Aligned with Double Down/Untapped."""

    try:
        resp = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}'},
            json={'model': ANALYSIS_MODEL, 'messages': [{"role": "user", "content": prompt}], 'max_tokens': 1000}
        )
        return resp.json()['choices'][0]['message']['content']
    except Exception:
        return "Strategy generation failed."

def save_report(bundle, video_topics, categories, recommendations, topic_prep):
    # Flatten stats for legacy support
    flat_stats = {}
    if categories:
        for cat, items in categories.items():
            for item in items:
                flat_stats[item['topic']] = item['avg_views']
            
    # Timeline data
    timeline_data = {}
    if topic_prep:
        for topic, data in topic_prep.items():
            timeline_data[topic] = {'videos': data['videos']}

    report = {
        'channel': bundle['channel'],
        'generated': time.strftime('%Y-%m-%dT%H:%M:%S'),
        'video_topics': video_topics,
        'topic_frequency': {t: len(d['views']) for t, d in topic_prep.items()} if topic_prep else {},
        'topic_performance': flat_stats, 
        'topic_categories': categories or {},
        'topic_timeline': timeline_data,
        'recommendations': recommendations,
    }

    report_path = bundle['bundle_path'] / 'analytics_report.json'
    with open(report_path, 'w', encoding='utf-8') as f: json.dump(report, f, indent=2)
    print(f"\n📄 Report saved: {report_path}")

def run_analytics(bundle_dir):
    """
    Main entry point called by server.py.
    """
    print(f"📦 Starting Analytics for: {bundle_dir}")
    try:
        bundle = load_bundle_data(bundle_dir)
        
        video_topics = extract_topics(bundle)
        if not video_topics:
            print("❌ No topics extracted. Aborting.")
            # Create a dummy report so pages don't crash entirely
            save_report(bundle, {}, {}, "No topics found.", {})
            return
        
        categories, topic_prep = perform_statistical_analysis(video_topics, bundle)
        recs = generate_strategic_recommendations(categories, bundle)
        
        save_report(bundle, video_topics, categories, recs, topic_prep)
        print("✅ Analytics Complete.")
        
    except Exception as e:
        print(f"❌ Analytics Pipeline Failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    if len(sys.argv) > 1:
        run_analytics(sys.argv[1])
    else:
        print("Usage: python analytics.py <bundle_dir>")