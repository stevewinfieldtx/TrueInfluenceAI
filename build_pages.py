"""
TrueInfluenceAI - Build Landing, Analytics & Discussion Pages
===============================================================
Generates three HTML pages into the bundle folder:
  - index.html       (landing page → links to dashboard, analytics, discussion)
  - analytics.html   (visual analytics report)
  - discuss.html     (chat with the influencer's AI voice + source references)

Usage:
  python build_pages.py                          (latest bundle)
  python build_pages.py SunnyLenarduzzi_20260211_164612
"""

import sys, os, json
from pathlib import Path
from datetime import datetime

from dotenv import load_dotenv
load_dotenv(Path(r"C:\Users\steve\Documents\.env"))
load_dotenv(Path(r"C:\Users\steve\Documents\TruePlatformAI\.env"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen/qwen3-embedding-8b")
BUNDLE_DIR = Path(r"C:\Users\steve\Documents\TrueInfluenceAI\bundles")


def find_latest_bundle():
    bundles = sorted(BUNDLE_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for b in bundles:
        if (b / 'ready.flag').exists():
            return b
    return None


def load_bundle(bp):
    bp = Path(bp)
    data = {}
    for name in ['manifest', 'sources', 'chunks', 'analytics_report', 'channel_metrics', 'voice_profile', 'insights']:
        p = bp / f'{name}.json'
        if p.exists():
            with open(p, 'r', encoding='utf-8') as f:
                data[name] = json.load(f)
        else:
            data[name] = {} if name != 'sources' and name != 'chunks' else []
    return data


# =====================================================================
# LANDING PAGE
# =====================================================================
def build_index(bp, data):
    channel = data['manifest'].get('channel', 'Unknown')
    metrics = data.get('channel_metrics', {})
    voice = data.get('voice_profile', {})
    tone = voice.get('tone', '')
    total_videos = data['manifest'].get('total_videos', 0)
    total_chunks = data['manifest'].get('total_chunks', 0)
    avg_views = metrics.get('channel_avg_views', 0)
    total_views = metrics.get('total_views', 0)
    engagement = metrics.get('channel_engagement_rate', 0)
    topics_count = len(data.get('analytics_report', {}).get('topic_frequency', {}))

    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{channel} — TrueInfluenceAI</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f1117;color:#e0e0e0;min-height:100vh}}
.hero{{text-align:center;padding:60px 24px 40px;background:linear-gradient(135deg,#161822 0%,#1a1d40 50%,#161822 100%);border-bottom:1px solid #2a2d3a}}
.hero h1{{font-size:42px;font-weight:700;color:#fff;margin-bottom:8px}}
.hero h1 span{{color:#6c63ff}}
.hero .sub{{font-size:15px;color:#888;max-width:600px;margin:0 auto 24px;line-height:1.6}}
.stats-row{{display:flex;justify-content:center;gap:32px;flex-wrap:wrap;margin-top:24px}}
.stat{{text-align:center}}
.stat .sv{{font-size:28px;font-weight:700;color:#fff}}
.stat .sl{{font-size:11px;color:#555;text-transform:uppercase;margin-top:2px;letter-spacing:.5px}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;max-width:1000px;margin:48px auto;padding:0 24px}}
.card{{background:#161822;border:1px solid #2a2d3a;border-radius:16px;padding:36px 28px;text-align:center;cursor:pointer;transition:all .2s;text-decoration:none;color:inherit}}
.card:hover{{transform:translateY(-4px);border-color:#6c63ff;box-shadow:0 8px 32px rgba(108,99,255,.15)}}
.card .icon{{font-size:48px;margin-bottom:16px}}
.card h3{{font-size:18px;color:#fff;margin-bottom:8px}}
.card p{{font-size:13px;color:#777;line-height:1.5}}
.card .tag{{display:inline-block;margin-top:14px;padding:4px 14px;border-radius:20px;font-size:11px;font-weight:600;background:#6c63ff22;color:#a29bfe}}
.footer{{text-align:center;padding:40px 24px;color:#333;font-size:11px}}
.footer a{{color:#6c63ff;text-decoration:none}}
.voice-bar{{max-width:700px;margin:0 auto;padding:16px 24px;background:#1a1d2e;border-radius:12px;border:1px solid #2a2d3a;text-align:left;margin-top:28px}}
.voice-bar .vl{{font-size:10px;color:#6c63ff;text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:6px}}
.voice-bar .vt{{font-size:13px;color:#999;line-height:1.5;font-style:italic}}
@media(max-width:700px){{.cards{{grid-template-columns:1fr}}.stats-row{{gap:20px}}}}
</style></head><body>

<div class="hero">
  <h1><span>TrueInfluence</span>AI</h1>
  <div class="sub">Creator Intelligence Platform for <strong style="color:#fff">{channel}</strong></div>
  <div class="stats-row">
    <div class="stat"><div class="sv">{total_videos}</div><div class="sl">Videos Analyzed</div></div>
    <div class="stat"><div class="sv">{total_chunks:,}</div><div class="sl">Content Chunks</div></div>
    <div class="stat"><div class="sv">{avg_views:,}</div><div class="sl">Avg Views</div></div>
    <div class="stat"><div class="sv">{total_views:,}</div><div class="sl">Total Views</div></div>
    <div class="stat"><div class="sv">{engagement:.1f}%</div><div class="sl">Engagement</div></div>
    <div class="stat"><div class="sv">{topics_count}</div><div class="sl">Topics Tracked</div></div>
  </div>
  {f'<div class="voice-bar"><div class="vl">Voice Profile Loaded</div><div class="vt">"{tone[:200]}"</div></div>' if tone else ''}
</div>

<div class="cards">
  <a class="card" href="dashboard.html">
    <div class="icon">📊</div>
    <h3>Content Dashboard</h3>
    <p>Interactive treemap of all topics. Click any topic to drill down into performance, timeline, AI-generated content ideas, and full scripts in {channel}'s voice.</p>
    <span class="tag">Treemap · Drill-Down · AI Strategy</span>
  </a>
  <a class="card" href="analytics.html">
    <div class="icon">🔬</div>
    <h3>Analytics Report</h3>
    <p>Topic performance rankings, rising/declining trends, topic pairings, and data-driven strategic recommendations for future content.</p>
    <span class="tag">Performance · Trends · Recommendations</span>
  </a>
  <a class="card" href="discuss.html">
    <div class="icon">💬</div>
    <h3>Ask {channel}</h3>
    <p>Chat directly with an AI that has absorbed all of {channel}'s content. Get answers in their voice with references to the specific videos where they discussed it.</p>
    <span class="tag">RAG Chat · Voice Clone · Source Links</span>
  </a>
</div>

<div class="footer">
  Powered by <a href="#">TrueInfluenceAI</a> · WinTech Partners · {datetime.now().strftime('%B %Y')}
</div>

</body></html>"""
    out = bp / 'index.html'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  [OK] {out.name}")


# =====================================================================
# ANALYTICS PAGE
# =====================================================================
def build_analytics(bp, data):
    channel = data['manifest'].get('channel', 'Unknown')
    report = data.get('analytics_report', {})
    metrics = data.get('channel_metrics', {})
    insights = data.get('insights', {})
    topic_freq = report.get('topic_frequency', {})
    topic_perf = report.get('topic_performance', {})
    topic_pairs = report.get('topic_pairs', {})
    topic_timeline = report.get('topic_timeline', {})
    recommendations = report.get('recommendations', '')
    channel_avg = metrics.get('channel_avg_views', 0)

    # Build topic table data — use topic_timeline as master (has ALL topics)
    # topic_frequency is capped at 30, so many declining/dormant topics are missing
    all_topics_set = set(topic_freq.keys()) | set(topic_timeline.keys()) | set(topic_perf.keys())
    topics_js = []
    for topic in all_topics_set:
        tl = topic_timeline.get(topic, {})
        r, m, o = tl.get('recent', 0), tl.get('middle', 0), tl.get('older', 0)
        # Use freq count if available, otherwise sum from timeline
        count = topic_freq.get(topic, r + m + o)
        avg_v = topic_perf.get(topic, 0)
        if r > o and r > m:
            trend = 'rising'
        elif o > r and o > m:
            trend = 'declining'
        elif o > 0 and r == 0:
            trend = 'dormant'
        else:
            trend = 'steady'
        ratio = round(avg_v / channel_avg, 2) if channel_avg > 0 else 0
        topics_js.append({'name': topic, 'count': count, 'avg_views': avg_v, 'ratio': ratio,
                          'trend': trend, 'recent': r, 'middle': m, 'older': o})
    # Sort by count descending
    topics_js.sort(key=lambda x: x['count'], reverse=True)

    pairs_js = [{'pair': k, 'count': v} for k, v in sorted(topic_pairs.items(), key=lambda x: x[1], reverse=True)[:15]]

    # --- Insights sections ---
    ai_deep = insights.get('ai_deep_analysis', {})
    contrarian = insights.get('contrarian_content', {})
    title_patterns = insights.get('title_patterns', {})
    engagement = insights.get('engagement_anomalies', {})
    velocity = insights.get('content_velocity', {})
    revivals = insights.get('revival_candidates', [])
    cannibalization = insights.get('topic_cannibalization', [])

    # Build blind spots HTML
    blind_spots_html = ''
    if ai_deep.get('blind_spots'):
        blind_spots_html = ''.join(f'<div class="insight-item"><div class="insight-icon">&#x1F441;</div><div class="insight-text">{b}</div></div>' for b in ai_deep['blind_spots'])

    money_html = ''
    if ai_deep.get('money_left_on_table'):
        money_html = ''.join(f'<div class="insight-item"><div class="insight-icon">&#x1F4B0;</div><div class="insight-text">{m}</div></div>' for m in ai_deep['money_left_on_table'])

    # Title formula
    title_rec = ai_deep.get('title_formula_rec', {})
    title_formula_html = ''
    if isinstance(title_rec, dict) and title_rec.get('formula'):
        examples_html = ''.join(f'<div class="example-title">{ex}</div>' for ex in title_rec.get('examples', []))
        title_formula_html = f'<div class="formula-box"><div class="formula-label">Winning Formula</div><div class="formula-text">{title_rec["formula"]}</div>{examples_html}</div>'
    elif isinstance(title_rec, str):
        title_formula_html = f'<div class="formula-box"><div class="formula-text">{title_rec}</div></div>'

    # Title pattern table
    pattern_rows = ''
    for pname, pdata in title_patterns.items():
        label = pname.replace('_', ' ').title()
        lift = pdata.get('lift_pct', 0)
        count = pdata.get('count', 0)
        avg_v = pdata.get('avg_views', 0)
        lift_color = '#6bcb77' if lift > 50 else ('#ffd93d' if lift > 0 else '#ff6b6b')
        pattern_rows += f'<tr><td style="color:#fff">{label}</td><td>{count}</td><td>{avg_v:,}</td><td style="color:{lift_color};font-weight:700">{lift:+.1f}%</td></tr>'

    # Contrarian section
    contrarian_html = ''
    if contrarian:
        c_avg = contrarian.get('avg_views_contrarian', 0)
        n_avg = contrarian.get('avg_views_conventional', 0)
        c_lift = contrarian.get('lift_pct', 0)
        top_c = contrarian.get('top_contrarian', [])
        top_html = ''.join(f'<div class="video-row"><span class="vr-title">{v["title"]}</span><span class="vr-views">{v["views"]:,}</span></div>' for v in top_c[:5])
        contrarian_html = f"""<div class="big-stat-row">
          <div class="big-stat"><div class="bs-val" style="color:#ff6b6b">{c_avg:,}</div><div class="bs-label">Contrarian Avg Views</div></div>
          <div class="big-stat"><div class="bs-val">{n_avg:,}</div><div class="bs-label">Conventional Avg Views</div></div>
          <div class="big-stat"><div class="bs-val" style="color:#6bcb77">+{c_lift:.0f}%</div><div class="bs-label">Contrarian Lift</div></div>
        </div>
        <div class="sub-label">Top Contrarian Videos</div>{top_html}"""

    # Engagement anomalies
    passion_html = ''
    high_passion = engagement.get('high_passion', [])
    if high_passion:
        avg_cr = engagement.get('channel_avg_comment_rate', 0)
        passion_html = f'<div class="sub-note">Channel avg comment rate: {avg_cr}%</div>'
        for v in high_passion[:5]:
            cr = v.get('comment_rate', 0)
            multiple = round(cr / avg_cr, 1) if avg_cr > 0 else 0
            passion_html += f'<div class="video-row"><span class="vr-title">{v["title"]}</span><span class="vr-badge" style="background:#6c63ff22;color:#a29bfe">{cr}% comments ({multiple}x avg)</span><span class="vr-views">{v["views"]:,} views</span></div>'

    # Velocity
    velocity_html = ''
    if velocity:
        avg_gap = velocity.get('avg_gap_days', 0)
        fast = velocity.get('fast_posting', {})
        normal = velocity.get('normal_posting', {})
        slow = velocity.get('slow_posting', {})
        velocity_html = f"""<div class="big-stat-row">
          <div class="big-stat"><div class="bs-val">{avg_gap}</div><div class="bs-label">Avg Days Between Posts</div></div>
          <div class="big-stat"><div class="bs-val">{normal.get('avg_views', 0):,}</div><div class="bs-label">{normal.get('label', '6-10 days')} ({normal.get('count', 0)} vids)</div></div>
          <div class="big-stat"><div class="bs-val" style="color:#ff6b6b">{slow.get('avg_views', 0):,}</div><div class="bs-label">{slow.get('label', '11+ days')} ({slow.get('count', 0)} vids)</div></div>
        </div>"""
        posting_rec = ai_deep.get('posting_rhythm_rec', '')
        if posting_rec:
            velocity_html += f'<div class="ai-rec">{posting_rec}</div>'

    # Revival candidates
    revival_html = ''
    for rv in revivals[:6]:
        trend_class = rv.get('trend', 'declining')
        revival_html += f'<div class="video-row"><span class="vr-title">{rv["topic"]}</span><span class="trend-badge {trend_class}">{trend_class}</span><span class="vr-badge">{rv["vs_channel"]}x channel avg</span><span class="vr-views">{rv["avg_views"]:,} avg</span></div>'

    # Cannibalization
    cannibal_html = ''
    for cn in cannibalization[:6]:
        cannibal_html += f'<div class="video-row"><span class="vr-title">{cn["topic_a"]} + {cn["topic_b"]}</span><span class="vr-badge" style="background:#ff6b6b22;color:#ff6b6b">{cn["overlap_pct"]}% overlap</span><span class="vr-views">{cn["co_occurrences"]}x paired</span></div>'

    # Big bet
    big_bet = ai_deep.get('one_big_bet', '')

    # Escape recommendations
    recs_html = ''
    if recommendations:
        recs_html = recommendations.replace('**', '').replace('\n', '<br>')

    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{channel} — Analytics | TrueInfluenceAI</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f1117;color:#e0e0e0}}
.header{{padding:14px 24px;background:#161822;border-bottom:1px solid #2a2d3a;display:flex;align-items:center;gap:16px}}
.header a{{color:#6c63ff;text-decoration:none;font-size:13px}}
.header h1{{font-size:18px;color:#fff;flex:1}}
.header h1 span{{color:#6c63ff}}
.container{{max-width:1100px;margin:0 auto;padding:24px}}
.section{{background:#161822;border:1px solid #2a2d3a;border-radius:12px;padding:24px;margin-bottom:24px}}
.section h2{{font-size:14px;color:#6c63ff;text-transform:uppercase;letter-spacing:1px;margin-bottom:16px}}
.section .section-sub{{font-size:12px;color:#555;margin-top:-12px;margin-bottom:16px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
th{{text-align:left;color:#555;font-size:10px;text-transform:uppercase;letter-spacing:.5px;padding:8px 12px;border-bottom:1px solid #2a2d3a}}
td{{padding:10px 12px;border-bottom:1px solid #1a1d2e}}
.trend-badge{{display:inline-block;padding:2px 10px;border-radius:10px;font-size:10px;font-weight:700}}
.trend-badge.rising{{background:#1a3a2a;color:#6bcb77}}
.trend-badge.declining{{background:#3a1a1a;color:#ff6b6b}}
.trend-badge.dormant{{background:#3a3a1a;color:#ffd93d}}
.trend-badge.steady{{background:#1a2a3a;color:#6ba3cb}}
.bar{{height:6px;border-radius:3px;background:#6c63ff;display:inline-block;vertical-align:middle}}
.bar.hot{{background:#ff6b6b}}
.bar.cool{{background:#4a4580}}
.grid2{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}
.grid3{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:24px}}
.pairs-grid{{display:flex;flex-wrap:wrap;gap:8px}}
.pair-chip{{background:#1a1d2e;border:1px solid #2a2d3a;border-radius:8px;padding:8px 14px;font-size:12px}}
.pair-chip b{{color:#fff}}
.pair-chip span{{color:#555;margin-left:4px}}
.recs{{font-size:13px;line-height:1.8;color:#ccc}}
.insight-item{{display:flex;gap:12px;padding:12px 16px;background:#1a1d2e;border-radius:10px;margin-bottom:10px;border-left:3px solid #6c63ff}}
.insight-icon{{font-size:20px;flex-shrink:0}}
.insight-text{{font-size:13px;line-height:1.6;color:#ccc}}
.big-stat-row{{display:flex;gap:16px;margin-bottom:16px}}
.big-stat{{flex:1;text-align:center;background:#1a1d2e;border-radius:10px;padding:16px}}
.bs-val{{font-size:28px;font-weight:700;color:#fff}}
.bs-label{{font-size:10px;color:#555;text-transform:uppercase;margin-top:4px;letter-spacing:.5px}}
.video-row{{display:flex;align-items:center;gap:10px;padding:8px 12px;background:#1a1d2e;border-radius:8px;margin-bottom:6px;font-size:12px}}
.vr-title{{flex:1;color:#ddd}}
.vr-views{{color:#6c63ff;font-weight:600;white-space:nowrap}}
.vr-badge{{display:inline-block;padding:2px 10px;border-radius:10px;font-size:10px;font-weight:600;background:#6c63ff22;color:#a29bfe;white-space:nowrap}}
.sub-label{{font-size:11px;color:#555;text-transform:uppercase;letter-spacing:.5px;margin:12px 0 8px;font-weight:700}}
.sub-note{{font-size:11px;color:#444;margin-bottom:10px;font-style:italic}}
.formula-box{{background:#1a1d40;border:1px solid #6c63ff44;border-radius:10px;padding:16px 20px;margin-bottom:16px}}
.formula-label{{font-size:10px;color:#6c63ff;text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:6px}}
.formula-text{{font-size:16px;color:#fff;font-weight:700;margin-bottom:10px}}
.example-title{{font-size:12px;color:#999;padding:4px 0 4px 12px;border-left:2px solid #6c63ff44;margin:4px 0}}
.ai-rec{{background:#1a1d2e;border-radius:8px;padding:12px 16px;font-size:13px;color:#ccc;line-height:1.6;margin-top:12px;border-left:3px solid #6c63ff}}
.big-bet{{background:linear-gradient(135deg,#1a1d40,#2a1a40);border:1px solid #6c63ff;border-radius:12px;padding:24px;font-size:15px;color:#fff;line-height:1.7;text-align:center}}
.big-bet .bb-label{{font-size:10px;color:#6c63ff;text-transform:uppercase;letter-spacing:2px;font-weight:700;margin-bottom:10px}}
@media(max-width:700px){{.grid2,.grid3{{grid-template-columns:1fr}}.big-stat-row{{flex-direction:column}}}}
</style></head><body>

<div class="header">
  <a href="index.html">&larr; Home</a>
  <h1><span>Analytics</span> — {channel}</h1>
</div>

<div class="container">

{'<div class="section"><div class="big-bet"><div class="bb-label">The One Big Bet</div>' + big_bet + '</div></div>' if big_bet else ''}

{'<div class="grid2"><div class="section"><h2>Blind Spots</h2><div class="section-sub">Things you probably don\'t realize about your own content</div>' + blind_spots_html + '</div><div class="section"><h2>Money Left on the Table</h2><div class="section-sub">Specific opportunities hiding in your data</div>' + money_html + '</div></div>' if blind_spots_html or money_html else ''}

{'<div class="section"><h2>Contrarian vs Conventional — Your Secret Weapon</h2><div class="section-sub">Titles that challenge assumptions massively outperform</div>' + contrarian_html + '</div>' if contrarian_html else ''}

{'<div class="grid2"><div class="section"><h2>Title Formula That Works</h2><div class="section-sub">Based on view lift analysis across all your titles</div>' + title_formula_html + '<table><tr><th>Pattern</th><th>Videos</th><th>Avg Views</th><th>Lift vs Others</th></tr>' + pattern_rows + '</table></div>' if pattern_rows else ''}

{'<div class="section"><h2>Audience Passion Signals</h2><div class="section-sub">Videos where your audience engaged far above normal — they want MORE of this</div>' + passion_html + '</div></div>' if passion_html else ''}

{'<div class="section"><h2>Posting Rhythm</h2><div class="section-sub">How your posting frequency affects performance</div>' + velocity_html + '</div>' if velocity_html else ''}

{'<div class="grid2"><div class="section"><h2>Revival Candidates</h2><div class="section-sub">Topics you stopped covering that your audience loved</div>' + revival_html + '</div>' if revival_html else ''}

{'<div class="section"><h2>Topic Cannibalization</h2><div class="section-sub">Topics that overlap so much they may confuse your audience</div>' + cannibal_html + '</div></div>' if cannibal_html else ''}

<div class="section">
  <h2>Topic Performance Rankings</h2>
  <table>
    <tr><th>Topic</th><th>Videos</th><th>Avg Views</th><th>vs Channel</th><th style="width:120px">Performance</th><th>Trend</th><th>Recent</th><th>Mid</th><th>Older</th></tr>
    {''.join(f"""<tr>
      <td style="color:#fff;font-weight:600">{t['name']}</td>
      <td>{t['count']}</td>
      <td>{t['avg_views']:,}</td>
      <td>{t['ratio']}x</td>
      <td><div class="bar {'hot' if t['ratio']>1.3 else ('cool' if t['ratio']<0.8 else '')}" style="width:{min(100,max(5,t['ratio']*50))}px"></div></td>
      <td><span class="trend-badge {t['trend']}">{t['trend']}</span></td>
      <td>{t['recent']}</td><td>{t['middle']}</td><td>{t['older']}</td>
    </tr>""" for t in topics_js)}
  </table>
</div>

<div class="grid2">
<div class="section">
  <h2>Topic Pairings</h2>
  <div class="pairs-grid">
    {''.join(f'<div class="pair-chip"><b>{p["pair"]}</b> <span>&times;{p["count"]}</span></div>' for p in pairs_js)}
  </div>
</div>

<div class="section">
  <h2>Quick Stats</h2>
  <table>
    <tr><td style="color:#888">Videos Analyzed</td><td style="color:#fff;font-weight:700">{report.get('videos_analyzed', 0)}</td></tr>
    <tr><td style="color:#888">Channel Avg Views</td><td style="color:#fff;font-weight:700">{channel_avg:,}</td></tr>
    <tr><td style="color:#888">Topics Tracked</td><td style="color:#fff;font-weight:700">{len(topic_freq)}</td></tr>
    <tr><td style="color:#888">Unique Pairings</td><td style="color:#fff;font-weight:700">{len(topic_pairs)}</td></tr>
    <tr><td style="color:#888">Rising Topics</td><td style="color:#6bcb77;font-weight:700">{sum(1 for t in topics_js if t['trend']=='rising')}</td></tr>
    <tr><td style="color:#888">Declining Topics</td><td style="color:#ff6b6b;font-weight:700">{sum(1 for t in topics_js if t['trend']=='declining')}</td></tr>
  </table>
</div>
</div>

{f'<div class="section"><h2>Strategic Recommendations</h2><div class="recs">{recs_html}</div></div>' if recs_html else ''}

</div>
</body></html>"""
    out = bp / 'analytics.html'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  [OK] {out.name}")


# =====================================================================
# DISCUSSION PAGE
# =====================================================================
def build_discuss(bp, data):
    channel = data['manifest'].get('channel', 'Unknown')
    voice = data.get('voice_profile', {})
    sources = data['sources']
    chunks = data['chunks']

    # Build source lookup for JS — include published_at for recency weighting
    source_map = {}
    for s in sources:
        source_map[s['source_id']] = {
            'title': s.get('title', 'Unknown'),
            'url': s.get('url', ''),
            'views': s.get('views', 0),
            'published_at': s.get('published_at', ''),
        }
    
    # Also store source_id -> published_at in chunks for recency boosting
    source_dates = {}
    for s in sources:
        source_dates[s['source_id']] = s.get('published_at', '')

    # Strip embeddings from chunks for the page (too large) — we'll send text to the API for embedding at query time
    # Instead, we precompute and embed the chunk texts + source_ids so the page can do RAG via API
    # Actually, the chunks file has embeddings already. We need to load them for in-browser cosine search.
    # But 571 chunks × 1536-dim embeddings = huge. Let's use the API approach like chat.py does.

    # For the discussion page, we'll:
    # 1. User types question
    # 2. JS calls OpenRouter embeddings API to get query embedding
    # 3. JS does cosine similarity against preloaded embeddings
    # 4. JS sends top-5 chunks + voice profile to OpenRouter chat API
    # 5. Display answer + source videos (up to 5, deduplicated)

    # But loading all embeddings in browser is heavy. Let's check size.
    valid_chunks = [c for c in chunks if c.get('embedding')]
    emb_dim = len(valid_chunks[0]['embedding']) if valid_chunks else 0
    print(f"    {len(valid_chunks)} chunks x {emb_dim}-dim embeddings")

    # Build lightweight chunks array for JS (text + source_id + embedding + published date)
    # We'll use float32 precision truncated to save space
    js_chunks = []
    for c in valid_chunks:
        js_chunks.append({
            'text': c['text'][:500],
            'source_id': c['source_id'],
            'pub': source_dates.get(c['source_id'], ''),
            'emb': [round(x, 5) for x in c['embedding']],
        })

    system_prompt = voice.get('system_prompt', f'You are {channel}. Answer questions based on your content.')

    html = f"""<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Ask {channel} | TrueInfluenceAI</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f1117;color:#e0e0e0;height:100vh;display:flex;flex-direction:column}}
.header{{padding:12px 24px;background:#161822;border-bottom:1px solid #2a2d3a;display:flex;align-items:center;gap:16px;flex-shrink:0}}
.header a{{color:#6c63ff;text-decoration:none;font-size:13px}}
.header h1{{font-size:18px;color:#fff;flex:1}}
.header h1 span{{color:#6c63ff}}
.chat-area{{flex:1;overflow-y:auto;padding:24px;max-width:800px;width:100%;margin:0 auto}}
.msg{{margin-bottom:20px;display:flex;gap:12px}}
.msg.user{{flex-direction:row-reverse}}
.msg .avatar{{width:36px;height:36px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:18px;flex-shrink:0}}
.msg.user .avatar{{background:#6c63ff33}}
.msg.bot .avatar{{background:#2a2d3a}}
.msg .bubble{{max-width:85%;padding:14px 18px;border-radius:16px;font-size:14px;line-height:1.65}}
.msg.user .bubble{{background:#6c63ff;color:#fff;border-bottom-right-radius:4px}}
.msg.bot .bubble{{background:#1a1d2e;border:1px solid #2a2d3a;color:#ccc;border-bottom-left-radius:4px}}
.sources{{margin-top:12px;padding-top:10px;border-top:1px solid #2a2d3a}}
.sources .src-label{{font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;font-weight:700}}
.src-item{{display:flex;align-items:center;gap:8px;padding:6px 10px;margin:4px 0;background:#12141f;border-radius:8px;cursor:pointer;transition:background .15s;text-decoration:none;color:inherit}}
.src-item:hover{{background:#22263a}}
.src-item .src-title{{font-size:12px;color:#ddd;flex:1}}
.src-item .src-views{{font-size:10px;color:#6c63ff;white-space:nowrap}}
.src-item .src-icon{{font-size:14px}}
.input-area{{flex-shrink:0;padding:16px 24px;background:#161822;border-top:1px solid #2a2d3a}}
.input-row{{max-width:800px;margin:0 auto;display:flex;gap:10px}}
.input-row input{{flex:1;padding:14px 18px;background:#1a1d2e;border:1px solid #2a2d3a;border-radius:12px;color:#fff;font-size:14px;outline:none;transition:border-color .15s}}
.input-row input:focus{{border-color:#6c63ff}}
.input-row input::placeholder{{color:#444}}
.input-row button{{padding:14px 24px;background:#6c63ff;color:#fff;border:none;border-radius:12px;font-size:14px;font-weight:600;cursor:pointer;transition:background .15s}}
.input-row button:hover{{background:#7c73ff}}
.input-row button:disabled{{opacity:.5;cursor:default}}
.typing{{display:flex;gap:4px;padding:8px 0}}
.typing span{{width:6px;height:6px;background:#555;border-radius:50%;animation:bounce .6s infinite alternate}}
.typing span:nth-child(2){{animation-delay:.2s}}
.typing span:nth-child(3){{animation-delay:.4s}}
@keyframes bounce{{to{{opacity:.2;transform:translateY(-4px)}}}}
.welcome{{text-align:center;padding:60px 24px;color:#555}}
.welcome h2{{color:#888;font-size:20px;margin-bottom:8px}}
.welcome p{{font-size:13px;max-width:500px;margin:0 auto;line-height:1.6}}
.welcome .examples{{margin-top:24px;display:flex;flex-wrap:wrap;gap:8px;justify-content:center}}
.welcome .ex{{padding:8px 16px;background:#1a1d2e;border:1px solid #2a2d3a;border-radius:20px;font-size:12px;color:#999;cursor:pointer;transition:all .15s}}
.welcome .ex:hover{{border-color:#6c63ff;color:#fff}}
</style></head><body>

<div class="header">
  <a href="index.html">&larr; Home</a>
  <h1>Ask <span>{channel}</span></h1>
</div>

<div class="chat-area" id="chatArea">
  <div class="welcome" id="welcome">
    <h2>Chat with {channel}</h2>
    <p>Ask anything about their content. Answers come directly from {channel}'s videos, written in their voice, with links to where they discussed it.</p>
    <div class="examples">
      <div class="ex" onclick="askExample(this)">How do I monetize a small YouTube channel?</div>
      <div class="ex" onclick="askExample(this)">What's your advice on building online courses?</div>
      <div class="ex" onclick="askExample(this)">How important is SEO for YouTube growth?</div>
    </div>
  </div>
</div>

<div class="input-area">
  <div class="input-row">
    <input type="text" id="userInput" placeholder="Ask {channel} anything..." onkeydown="if(event.key==='Enter')sendMessage()">
    <button id="sendBtn" onclick="sendMessage()">Send</button>
  </div>
</div>

<script>
const CHANNEL = {json.dumps(channel)};
const API_KEY = {json.dumps(OPENROUTER_API_KEY)};
const EMB_MODEL = {json.dumps(EMBEDDING_MODEL)};
const CHAT_MODEL = "google/gemini-2.5-flash-lite:online";
const SOURCES = {json.dumps(source_map)};
const SYSTEM_PROMPT = {json.dumps(system_prompt)};

// Preloaded chunks with embeddings
const CHUNKS = {json.dumps(js_chunks)};

// Precompute norms for cosine similarity
const NORMS = new Float64Array(CHUNKS.length);
for (let i = 0; i < CHUNKS.length; i++) {{
  let sum = 0;
  const emb = CHUNKS[i].emb;
  for (let j = 0; j < emb.length; j++) sum += emb[j] * emb[j];
  NORMS[i] = Math.sqrt(sum) || 1;
}}

let history = [];

function fmtViews(v) {{ if(v>=1e6) return (v/1e6).toFixed(1)+'M'; if(v>=1e3) return (v/1e3).toFixed(0)+'k'; return v.toString(); }}

function askExample(el) {{
  document.getElementById('userInput').value = el.textContent;
  sendMessage();
}}

async function sendMessage() {{
  const input = document.getElementById('userInput');
  const text = input.value.trim();
  if (!text) return;

  const welcome = document.getElementById('welcome');
  if (welcome) welcome.remove();

  appendMsg('user', text);
  input.value = '';
  input.disabled = true;
  document.getElementById('sendBtn').disabled = true;

  const typingId = showTyping();

  try {{
    // Step 1: Embed the query
    const qEmb = await embedQuery(text);
    if (!qEmb) throw new Error('Embedding failed');

    // Step 2: Cosine similarity search
    const results = searchChunks(qEmb, 8);

    // Step 3: Deduplicate by source_id, keep top 5
    const seen = new Set();
    const topResults = [];
    for (const r of results) {{
      if (!seen.has(r.source_id)) {{
        seen.add(r.source_id);
        topResults.push(r);
      }}
      if (topResults.length >= 5) break;
    }}

    // Step 4: Build context and call chat API
    const contextParts = topResults.map((r, i) => {{
      const src = SOURCES[r.source_id] || {{}};
      return `VIDEO ${{i+1}}: "${{src.title || 'Unknown'}}"\\nKEY POINTS: ${{r.text.substring(0, 400)}}`;
    }});

    const messages = [
      {{ role: "system", content: `You ARE ${{CHANNEL}}. Respond in first person as if you are the creator speaking directly to a fan or follower.

RULES:
1. Restate your ideas in fresh words — never repeat your transcript word-for-word.
2. Never fabricate calls-to-action, links, comment prompts, or offers you didn't actually make.
3. End each response with 1-3 concrete next steps the user can take right now.
4. Keep it warm, direct, and actionable.

${{SYSTEM_PROMPT}}` }}
    ];

    // Add conversation history (last 6 messages)
    for (const h of history.slice(-6)) messages.push(h);

    messages.push({{
      role: "user",
      content: `REFERENCE NOTES from ${{CHANNEL}}'s videos (synthesize, do NOT copy):
${{contextParts.join('\\n\\n')}}

USER QUESTION: ${{text}}

Answer in your own words. Give 1-3 actionable next steps. Never copy the source text.`
    }});

    const resp = await fetch('https://openrouter.ai/api/v1/chat/completions', {{
      method: 'POST',
      headers: {{ 'Authorization': `Bearer ${{API_KEY}}`, 'Content-Type': 'application/json' }},
      body: JSON.stringify({{ model: CHAT_MODEL, messages, max_tokens: 1000, temperature: 0.3 }})
    }});

    removeTyping(typingId);

    if (!resp.ok) throw new Error('Chat API ' + resp.status);

    const data = await resp.json();
    const answer = data.choices?.[0]?.message?.content || 'No response.';

    // Build source references
    const sourceRefs = topResults.map(r => {{
      const src = SOURCES[r.source_id] || {{}};
      return {{ title: src.title || 'Unknown', url: src.url || '', views: src.views || 0 }};
    }}).filter(s => s.url);

    appendBotMsg(answer, sourceRefs);

    history.push({{ role: "user", content: text }});
    history.push({{ role: "assistant", content: answer }});

  }} catch(e) {{
    removeTyping(typingId);
    appendMsg('bot', 'Sorry, something went wrong: ' + e.message);
  }}

  input.disabled = false;
  document.getElementById('sendBtn').disabled = false;
  input.focus();
}}

async function embedQuery(text) {{
  const resp = await fetch('https://openrouter.ai/api/v1/embeddings', {{
    method: 'POST',
    headers: {{ 'Authorization': `Bearer ${{API_KEY}}`, 'Content-Type': 'application/json' }},
    body: JSON.stringify({{ model: EMB_MODEL, input: text.substring(0, 8000) }})
  }});
  if (!resp.ok) return null;
  const data = await resp.json();
  return data.data?.[0]?.embedding || null;
}}

// Recency weight: matches recency.py logic
function recencyWeight(pubDate) {{
  if (!pubDate) return 0.3;
  const pub = new Date(pubDate);
  if (isNaN(pub.getTime())) return 0.3;
  const now = new Date();
  const days = Math.floor((now - pub) / (1000*60*60*24));
  if (days < 0) return 1.0;
  if (days <= 30) return 1.0;
  if (days <= 90) return 1.0 - (days-30)/60 * 0.15;
  if (days <= 180) return 0.85 - (days-90)/90 * 0.20;
  if (days <= 365) return 0.65 - (days-180)/185 * 0.25;
  const beyond = days - 365;
  return Math.max(0.20, 0.40 - beyond/365 * 0.20);
}}

function searchChunks(qEmb, topK) {{
  // Normalize query
  let qNorm = 0;
  for (let i = 0; i < qEmb.length; i++) qNorm += qEmb[i] * qEmb[i];
  qNorm = Math.sqrt(qNorm) || 1;

  const scores = new Float64Array(CHUNKS.length);
  for (let i = 0; i < CHUNKS.length; i++) {{
    let dot = 0;
    const emb = CHUNKS[i].emb;
    for (let j = 0; j < emb.length; j++) dot += emb[j] * qEmb[j];
    const rawScore = dot / (NORMS[i] * qNorm);
    // Apply recency boost — recent content gets priority
    const weight = recencyWeight(CHUNKS[i].pub);
    scores[i] = rawScore * weight;
  }}

  // Get top-K indices
  const indices = Array.from({{length: CHUNKS.length}}, (_, i) => i);
  indices.sort((a, b) => scores[b] - scores[a]);

  return indices.slice(0, topK).map(i => ({{
    text: CHUNKS[i].text,
    source_id: CHUNKS[i].source_id,
    score: scores[i]
  }}));
}}

function appendMsg(type, text) {{
  const area = document.getElementById('chatArea');
  const div = document.createElement('div');
  div.className = 'msg ' + type;
  div.innerHTML = `
    <div class="avatar">${{type === 'user' ? '👤' : '🎙️'}}</div>
    <div class="bubble">${{text.replace(/\\n/g, '<br>')}}</div>
  `;
  area.appendChild(div);
  area.scrollTop = area.scrollHeight;
}}

function appendBotMsg(text, sources) {{
  const area = document.getElementById('chatArea');
  const div = document.createElement('div');
  div.className = 'msg bot';

  let sourcesHtml = '';
  if (sources && sources.length > 0) {{
    sourcesHtml = `<div class="sources">
      <div class="src-label">Where I talked about this:</div>
      ${{sources.map(s => `
        <a class="src-item" href="${{s.url}}" target="_blank" rel="noopener">
          <span class="src-icon">📹</span>
          <span class="src-title">${{s.title}}</span>
          ${{s.views > 0 ? `<span class="src-views">${{fmtViews(s.views)}} views</span>` : ''}}
        </a>
      `).join('')}}
    </div>`;
  }}

  div.innerHTML = `
    <div class="avatar">🎙️</div>
    <div class="bubble">
      ${{text.replace(/\\*\\*(.+?)\\*\\*/g, '<strong>$1</strong>').replace(/\\n/g, '<br>')}}
      ${{sourcesHtml}}
    </div>
  `;
  area.appendChild(div);
  area.scrollTop = area.scrollHeight;
}}

function showTyping() {{
  const area = document.getElementById('chatArea');
  const id = 'typing_' + Date.now();
  const div = document.createElement('div');
  div.className = 'msg bot';
  div.id = id;
  div.innerHTML = `<div class="avatar">🎙️</div><div class="bubble"><div class="typing"><span></span><span></span><span></span></div></div>`;
  area.appendChild(div);
  area.scrollTop = area.scrollHeight;
  return id;
}}

function removeTyping(id) {{
  const el = document.getElementById(id);
  if (el) el.remove();
}}
</script>
</body></html>"""

    out = bp / 'discuss.html'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  [OK] {out.name}")


# =====================================================================
# MAIN
# =====================================================================
def main():
    if len(sys.argv) > 1:
        bp = Path(sys.argv[1])
        if not bp.is_absolute():
            bp = BUNDLE_DIR / bp
    else:
        bp = find_latest_bundle()

    if not bp or not bp.exists():
        print("[!] No bundle found.")
        sys.exit(1)

    print(f"[*] Building pages for: {bp.name}")
    data = load_bundle(bp)

    build_index(bp, data)
    build_analytics(bp, data)
    build_discuss(bp, data)

    print(f"\n[OK] All pages saved to {bp}")
    print(f"     Open: {bp / 'index.html'}")

    import webbrowser
    webbrowser.open(str(bp / 'index.html'))


if __name__ == '__main__':
    main()
