"""
TrueInfluenceAI - Deep Insights Generator
==========================================
Analyzes bundle data to surface non-obvious insights:
  - Title pattern analysis (what title formulas work)
  - Engagement anomalies (high comment/like ratios)
  - Topic cannibalization detection
  - Content velocity vs performance
  - Contrarian content detection
  - Optimal posting patterns
  
Saves insights.json to the bundle, used by build_pages.py for analytics.html

Usage:
  python build_insights.py
"""

import json, re, os
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta
import numpy as np

from dotenv import load_dotenv
load_dotenv(Path(r"C:\Users\steve\Documents\.env"))
load_dotenv(Path(r"C:\Users\steve\Documents\TruePlatformAI\.env"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
BUNDLE_DIR = Path(r"C:\Users\steve\Documents\TrueInfluenceAI\bundles")

import requests

def find_latest_bundle():
    bundles = sorted(BUNDLE_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for b in bundles:
        if (b / 'ready.flag').exists():
            return b
    return None


def load_data(bp):
    data = {}
    for name in ['manifest', 'sources', 'analytics_report', 'channel_metrics', 'voice_profile']:
        p = bp / f'{name}.json'
        if p.exists():
            with open(p, 'r', encoding='utf-8') as f:
                data[name] = json.load(f)
        else:
            data[name] = {} if name != 'sources' else []
    return data


def analyze(bp, data):
    sources = data['sources']
    report = data.get('analytics_report', {})
    metrics = data.get('channel_metrics', {})
    channel_avg_views = metrics.get('channel_avg_views', 0)
    channel_avg_likes = metrics.get('channel_avg_likes', 0)
    channel_avg_comments = metrics.get('channel_avg_comments', 0)

    insights = {}

    # ─── 1. TITLE PATTERN ANALYSIS ───────────────────────────────────
    print("  [1/7] Title patterns...")
    patterns = {
        'dollar_amount': r'\$[\d,.]+[kKmM]?',
        'number_in_title': r'\b\d+\b',
        'how_to': r'(?i)^how\s+(to|i|a)',
        'question_title': r'\?',
        'negative_contrarian': r'(?i)(without|don\'t|stop|never|no one|isn\'t|won\'t|over|anti|quit)',
        'listicle': r'(?i)^\d+\s',
        'parenthetical': r'\(.*\)',
        'timeframe': r'(?i)(\d+\s*(day|week|month|year|minute|hour)s?|\btoday\b|\bfast\b)',
    }

    pattern_results = {}
    for pname, regex in patterns.items():
        matching = [s for s in sources if re.search(regex, s.get('title', ''))]
        non_matching = [s for s in sources if not re.search(regex, s.get('title', ''))]

        match_views = [s['views'] for s in matching if s.get('views', 0) > 0]
        non_views = [s['views'] for s in non_matching if s.get('views', 0) > 0]

        avg_match = int(np.mean(match_views)) if match_views else 0
        avg_non = int(np.mean(non_views)) if non_views else 0
        lift = round((avg_match / avg_non - 1) * 100, 1) if avg_non > 0 else 0

        pattern_results[pname] = {
            'count': len(matching),
            'avg_views': avg_match,
            'avg_views_without': avg_non,
            'lift_pct': lift,
            'examples': [s['title'] for s in sorted(matching, key=lambda x: x.get('views', 0), reverse=True)[:3]],
        }

    # Sort by lift
    insights['title_patterns'] = dict(sorted(pattern_results.items(), key=lambda x: x[1]['lift_pct'], reverse=True))

    # ─── 2. ENGAGEMENT ANOMALIES ─────────────────────────────────────
    print("  [2/7] Engagement anomalies...")
    engagement_data = []
    for s in sources:
        views = s.get('views', 0)
        likes = s.get('likes', 0)
        comments = s.get('comment_count', 0)
        if views < 100:
            continue

        like_rate = round(likes / views * 100, 2) if views > 0 else 0
        comment_rate = round(comments / views * 100, 2) if views > 0 else 0
        engagement_rate = round((likes + comments) / views * 100, 2) if views > 0 else 0

        avg_like_rate = round(channel_avg_likes / channel_avg_views * 100, 2) if channel_avg_views > 0 else 0
        avg_comment_rate = round(channel_avg_comments / channel_avg_views * 100, 2) if channel_avg_views > 0 else 0

        engagement_data.append({
            'title': s.get('title', ''),
            'views': views,
            'likes': likes,
            'comments': comments,
            'like_rate': like_rate,
            'comment_rate': comment_rate,
            'engagement_rate': engagement_rate,
            'like_rate_vs_avg': round(like_rate / avg_like_rate, 2) if avg_like_rate > 0 else 0,
            'comment_rate_vs_avg': round(comment_rate / avg_comment_rate, 2) if avg_comment_rate > 0 else 0,
            'published_at': s.get('published_at', ''),
        })

    # High comment rate (audience passion signal)
    high_comment = sorted(engagement_data, key=lambda x: x['comment_rate'], reverse=True)[:5]
    # High like rate (audience approval signal)
    high_like = sorted(engagement_data, key=lambda x: x['like_rate'], reverse=True)[:5]
    # Low engagement despite high views (viral but shallow)
    shallow_viral = sorted(
        [e for e in engagement_data if e['views'] > channel_avg_views],
        key=lambda x: x['engagement_rate']
    )[:3]

    insights['engagement_anomalies'] = {
        'high_passion': high_comment,
        'high_approval': high_like,
        'shallow_viral': shallow_viral,
        'channel_avg_like_rate': round(channel_avg_likes / channel_avg_views * 100, 2) if channel_avg_views > 0 else 0,
        'channel_avg_comment_rate': round(channel_avg_comments / channel_avg_views * 100, 2) if channel_avg_views > 0 else 0,
    }

    # ─── 3. TOPIC CANNIBALIZATION ─────────────────────────────────────
    print("  [3/7] Topic cannibalization...")
    topic_freq = report.get('topic_frequency', {})
    topic_pairs = report.get('topic_pairs', {})
    video_topics = report.get('video_topics', {})

    # Find topics that almost always appear together (>70% co-occurrence)
    cannibalization = []
    for pair_key, co_count in topic_pairs.items():
        parts = pair_key.split(' + ')
        if len(parts) != 2:
            continue
        t1, t2 = parts
        f1 = topic_freq.get(t1, 0)
        f2 = topic_freq.get(t2, 0)
        if f1 == 0 or f2 == 0:
            continue
        overlap_pct = round(co_count / min(f1, f2) * 100, 1)
        if overlap_pct >= 60 and co_count >= 3:
            cannibalization.append({
                'topic_a': t1, 'topic_b': t2,
                'co_occurrences': co_count,
                'freq_a': f1, 'freq_b': f2,
                'overlap_pct': overlap_pct,
            })

    cannibalization.sort(key=lambda x: x['overlap_pct'], reverse=True)
    insights['topic_cannibalization'] = cannibalization[:10]

    # ─── 4. CONTENT VELOCITY ─────────────────────────────────────────
    print("  [4/7] Content velocity...")
    dated_sources = []
    for s in sources:
        pub = s.get('published_at', '')
        if pub:
            try:
                dt = datetime.fromisoformat(pub.replace('Z', '+00:00'))
                dated_sources.append({**s, '_dt': dt})
            except:
                pass

    dated_sources.sort(key=lambda x: x['_dt'], reverse=True)

    velocity_data = []
    for i in range(len(dated_sources) - 1):
        curr = dated_sources[i]
        prev = dated_sources[i + 1]
        gap_days = (curr['_dt'] - prev['_dt']).days
        velocity_data.append({
            'title': curr.get('title', ''),
            'views': curr.get('views', 0),
            'gap_days': gap_days,
            'published_at': curr.get('published_at', ''),
        })

    if velocity_data:
        # Correlate gap with views
        gaps = [v['gap_days'] for v in velocity_data if v['gap_days'] > 0]
        views = [v['views'] for v in velocity_data if v['gap_days'] > 0]

        # Bucket by posting frequency
        fast_posts = [v for v in velocity_data if 0 < v['gap_days'] <= 5]
        normal_posts = [v for v in velocity_data if 5 < v['gap_days'] <= 10]
        slow_posts = [v for v in velocity_data if v['gap_days'] > 10]

        avg_fast = int(np.mean([v['views'] for v in fast_posts])) if fast_posts else 0
        avg_normal = int(np.mean([v['views'] for v in normal_posts])) if normal_posts else 0
        avg_slow = int(np.mean([v['views'] for v in slow_posts])) if slow_posts else 0

        insights['content_velocity'] = {
            'avg_gap_days': round(np.mean(gaps), 1) if gaps else 0,
            'fast_posting': {'label': '1-5 days apart', 'count': len(fast_posts), 'avg_views': avg_fast},
            'normal_posting': {'label': '6-10 days apart', 'count': len(normal_posts), 'avg_views': avg_normal},
            'slow_posting': {'label': '11+ days apart', 'count': len(slow_posts), 'avg_views': avg_slow},
            'best_performers_by_gap': sorted(velocity_data, key=lambda x: x['views'], reverse=True)[:5],
        }

    # ─── 5. CONTRARIAN CONTENT DETECTION ─────────────────────────────
    print("  [5/7] Contrarian content...")
    contrarian_keywords = [
        'without', 'don\'t', 'stop', 'never', 'no one', 'isn\'t', 'won\'t',
        'over', 'anti', 'quit', 'myth', 'lie', 'wrong', 'mistake', 'truth',
        'harsh', 'ugly', 'hate', 'dead', 'kill', 'secret', 'nobody',
    ]
    contrarian_vids = []
    conventional_vids = []
    for s in sources:
        title_lower = s.get('title', '').lower()
        is_contrarian = any(kw in title_lower for kw in contrarian_keywords)
        entry = {
            'title': s.get('title', ''),
            'views': s.get('views', 0),
            'likes': s.get('likes', 0),
            'comments': s.get('comment_count', 0),
            'published_at': s.get('published_at', ''),
        }
        if is_contrarian:
            contrarian_vids.append(entry)
        else:
            conventional_vids.append(entry)

    avg_contrarian = int(np.mean([v['views'] for v in contrarian_vids])) if contrarian_vids else 0
    avg_conventional = int(np.mean([v['views'] for v in conventional_vids])) if conventional_vids else 0
    contrarian_lift = round((avg_contrarian / avg_conventional - 1) * 100, 1) if avg_conventional > 0 else 0

    insights['contrarian_content'] = {
        'contrarian_count': len(contrarian_vids),
        'conventional_count': len(conventional_vids),
        'avg_views_contrarian': avg_contrarian,
        'avg_views_conventional': avg_conventional,
        'lift_pct': contrarian_lift,
        'top_contrarian': sorted(contrarian_vids, key=lambda x: x['views'], reverse=True)[:5],
    }

    # ─── 6. REVIVAL CANDIDATES ───────────────────────────────────────
    print("  [6/7] Revival candidates...")
    topic_timeline = report.get('topic_timeline', {})
    topic_perf = report.get('topic_performance', {})

    revivals = []
    for topic, tl in topic_timeline.items():
        r, m, o = tl.get('recent', 0), tl.get('middle', 0), tl.get('older', 0)
        avg_v = topic_perf.get(topic, 0)
        # Declining or dormant but above-average performance
        if (o > r or (o > 0 and r == 0)) and avg_v > channel_avg_views * 0.8:
            revivals.append({
                'topic': topic,
                'avg_views': avg_v,
                'vs_channel': round(avg_v / channel_avg_views, 2) if channel_avg_views > 0 else 0,
                'recent': r, 'middle': m, 'older': o,
                'trend': 'dormant' if r == 0 and o > 0 else 'declining',
            })

    revivals.sort(key=lambda x: x['avg_views'], reverse=True)
    insights['revival_candidates'] = revivals[:8]

    # ─── 7. AI DEEP ANALYSIS ─────────────────────────────────────────
    print("  [7/7] AI deep analysis...")

    # Build a rich prompt with all the non-obvious data
    prompt = f"""You are a world-class content strategist analyzing a YouTube creator's channel. 
Your job is to find insights they would NEVER see on their own — non-obvious patterns, 
counterintuitive findings, and specific actionable recommendations.

CHANNEL: {data['manifest'].get('channel', 'Unknown')}
CHANNEL AVG VIEWS: {channel_avg_views:,}

=== TITLE FORMULA ANALYSIS ===
{json.dumps({k: {'lift': v['lift_pct'], 'count': v['count'], 'avg_views': v['avg_views']} for k, v in insights['title_patterns'].items()}, indent=2)}

=== CONTRARIAN vs CONVENTIONAL ===
Contrarian titles ({insights['contrarian_content']['contrarian_count']} videos) avg {insights['contrarian_content']['avg_views_contrarian']:,} views
Conventional titles ({insights['contrarian_content']['conventional_count']} videos) avg {insights['contrarian_content']['avg_views_conventional']:,} views
Contrarian lift: {insights['contrarian_content']['lift_pct']}%
Top contrarian: {json.dumps([v['title'] + f" ({v['views']:,} views)" for v in insights['contrarian_content']['top_contrarian'][:3]])}

=== ENGAGEMENT ANOMALIES ===
Highest passion (comment rate): {json.dumps([{'title': v['title'], 'comment_rate': str(v['comment_rate'])+'%', 'views': v['views']} for v in insights['engagement_anomalies']['high_passion'][:3]], indent=2)}

=== CONTENT VELOCITY ===
{json.dumps(insights.get('content_velocity', {}), indent=2, default=str)}

=== REVIVAL CANDIDATES (declining topics that performed well) ===
{json.dumps(insights['revival_candidates'][:5], indent=2)}

=== TOPIC CANNIBALIZATION (topics that overlap >60%) ===
{json.dumps(insights['topic_cannibalization'][:5], indent=2)}

Respond in JSON. Be specific, cite numbers, and focus on NON-OBVIOUS insights:
{{
  "blind_spots": ["3-4 things the creator probably doesn't realize about their own content"],
  "money_left_on_table": ["3 specific opportunities they're missing based on this data"],
  "title_formula_rec": "The specific title formula they should use more, with 3 example titles",
  "posting_rhythm_rec": "Based on velocity data, what posting schedule optimizes their views",
  "one_big_bet": "The single biggest content bet they should make based on ALL this data — be specific and bold"
}}"""

    try:
        resp = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': 'google/gemini-2.5-flash-lite:online',
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 1500,
                'temperature': 0.4,
            },
            timeout=60,
        )
        if resp.status_code == 200:
            text = resp.json()['choices'][0]['message']['content'].strip()
            text = text.replace('```json', '').replace('```', '').strip()
            try:
                insights['ai_deep_analysis'] = json.loads(text)
            except:
                insights['ai_deep_analysis'] = {'raw': text}
        else:
            print(f"    API error: {resp.status_code}")
    except Exception as e:
        print(f"    AI analysis failed: {e}")

    return insights


def main():
    bp = find_latest_bundle()
    if not bp:
        print("[!] No bundle found.")
        return

    print(f"[*] Generating deep insights for: {bp.name}")
    data = load_data(bp)
    insights = analyze(bp, data)

    out = bp / 'insights.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(insights, f, indent=2, default=str)

    print(f"\n[OK] Saved {out}")
    print(f"     {len(insights)} insight categories generated")


if __name__ == '__main__':
    main()
