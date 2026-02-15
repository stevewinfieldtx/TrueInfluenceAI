"""
TrueInfluenceAI - Deep Insights Generator (Cloud)
===================================================
Full statistical analysis + LLM deep insights.
Produces all data needed by build_actionable_core.py:
  - Title pattern analysis
  - Engagement anomalies (passion signals)
  - Topic cannibalization
  - Content velocity
  - Contrarian content detection
  - Revival candidates
  - AI deep analysis (one big bet, blind spots, etc.)
"""

import os, json, re
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta

import numpy as np
import requests
import traceback

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL_ID = os.getenv("OPENROUTER_MODEL_ID", "google/gemini-2.5-flash-lite:online")


def build_insights(bundle_dir):
    """Generate deep statistical + AI insights from creator data."""
    bundle_dir = Path(bundle_dir)

    sources = json.loads((bundle_dir / "sources.json").read_text(encoding="utf-8"))
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))

    report = {}
    if (bundle_dir / "analytics_report.json").exists():
        report = json.loads((bundle_dir / "analytics_report.json").read_text(encoding="utf-8"))
    metrics = {}
    if (bundle_dir / "channel_metrics.json").exists():
        metrics = json.loads((bundle_dir / "channel_metrics.json").read_text(encoding="utf-8"))
    voice = {}
    if (bundle_dir / "voice_profile.json").exists():
        voice = json.loads((bundle_dir / "voice_profile.json").read_text(encoding="utf-8"))

    channel = manifest.get("channel", "Unknown")
    channel_avg_views = metrics.get("channel_avg_views", 0)
    channel_avg_likes = metrics.get("channel_avg_likes", 0)
    channel_avg_comments = metrics.get("channel_avg_comments", 0)
    # Fallback: compute from total if per-video avg not stored
    if not channel_avg_comments and metrics.get('total_comments') and len(sources) > 0:
        channel_avg_comments = metrics['total_comments'] / len(sources)

    insights = {}

    try:
        _build_all_insights(insights, sources, report, metrics, channel, channel_avg_views, channel_avg_likes, channel_avg_comments, bundle_dir)
    except Exception as e:
        print(f"  ERROR in insights: {e}")
        traceback.print_exc()
        insights['error'] = str(e)

    insights['generated_at'] = datetime.utcnow().isoformat()
    (bundle_dir / "insights.json").write_text(
        json.dumps(insights, indent=2, ensure_ascii=False, default=str), encoding="utf-8"
    )
    count_r = len(insights.get('revival_candidates', []))
    count_c = len(insights.get('topic_cannibalization', []))
    count_p = len(insights.get('engagement_anomalies', {}).get('high_passion', []))
    print(f"  Insights complete: {count_r} revivals, {count_c} cannibalization, {count_p} passion signals")


def _build_all_insights(insights, sources, report, metrics, channel, channel_avg_views, channel_avg_likes, channel_avg_comments, bundle_dir):
    # ─── 1. TITLE PATTERN ANALYSIS ───────────────────────────────
    print("  [1/7] Title patterns...")
    patterns = {
        'dollar_amount': r'\$[\d,.]+[kKmM]?',
        'number_in_title': r'\b\d+\b',
        'how_to': r'(?i)^how\s+(to|i|a)',
        'question_title': r'\?',
        'negative_contrarian': r"(?i)(without|don't|stop|never|no one|isn't|won't|over|anti|quit)",
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
            'count': len(matching), 'avg_views': avg_match,
            'avg_views_without': avg_non, 'lift_pct': lift,
            'examples': [s['title'] for s in sorted(matching, key=lambda x: x.get('views', 0), reverse=True)[:3]],
        }

    insights['title_patterns'] = dict(sorted(pattern_results.items(), key=lambda x: x[1]['lift_pct'], reverse=True))

    # ─── 2. ENGAGEMENT ANOMALIES ─────────────────────────────────
    print("  [2/7] Engagement anomalies...")
    engagement_data = []
    for s in sources:
        views = s.get('views', 0)
        likes = s.get('likes', 0)
        comments = s.get('comment_count', s.get('comments', 0))
        if views < 100:
            continue
        like_rate = round(likes / views * 100, 2) if views > 0 else 0
        comment_rate = round(comments / views * 100, 2) if views > 0 else 0
        engagement_rate = round((likes + comments) / views * 100, 2) if views > 0 else 0
        avg_like_rate = round(channel_avg_likes / channel_avg_views * 100, 2) if channel_avg_views > 0 else 0
        avg_comment_rate = round(channel_avg_comments / channel_avg_views * 100, 2) if channel_avg_views > 0 else 0
        engagement_data.append({
            'title': s.get('title', ''), 'views': views, 'likes': likes, 'comments': comments,
            'like_rate': like_rate, 'comment_rate': comment_rate, 'engagement_rate': engagement_rate,
            'like_rate_vs_avg': round(like_rate / avg_like_rate, 2) if avg_like_rate > 0 else 0,
            'comment_rate_vs_avg': round(comment_rate / avg_comment_rate, 2) if avg_comment_rate > 0 else 0,
            'published_at': s.get('published_at', ''),
        })

    high_comment = sorted(engagement_data, key=lambda x: x['comment_rate'], reverse=True)[:5]
    high_like = sorted(engagement_data, key=lambda x: x['like_rate'], reverse=True)[:5]
    shallow_viral = sorted(
        [e for e in engagement_data if e['views'] > channel_avg_views],
        key=lambda x: x['engagement_rate']
    )[:3]

    insights['engagement_anomalies'] = {
        'high_passion': high_comment, 'high_approval': high_like, 'shallow_viral': shallow_viral,
        'channel_avg_like_rate': round(channel_avg_likes / channel_avg_views * 100, 2) if channel_avg_views > 0 else 0,
        'channel_avg_comment_rate': round(channel_avg_comments / channel_avg_views * 100, 2) if channel_avg_views > 0 else 0,
    }

    # ─── 3. TOPIC CANNIBALIZATION ────────────────────────────────
    print("  [3/7] Topic cannibalization...")
    topic_freq = report.get('topic_frequency', {})
    topic_pairs = report.get('topic_pairs', {})

    cannibalization = []
    for pair_key, raw_co in topic_pairs.items():
        co_count = raw_co.get('count', 0) if isinstance(raw_co, dict) else (raw_co or 0)
        parts = pair_key.split(' + ')
        if len(parts) != 2:
            continue
        t1, t2 = parts
        f1 = topic_freq.get(t1, 0)
        f1 = f1.get('count', 0) if isinstance(f1, dict) else (f1 or 0)
        f2 = topic_freq.get(t2, 0)
        f2 = f2.get('count', 0) if isinstance(f2, dict) else (f2 or 0)
        if f1 == 0 or f2 == 0:
            continue
        overlap_pct = round(co_count / min(f1, f2) * 100, 1)
        if overlap_pct >= 60 and co_count >= 3:
            cannibalization.append({
                'topic_a': t1, 'topic_b': t2, 'co_occurrences': co_count,
                'freq_a': f1, 'freq_b': f2, 'overlap_pct': overlap_pct,
            })

    cannibalization.sort(key=lambda x: x['overlap_pct'], reverse=True)
    insights['topic_cannibalization'] = cannibalization[:10]

    # ─── 4. CONTENT VELOCITY ─────────────────────────────────────
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
            'title': curr.get('title', ''), 'views': curr.get('views', 0),
            'gap_days': gap_days, 'published_at': curr.get('published_at', ''),
        })

    if velocity_data:
        gaps = [v['gap_days'] for v in velocity_data if v['gap_days'] > 0]
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
        }

    # ─── 5. CONTRARIAN CONTENT DETECTION ─────────────────────────
    print("  [5/7] Contrarian content...")
    contrarian_keywords = [
        'without', "don't", 'stop', 'never', 'no one', "isn't", "won't",
        'over', 'anti', 'quit', 'myth', 'lie', 'wrong', 'mistake', 'truth',
        'harsh', 'ugly', 'hate', 'dead', 'kill', 'secret', 'nobody',
    ]
    contrarian_vids = []
    conventional_vids = []
    for s in sources:
        title_lower = s.get('title', '').lower()
        is_contrarian = any(kw in title_lower for kw in contrarian_keywords)
        entry = {
            'title': s.get('title', ''), 'views': s.get('views', 0),
            'likes': s.get('likes', 0), 'comments': s.get('comment_count', s.get('comments', 0)),
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
        'contrarian_count': len(contrarian_vids), 'conventional_count': len(conventional_vids),
        'avg_views_contrarian': avg_contrarian, 'avg_views_conventional': avg_conventional,
        'lift_pct': contrarian_lift,
        'top_contrarian': sorted(contrarian_vids, key=lambda x: x['views'], reverse=True)[:5],
    }

    # ─── 6. REVIVAL CANDIDATES ───────────────────────────────────
    print("  [6/7] Revival candidates...")
    topic_timeline = report.get('topic_timeline', {})
    topic_perf = report.get('topic_performance', {})

    revivals = []
    for topic, tl in topic_timeline.items():
        if not isinstance(tl, dict):
            continue
        r, m, o = tl.get('recent', 0), tl.get('middle', 0), tl.get('older', 0)
        perf = topic_perf.get(topic, 0)
        avg_v = perf.get('weighted_avg_views', perf.get('avg_views', 0)) if isinstance(perf, dict) else (perf or 0)
        if (o > r or (o > 0 and r == 0)) and avg_v > channel_avg_views * 0.8:
            revivals.append({
                'topic': topic, 'avg_views': int(avg_v),
                'vs_channel': round(avg_v / channel_avg_views, 2) if channel_avg_views > 0 else 0,
                'recent': r, 'middle': m, 'older': o,
                'trend': 'dormant' if r == 0 and o > 0 else 'declining',
            })

    revivals.sort(key=lambda x: x['avg_views'], reverse=True)
    insights['revival_candidates'] = revivals[:8]

    # ─── 7. AI DEEP ANALYSIS ─────────────────────────────────────
    print("  [7/7] AI deep analysis...")

    prompt = f"""You are a world-class content strategist analyzing a YouTube creator's channel.
Your job is to find insights they would NEVER see on their own.

CHANNEL: {channel}
CHANNEL AVG VIEWS: {channel_avg_views:,}

=== TITLE FORMULA ANALYSIS ===
{json.dumps({k: {'lift': v['lift_pct'], 'count': v['count'], 'avg_views': v['avg_views']} for k, v in insights['title_patterns'].items()}, indent=2)}

=== CONTRARIAN vs CONVENTIONAL ===
Contrarian titles ({insights['contrarian_content']['contrarian_count']} videos) avg {insights['contrarian_content']['avg_views_contrarian']:,} views
Conventional titles ({insights['contrarian_content']['conventional_count']} videos) avg {insights['contrarian_content']['avg_views_conventional']:,} views
Contrarian lift: {insights['contrarian_content']['lift_pct']}%

=== ENGAGEMENT ANOMALIES ===
Highest passion (comment rate): {json.dumps([{{'title': v['title'], 'comment_rate': str(v['comment_rate'])+'%', 'views': v['views']}} for v in insights['engagement_anomalies']['high_passion'][:3]], indent=2)}

=== CONTENT VELOCITY ===
{json.dumps(insights.get('content_velocity', {{}}), indent=2, default=str)}

=== REVIVAL CANDIDATES ===
{json.dumps(insights['revival_candidates'][:5], indent=2)}

=== TOPIC CANNIBALIZATION (>60% overlap) ===
{json.dumps(insights['topic_cannibalization'][:5], indent=2)}

Respond in JSON. Be specific, cite numbers, focus on NON-OBVIOUS insights:
{{
  "blind_spots": ["3-4 things the creator probably doesn't realize"],
  "money_left_on_table": ["3 specific missed opportunities based on data"],
  "title_formula_rec": {{"formula": "The title pattern they should use more", "examples": ["3 example titles using this formula"]}},
  "posting_rhythm_rec": "Based on velocity data, the optimal posting schedule",
  "one_big_bet": "The single biggest content bet they should make — be specific, bold, and cite the data that supports it",
  "four_followups": [
    "Follow-up action #1 that supports the big bet — specific and actionable",
    "Follow-up action #2 — a different angle or tactic that reinforces the strategy",
    "Follow-up action #3 — something they should STOP doing or change",
    "Follow-up action #4 — the quick win they can do THIS WEEK"
  ]
}}"""

    try:
        resp = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={
                'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                'Content-Type': 'application/json',
            },
            json={
                'model': OPENROUTER_MODEL_ID,
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 1500, 'temperature': 0.4,
            },
            timeout=90,
        )
        if resp.status_code == 200:
            text = resp.json()['choices'][0]['message']['content'].strip()
            text = text.replace('```json', '').replace('```', '').strip()
            try:
                insights['ai_deep_analysis'] = json.loads(text)
            except:
                insights['ai_deep_analysis'] = {'raw': text}
            print(f"    AI deep analysis complete")
        else:
            print(f"    API error: {resp.status_code}")
    except Exception as e:
        print(f"    AI analysis failed: {e}")
        insights['ai_deep_analysis'] = {}

    # Keep strategic_direction for backwards compat
    insights['strategic_direction'] = insights.get('ai_deep_analysis', {}).get('one_big_bet', '')
