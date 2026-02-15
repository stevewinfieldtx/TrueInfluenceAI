"""
TrueInfluenceAI - Actionable Intelligence Page Builder
=======================================================
Replaces the old analytics.html with an ACTION-ORIENTED page.
No more tables of numbers. Every section answers ONE question:
  "What should I do next?"

Reads: insights.json, analytics_report.json, channel_metrics.json, sources.json
Writes: analytics.html (overwrites the old one)

Usage:
  py build_actionable.py
  py build_actionable.py SunnyLenarduzzi_20260211_164612
"""

import sys, json, os
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv(Path(r"C:\Users\steve\Documents\.env"))
load_dotenv(Path(r"C:\Users\steve\Documents\TruePlatformAI\.env"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
BUNDLE_DIR = Path(r"C:\Users\steve\Documents\TrueInfluenceAI\bundles")


def find_latest_bundle():
    bundles = sorted(BUNDLE_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for b in bundles:
        if (b / 'ready.flag').exists():
            return b
    return None


def load_json(bp, name):
    p = bp / f'{name}.json'
    if p.exists():
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def esc(s):
    """Escape HTML"""
    if not isinstance(s, str):
        s = str(s)
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')


def fmt_views(v):
    if v >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v/1_000:.0f}k"
    return f"{v:,}"


def build_analytics(bp):
    insights = load_json(bp, 'insights')
    report = load_json(bp, 'analytics_report')
    metrics = load_json(bp, 'channel_metrics')
    manifest = load_json(bp, 'manifest')
    sources_list = load_json(bp, 'sources') or []
    voice_profile = load_json(bp, 'voice_profile')

    channel = manifest.get('channel', 'Unknown')
    channel_avg = metrics.get('channel_avg_views', 0)
    total_videos = manifest.get('total_videos', 0)
    total_views = metrics.get('total_views', 0)
    engagement_rate = metrics.get('channel_engagement_rate', 0)

    ai_deep = insights.get('ai_deep_analysis', {})
    contrarian = insights.get('contrarian_content', {})
    title_patterns = insights.get('title_patterns', {})
    engagement = insights.get('engagement_anomalies', {})
    velocity = insights.get('content_velocity', {})
    revivals = insights.get('revival_candidates', [])
    cannibalization = insights.get('topic_cannibalization', [])
    topic_timeline = report.get('topic_timeline', {})
    topic_perf = report.get('topic_performance', {})
    topic_freq = report.get('topic_frequency', {})
    topic_pairs = report.get('topic_pairs', {})

    # ─── Compute derived data ────────────────────────────────────────

    # Rising topics with performance
    rising_topics = []
    for topic, tl in topic_timeline.items():
        r, m, o = tl.get('recent', 0), tl.get('middle', 0), tl.get('older', 0)
        if r > o and r > m and (r + m + o) >= 2:
            avg_v = topic_perf.get(topic, 0)
            rising_topics.append({
                'name': topic, 'recent': r, 'middle': m, 'older': o,
                'avg_views': avg_v,
                'vs_channel': round(avg_v / channel_avg, 2) if channel_avg > 0 else 0,
            })
    rising_topics.sort(key=lambda x: x['avg_views'], reverse=True)

    # Declining topics
    declining_topics = []
    for topic, tl in topic_timeline.items():
        r, m, o = tl.get('recent', 0), tl.get('middle', 0), tl.get('older', 0)
        if o > r and o > m and (r + m + o) >= 2:
            avg_v = topic_perf.get(topic, 0)
            declining_topics.append({
                'name': topic, 'recent': r, 'middle': m, 'older': o,
                'avg_views': avg_v,
            })
    declining_topics.sort(key=lambda x: x['avg_views'], reverse=True)

    # Untapped combos: pairs where each topic performs well individually
    # but the combination hasn't been explored much
    untapped_combos = []
    existing_pairs = set(topic_pairs.keys())
    top_topics = sorted(topic_perf.items(), key=lambda x: x[1], reverse=True)[:15]
    for i, (t1, v1) in enumerate(top_topics):
        for t2, v2 in top_topics[i+1:]:
            pair_key1 = f"{t1} + {t2}"
            pair_key2 = f"{t2} + {t1}"
            co_count = topic_pairs.get(pair_key1, 0) or topic_pairs.get(pair_key2, 0)
            if co_count <= 1 and v1 > channel_avg * 0.8 and v2 > channel_avg * 0.8:
                untapped_combos.append({
                    'topic_a': t1, 'topic_b': t2,
                    'views_a': v1, 'views_b': v2,
                    'co_count': co_count,
                })
    untapped_combos.sort(key=lambda x: x['views_a'] + x['views_b'], reverse=True)

    # Evergreen decay: old content with high views that may need updating
    evergreen_decay = []
    if sources_list:
        now = datetime.utcnow()
        for s in sources_list:
            pub = s.get('published_at', '')
            views = s.get('views', 0)
            if pub and views > channel_avg:
                try:
                    dt = datetime.fromisoformat(pub.replace('Z', '+00:00')).replace(tzinfo=None)
                    age_days = (now - dt).days
                    if age_days > 180:  # older than 6 months
                        evergreen_decay.append({
                            'title': s.get('title', ''),
                            'views': views,
                            'age_days': age_days,
                            'age_label': f"{age_days // 30} months ago",
                            'published_at': pub[:10],
                        })
                except:
                    pass
        evergreen_decay.sort(key=lambda x: x['views'], reverse=True)

    # High-passion videos (audience is BEGGING for more)
    high_passion = engagement.get('high_passion', [])

    # ─── Build HTML ──────────────────────────────────────────────────

    # Big Bet section
    big_bet = ai_deep.get('one_big_bet', '')
    big_bet_html = ''
    if big_bet:
        big_bet_html = f'''
    <div class="big-bet">
        <div class="bb-eyebrow">🎯 THE ONE BIG BET</div>
        <div class="bb-text">{esc(big_bet)}</div>
    </div>'''

    # Section 1: What's Working NOW
    working_now_cards = ''
    for t in rising_topics[:6]:
        perf_class = 'hot' if t['vs_channel'] > 1.3 else ('warm' if t['vs_channel'] > 0.8 else 'cool')
        working_now_cards += f'''
        <div class="action-card">
            <div class="ac-header">
                <span class="ac-topic">{esc(t["name"])}</span>
                <span class="ac-badge rising">▲ Rising</span>
            </div>
            <div class="ac-stat-row">
                <div class="ac-stat"><div class="ac-stat-val">{fmt_views(t["avg_views"])}</div><div class="ac-stat-label">Avg Views</div></div>
                <div class="ac-stat"><div class="ac-stat-val {perf_class}">{t["vs_channel"]}x</div><div class="ac-stat-label">vs Channel</div></div>
                <div class="ac-stat"><div class="ac-stat-val">{t["recent"]}/{t["middle"]}/{t["older"]}</div><div class="ac-stat-label">R/M/O</div></div>
            </div>
            <div class="ac-action">✅ Keep making this. Audience demand is growing.</div>
            <button class="write-btn" onclick="writeIt(this)" data-type="rising" data-topic="{esc(t['name'])}" data-views="{t['avg_views']}" data-ratio="{t['vs_channel']}">✍️ Write It For Me</button>
        </div>'''

    # Section 2: Resurrection Candidates
    revival_cards = ''
    for rv in revivals[:6]:
        revival_cards += f'''
        <div class="action-card">
            <div class="ac-header">
                <span class="ac-topic">{esc(rv["topic"])}</span>
                <span class="ac-badge dormant">💤 {rv["trend"].title()}</span>
            </div>
            <div class="ac-stat-row">
                <div class="ac-stat"><div class="ac-stat-val">{fmt_views(rv["avg_views"])}</div><div class="ac-stat-label">Avg Views</div></div>
                <div class="ac-stat"><div class="ac-stat-val hot">{rv["vs_channel"]}x</div><div class="ac-stat-label">vs Channel</div></div>
            </div>
            <div class="ac-action">🔄 This topic PROVED demand ({fmt_views(rv["avg_views"])} avg) but you stopped covering it. Bring it back with a fresh angle.</div>
            <button class="write-btn" onclick="writeIt(this)" data-type="revival" data-topic="{esc(rv['topic'])}" data-views="{rv['avg_views']}" data-ratio="{rv['vs_channel']}">✍️ Write It For Me</button>
        </div>'''

    # Section 3: Evergreen Decay (Update These)
    evergreen_cards = ''
    for ev in evergreen_decay[:6]:
        evergreen_cards += f'''
        <div class="action-card">
            <div class="ac-header">
                <span class="ac-topic">{esc(ev["title"][:60])}</span>
                <span class="ac-badge stale">📅 {ev["age_label"]}</span>
            </div>
            <div class="ac-stat-row">
                <div class="ac-stat"><div class="ac-stat-val">{fmt_views(ev["views"])}</div><div class="ac-stat-label">Views</div></div>
                <div class="ac-stat"><div class="ac-stat-val">{ev["published_at"]}</div><div class="ac-stat-label">Published</div></div>
            </div>
            <div class="ac-action">📝 High-performing but aging. Update with current info for a near-guaranteed win — the audience already proved they want this.</div>
            <button class="write-btn" onclick="writeIt(this)" data-type="evergreen" data-topic="{esc(ev['title'][:60])}" data-views="{ev['views']}">✍️ Write It For Me</button>
        </div>'''

    # Section 4: Topic Combinations to Try
    combo_cards = ''
    for cb in untapped_combos[:6]:
        combo_cards += f'''
        <div class="action-card">
            <div class="ac-header">
                <span class="ac-topic">{esc(cb["topic_a"])} + {esc(cb["topic_b"])}</span>
                <span class="ac-badge new">🆕 Untapped</span>
            </div>
            <div class="ac-stat-row">
                <div class="ac-stat"><div class="ac-stat-val">{fmt_views(cb["views_a"])}</div><div class="ac-stat-label">{esc(cb["topic_a"][:15])}</div></div>
                <div class="ac-stat"><div class="ac-stat-val">{fmt_views(cb["views_b"])}</div><div class="ac-stat-label">{esc(cb["topic_b"][:15])}</div></div>
                <div class="ac-stat"><div class="ac-stat-val">{cb["co_count"]}</div><div class="ac-stat-label">Times Combined</div></div>
            </div>
            <div class="ac-action">🧪 Both topics perform well independently but you've barely combined them. Test a video that blends both angles.</div>
            <button class="write-btn" onclick="writeIt(this)" data-type="combo" data-topic="{esc(cb['topic_a'])} + {esc(cb['topic_b'])}" data-views="{cb['views_a']}">✍️ Write It For Me</button>
        </div>'''

    # Section 5: Audience Passion Signals
    passion_cards = ''
    avg_cr = engagement.get('channel_avg_comment_rate', 0)
    for hp in high_passion[:5]:
        cr = hp.get('comment_rate', 0)
        multiple = round(cr / avg_cr, 1) if avg_cr > 0 else 0
        passion_cards += f'''
        <div class="action-card compact">
            <div class="ac-header">
                <span class="ac-topic">{esc(hp["title"][:55])}</span>
                <span class="ac-badge passion">🔥 {multiple}x comments</span>
            </div>
            <div class="ac-stat-row">
                <div class="ac-stat"><div class="ac-stat-val">{fmt_views(hp["views"])}</div><div class="ac-stat-label">Views</div></div>
                <div class="ac-stat"><div class="ac-stat-val">{hp["engagement_rate"]}%</div><div class="ac-stat-label">Engagement</div></div>
                <div class="ac-stat"><div class="ac-stat-val">{cr}%</div><div class="ac-stat-label">Comment Rate</div></div>
            </div>
            <div class="ac-action">💬 Your audience is TALKING about this. High comment rate = strong emotional connection. Mine the comments for follow-up topics.</div>
            <button class="write-btn" onclick="writeIt(this)" data-type="passion" data-topic="{esc(hp['title'][:55])}" data-views="{hp['views']}">✍️ Write It For Me</button>
        </div>'''

    # Section 6: Contrarian Edge
    contrarian_html = ''
    if contrarian:
        c_avg = contrarian.get('avg_views_contrarian', 0)
        n_avg = contrarian.get('avg_views_conventional', 0)
        c_lift = contrarian.get('lift_pct', 0)
        top_c = contrarian.get('top_contrarian', [])
        top_items = ''
        for v in top_c[:5]:
            top_items += f'''
            <div class="contrarian-item">
                <span class="ci-title">{esc(v["title"])}</span>
                <span class="ci-views">{fmt_views(v["views"])}</span>
            </div>'''

        contrarian_html = f'''
    <div class="section">
        <div class="section-icon">⚡</div>
        <h2>Your Contrarian Edge</h2>
        <p class="section-desc">Titles that challenge assumptions massively outperform your conventional content.</p>
        <div class="mega-stat-row">
            <div class="mega-stat">
                <div class="ms-val hot">{fmt_views(c_avg)}</div>
                <div class="ms-label">Contrarian Avg</div>
            </div>
            <div class="mega-stat">
                <div class="ms-val dim">{fmt_views(n_avg)}</div>
                <div class="ms-label">Conventional Avg</div>
            </div>
            <div class="mega-stat">
                <div class="ms-val green">+{c_lift:.0f}%</div>
                <div class="ms-label">Contrarian Lift</div>
            </div>
        </div>
        <div class="sub-label">Top Contrarian Videos</div>
        {top_items}
        <div class="ac-action" style="margin-top:16px">🎯 Lean into the "anti-guru" positioning. Your audience rewards you for challenging conventional wisdom.</div>
    </div>'''

    # Section 7: Title Formula
    title_rec = ai_deep.get('title_formula_rec', {})
    title_html = ''
    if title_rec:
        if isinstance(title_rec, dict):
            formula = title_rec.get('formula', '')
            examples = title_rec.get('examples', [])
        else:
            formula = str(title_rec)
            examples = []
        
        examples_html = ''.join(f'<div class="formula-example">"{esc(ex)}"</div>' for ex in examples[:3])
        
        # Add top pattern data
        patterns_html = ''
        sorted_patterns = sorted(title_patterns.items(), key=lambda x: x[1].get('lift_pct', 0), reverse=True)
        for pname, pdata in sorted_patterns[:5]:
            lift = pdata.get('lift_pct', 0)
            count = pdata.get('count', 0)
            avg_v = pdata.get('avg_views', 0)
            lift_color = '#6bcb77' if lift > 50 else ('#ffd93d' if lift > 0 else '#ff6b6b')
            label = pname.replace('_', ' ').title()
            patterns_html += f'''
            <div class="pattern-row">
                <span class="pr-name">{esc(label)}</span>
                <span class="pr-count">{count} videos</span>
                <span class="pr-views">{fmt_views(avg_v)} avg</span>
                <span class="pr-lift" style="color:{lift_color}">{lift:+.0f}%</span>
            </div>'''

        title_html = f'''
    <div class="section">
        <div class="section-icon">✍️</div>
        <h2>Title Intelligence</h2>
        <p class="section-desc">Which title formulas drive the most views for YOUR audience?</p>
        <div class="formula-box">
            <div class="formula-label">Winning Formula</div>
            <div class="formula-text">{esc(formula)}</div>
            {examples_html}
        </div>
        <div class="sub-label">All Title Patterns Ranked by View Lift</div>
        {patterns_html}
    </div>'''

    # Section 8: Blind Spots & Money Left on Table
    blind_spots = ai_deep.get('blind_spots', [])
    money = ai_deep.get('money_left_on_table', [])
    
    insights_cards = ''
    for bs in blind_spots:
        insights_cards += f'''
        <div class="insight-card blind">
            <div class="ic-icon">👁️</div>
            <div class="ic-label">Blind Spot</div>
            <div class="ic-text">{esc(bs)}</div>
        </div>'''
    for m in money:
        insights_cards += f'''
        <div class="insight-card money">
            <div class="ic-icon">💰</div>
            <div class="ic-label">Money on the Table</div>
            <div class="ic-text">{esc(m)}</div>
        </div>'''

    # Section 9: Cannibalization warnings
    cannibal_html = ''
    if cannibalization:
        cannibal_items = ''
        for cn in cannibalization[:5]:
            cannibal_items += f'''
            <div class="cannibal-item">
                <span class="cn-pair">{esc(cn["topic_a"])} ↔ {esc(cn["topic_b"])}</span>
                <span class="cn-overlap" style="color:#ff6b6b">{cn["overlap_pct"]}% overlap</span>
                <span class="cn-count">{cn["co_occurrences"]}x paired</span>
            </div>'''
        cannibal_html = f'''
    <div class="section">
        <div class="section-icon">⚠️</div>
        <h2>Topic Cannibalization</h2>
        <p class="section-desc">These topics overlap so much your audience may see them as the same thing. Differentiate or consolidate.</p>
        {cannibal_items}
    </div>'''

    # Section 10: Posting Rhythm
    rhythm_html = ''
    if velocity:
        rhythm_rec = ai_deep.get('posting_rhythm_rec', '')
        avg_gap = velocity.get('avg_gap_days', 0)
        normal = velocity.get('normal_posting', {})
        slow = velocity.get('slow_posting', {})
        fast = velocity.get('fast_posting', {})
        
        rhythm_html = f'''
    <div class="section">
        <div class="section-icon">⏱️</div>
        <h2>Posting Rhythm</h2>
        <p class="section-desc">How your posting frequency affects performance.</p>
        <div class="mega-stat-row">
            <div class="mega-stat"><div class="ms-val">{avg_gap}</div><div class="ms-label">Avg Days Between Posts</div></div>
            <div class="mega-stat"><div class="ms-val">{fmt_views(normal.get("avg_views", 0))}</div><div class="ms-label">{normal.get("label", "6-10 days")} ({normal.get("count", 0)} vids)</div></div>
            <div class="mega-stat"><div class="ms-val dim">{fmt_views(slow.get("avg_views", 0))}</div><div class="ms-label">{slow.get("label", "11+ days")} ({slow.get("count", 0)} vids)</div></div>
        </div>
        {f'<div class="ac-action">{esc(rhythm_rec)}</div>' if rhythm_rec else ''}
    </div>'''

    # ─── Assemble Full Page ──────────────────────────────────────────

    html = f'''<!DOCTYPE html>
<html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{esc(channel)} — Content Intelligence | TrueInfluenceAI</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f1117;color:#e0e0e0;line-height:1.5}}

/* Header */
.header{{padding:14px 24px;background:#161822;border-bottom:1px solid #2a2d3a;display:flex;align-items:center;gap:16px;position:sticky;top:0;z-index:100}}
.header a{{color:#6c63ff;text-decoration:none;font-size:13px}}
.header h1{{font-size:18px;color:#fff;flex:1}}
.header h1 span{{color:#6c63ff}}

/* Stats bar */
.stats-bar{{display:flex;justify-content:center;gap:40px;padding:20px 24px;background:#161822;border-bottom:1px solid #1a1d2e}}
.sb-item{{text-align:center}}
.sb-val{{font-size:22px;font-weight:700;color:#fff}}
.sb-label{{font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.5px;margin-top:2px}}

/* Container */
.container{{max-width:1100px;margin:0 auto;padding:24px}}

/* Big Bet */
.big-bet{{background:linear-gradient(135deg,#1a1d40 0%,#2a1540 100%);border:1px solid #6c63ff;border-radius:16px;padding:32px;margin-bottom:32px;text-align:center}}
.bb-eyebrow{{font-size:11px;color:#6c63ff;text-transform:uppercase;letter-spacing:2px;font-weight:700;margin-bottom:12px}}
.bb-text{{font-size:16px;color:#e0e0e0;line-height:1.7;max-width:800px;margin:0 auto}}

/* Sections */
.section{{background:#161822;border:1px solid #2a2d3a;border-radius:14px;padding:28px;margin-bottom:28px;position:relative}}
.section-icon{{font-size:24px;margin-bottom:8px}}
.section h2{{font-size:16px;color:#fff;margin-bottom:4px}}
.section .section-desc{{font-size:13px;color:#666;margin-bottom:20px}}

/* Action Cards Grid */
.card-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}}

/* Action Card */
.action-card{{background:#1a1d2e;border:1px solid #252840;border-radius:12px;padding:18px;transition:border-color .2s}}
.action-card:hover{{border-color:#6c63ff44}}
.action-card.compact{{padding:14px}}
.ac-header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;gap:10px}}
.ac-topic{{font-size:15px;font-weight:700;color:#fff;flex:1}}
.ac-badge{{display:inline-block;padding:3px 10px;border-radius:10px;font-size:10px;font-weight:700;white-space:nowrap}}
.ac-badge.rising{{background:#1a3a2a;color:#6bcb77}}
.ac-badge.dormant{{background:#3a3a1a;color:#ffd93d}}
.ac-badge.stale{{background:#3a2a1a;color:#ffaa6b}}
.ac-badge.new{{background:#1a2a3a;color:#6bc3cb}}
.ac-badge.passion{{background:#3a1a2a;color:#ff6b8a}}
.ac-stat-row{{display:flex;gap:16px;margin-bottom:12px}}
.ac-stat{{flex:1;text-align:center}}
.ac-stat-val{{font-size:18px;font-weight:700;color:#fff}}
.ac-stat-val.hot{{color:#ff6b6b}}
.ac-stat-val.warm{{color:#ffd93d}}
.ac-stat-val.cool{{color:#6ba3cb}}
.ac-stat-val.green{{color:#6bcb77}}
.ac-stat-label{{font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.3px;margin-top:2px}}
.ac-action{{font-size:12px;color:#999;line-height:1.6;padding:10px 14px;background:#12141f;border-radius:8px;border-left:3px solid #6c63ff}}

/* Mega Stats */
.mega-stat-row{{display:flex;gap:16px;margin-bottom:20px}}
.mega-stat{{flex:1;text-align:center;background:#1a1d2e;border-radius:12px;padding:20px}}
.ms-val{{font-size:32px;font-weight:700;color:#fff}}
.ms-val.hot{{color:#ff6b6b}}
.ms-val.green{{color:#6bcb77}}
.ms-val.dim{{color:#666}}
.ms-label{{font-size:10px;color:#555;text-transform:uppercase;letter-spacing:.5px;margin-top:4px}}

/* Contrarian items */
.contrarian-item{{display:flex;align-items:center;padding:10px 14px;background:#1a1d2e;border-radius:8px;margin-bottom:6px}}
.ci-title{{flex:1;font-size:13px;color:#ddd}}
.ci-views{{font-size:13px;font-weight:700;color:#6c63ff;white-space:nowrap}}

/* Formula */
.formula-box{{background:#1a1d40;border:1px solid #6c63ff44;border-radius:12px;padding:20px;margin-bottom:20px}}
.formula-label{{font-size:10px;color:#6c63ff;text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:6px}}
.formula-text{{font-size:18px;color:#fff;font-weight:700;margin-bottom:12px}}
.formula-example{{font-size:12px;color:#999;padding:6px 0 6px 14px;border-left:2px solid #6c63ff44;margin:4px 0;font-style:italic}}

/* Pattern rows */
.pattern-row{{display:flex;align-items:center;padding:10px 14px;background:#1a1d2e;border-radius:8px;margin-bottom:6px;font-size:13px}}
.pr-name{{flex:1;color:#ddd;font-weight:600}}
.pr-count{{color:#666;margin-right:16px;font-size:11px}}
.pr-views{{color:#999;margin-right:16px}}
.pr-lift{{font-weight:700;min-width:60px;text-align:right}}

/* Insight Cards */
.insights-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}}
.insight-card{{background:#1a1d2e;border-radius:12px;padding:18px;border-left:4px solid #6c63ff}}
.insight-card.blind{{border-left-color:#ffd93d}}
.insight-card.money{{border-left-color:#6bcb77}}
.ic-icon{{font-size:20px;margin-bottom:4px}}
.ic-label{{font-size:10px;color:#6c63ff;text-transform:uppercase;letter-spacing:.5px;font-weight:700;margin-bottom:6px}}
.insight-card.blind .ic-label{{color:#ffd93d}}
.insight-card.money .ic-label{{color:#6bcb77}}
.ic-text{{font-size:13px;color:#ccc;line-height:1.6}}

/* Cannibalization */
.cannibal-item{{display:flex;align-items:center;gap:12px;padding:10px 14px;background:#1a1d2e;border-radius:8px;margin-bottom:6px;font-size:13px}}
.cn-pair{{flex:1;color:#ddd;font-weight:600}}
.cn-overlap{{font-weight:700;white-space:nowrap}}
.cn-count{{color:#666;white-space:nowrap}}

/* Sub-labels */
.sub-label{{font-size:11px;color:#555;text-transform:uppercase;letter-spacing:.5px;margin:16px 0 10px;font-weight:700}}

/* Footer */
.footer{{text-align:center;padding:40px 24px;color:#333;font-size:11px}}
.footer a{{color:#6c63ff;text-decoration:none}}

/* Write buttons */
.write-btn{{display:block;width:100%;margin-top:12px;padding:10px 16px;background:#6c63ff22;border:1px solid #6c63ff44;color:#a29bfe;font-size:13px;font-weight:600;border-radius:8px;cursor:pointer;transition:all .2s}}
.write-btn:hover{{background:#6c63ff;color:#fff;border-color:#6c63ff}}
.write-btn:disabled{{opacity:.5;cursor:wait}}
.write-btn.loading{{background:#6c63ff44;color:#ddd;border-color:#6c63ff66}}

/* Writer Modal */
.writer-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:200;backdrop-filter:blur(4px)}}
.writer-overlay.active{{display:flex;align-items:center;justify-content:center}}
.writer-modal{{background:#161822;border:1px solid #2a2d3a;border-radius:16px;width:90%;max-width:800px;max-height:85vh;display:flex;flex-direction:column;box-shadow:0 24px 64px rgba(0,0,0,.5)}}
.wm-header{{padding:20px 24px;border-bottom:1px solid #2a2d3a;display:flex;align-items:center;gap:12px;flex-shrink:0}}
.wm-header h3{{flex:1;font-size:16px;color:#fff}}
.wm-header .wm-badge{{padding:3px 10px;border-radius:10px;font-size:10px;font-weight:700;background:#6c63ff22;color:#a29bfe}}
.wm-close{{background:none;border:none;color:#666;font-size:24px;cursor:pointer;padding:4px 8px}}
.wm-close:hover{{color:#fff}}
.wm-body{{flex:1;overflow-y:auto;padding:24px}}
.wm-content{{font-size:14px;color:#ccc;line-height:1.8;white-space:pre-wrap}}
.wm-content h1,.wm-content h2,.wm-content h3{{color:#fff;margin:16px 0 8px}}
.wm-content strong{{color:#fff}}
.wm-loading{{text-align:center;padding:60px 24px;color:#888}}
.wm-loading .spinner{{display:inline-block;width:32px;height:32px;border:3px solid #2a2d3a;border-top-color:#6c63ff;border-radius:50%;animation:spin .8s linear infinite;margin-bottom:16px}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.wm-actions{{padding:16px 24px;border-top:1px solid #2a2d3a;display:flex;gap:10px;flex-shrink:0}}
.wm-actions button{{padding:10px 20px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;border:none;transition:all .15s}}
.wm-btn-copy{{background:#6c63ff;color:#fff}}
.wm-btn-copy:hover{{background:#7c73ff}}
.wm-btn-regen{{background:#1a1d2e;color:#a29bfe;border:1px solid #6c63ff44}}
.wm-btn-regen:hover{{background:#6c63ff22}}
.wm-btn-close{{background:#1a1d2e;color:#888;border:1px solid #2a2d3a}}
.wm-btn-close:hover{{background:#252840;color:#ccc}}

/* Responsive */
@media(max-width:700px){{
    .card-grid{{grid-template-columns:1fr}}
    .mega-stat-row{{flex-direction:column}}
    .stats-bar{{gap:20px;flex-wrap:wrap}}
    .insights-grid{{grid-template-columns:1fr}}
    .ac-stat-row{{flex-wrap:wrap}}
}}
</style></head><body>

<div class="header">
    <a href="index.html">&larr; Home</a>
    <h1><span>Content Intelligence</span> — {esc(channel)}</h1>
</div>

<div class="stats-bar">
    <div class="sb-item"><div class="sb-val">{total_videos}</div><div class="sb-label">Videos Analyzed</div></div>
    <div class="sb-item"><div class="sb-val">{fmt_views(total_views)}</div><div class="sb-label">Total Views</div></div>
    <div class="sb-item"><div class="sb-val">{fmt_views(channel_avg)}</div><div class="sb-label">Avg Views</div></div>
    <div class="sb-item"><div class="sb-val">{engagement_rate:.1f}%</div><div class="sb-label">Engagement Rate</div></div>
    <div class="sb-item"><div class="sb-val">{len(rising_topics)}</div><div class="sb-label">Rising Topics</div></div>
    <div class="sb-item"><div class="sb-val">{len(revivals)}</div><div class="sb-label">Revival Opportunities</div></div>
</div>

<div class="container">

{big_bet_html}

{"" if not insights_cards else f'''
    <div class="section">
        <div class="section-icon">🧠</div>
        <h2>What You Probably Don't Realize</h2>
        <p class="section-desc">AI-detected blind spots and missed opportunities in your content strategy.</p>
        <div class="insights-grid">{insights_cards}</div>
    </div>
'''}

{"" if not working_now_cards else f'''
    <div class="section">
        <div class="section-icon">🚀</div>
        <h2>What's Working NOW — Double Down</h2>
        <p class="section-desc">These topics are rising in frequency AND performing well. Your audience is telling you to make more of this.</p>
        <div class="card-grid">{working_now_cards}</div>
    </div>
'''}

{contrarian_html}

{"" if not revival_cards else f'''
    <div class="section">
        <div class="section-icon">🔄</div>
        <h2>Resurrection Candidates — Bring These Back</h2>
        <p class="section-desc">Topics you stopped covering but your audience loved. Proven demand, zero recent supply.</p>
        <div class="card-grid">{revival_cards}</div>
    </div>
'''}

{"" if not evergreen_cards else f'''
    <div class="section">
        <div class="section-icon">📅</div>
        <h2>Evergreen Decay — Update These Winners</h2>
        <p class="section-desc">High-performing content that's aging. Refresh with current info for a near-guaranteed win.</p>
        <div class="card-grid">{evergreen_cards}</div>
    </div>
'''}

{"" if not combo_cards else f'''
    <div class="section">
        <div class="section-icon">🧪</div>
        <h2>Untapped Topic Combinations</h2>
        <p class="section-desc">Each of these topics performs well on its own, but you've rarely combined them. Test the mashup.</p>
        <div class="card-grid">{combo_cards}</div>
    </div>
'''}

{"" if not passion_cards else f'''
    <div class="section">
        <div class="section-icon">💬</div>
        <h2>Audience Passion Signals</h2>
        <p class="section-desc">Videos where your audience engaged far above normal. High comment rate = they're TELLING you what they need.</p>
        <div class="card-grid">{passion_cards}</div>
    </div>
'''}

{title_html}

{cannibal_html}

{rhythm_html}

</div>

<div class="footer">
    Powered by <a href="#">TrueInfluenceAI</a> · WinTech Partners · {datetime.now().strftime('%B %Y')}<br>
    Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}
</div>

</body></html>'''

    out = bp / 'analytics.html'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"  [OK] {out.name} ({len(html):,} bytes)")
    return out


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

    print(f"[*] Building actionable analytics for: {bp.name}")
    out = build_analytics(bp)
    print(f"\n[OK] Done: {out}")

    import webbrowser
    webbrowser.open(str(out))


if __name__ == '__main__':
    main()
