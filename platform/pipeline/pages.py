"""
TrueInfluenceAI - Interactive Dashboard Pages v2
===================================================
Three-layer interactive dashboard:
  Layer 1: Dashboard cards (Double Down, Untapped, Resurface, Stop Making)
  Layer 2: Expanded detail with two action buttons
  Layer 3a: Deep stats (filtered analytics)
  Layer 3b: Content starter (voice-matched writing help)

Also builds: index, analytics, discuss pages.
"""

import os, json
from pathlib import Path
from datetime import datetime

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL_ID = os.getenv("OPENROUTER_MODEL_ID", "anthropic/claude-sonnet-4-20250514")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen/qwen3-embedding-8b")

# ─── Shared Styles ──────────────────────────────────────────────
FONTS = '<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=Fraunces:opsz,wght@9..144,400;9..144,700;9..144,900&display=swap" rel="stylesheet">'

THEME_CSS = """
:root{
  --bg:#06070b;--surface:#0c0d14;--surface2:#12131c;--border:#1a1c2a;
  --accent:#6366f1;--accent-glow:#818cf8;--accent-soft:rgba(99,102,241,.08);
  --text:#9ca3af;--bright:#f1f5f9;--muted:#4b5563;
  --green:#34d399;--green-soft:rgba(52,211,153,.1);
  --red:#f87171;--red-soft:rgba(248,113,113,.1);
  --gold:#fbbf24;--gold-soft:rgba(251,191,36,.1);
  --blue:#60a5fa;--blue-soft:rgba(96,165,250,.1);
}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Outfit',sans-serif;background:var(--bg);color:var(--text);min-height:100vh;-webkit-font-smoothing:antialiased}
a{color:var(--accent-glow);text-decoration:none}a:hover{color:var(--bright)}
.container{max-width:1140px;margin:0 auto;padding:32px 24px}
h2{font-family:'Fraunces',serif;font-size:32px;font-weight:900;color:var(--bright);margin-bottom:6px}
h3{font-family:'Fraunces',serif;font-size:20px;font-weight:700;color:var(--bright);margin:32px 0 16px}
.sub{color:var(--muted);font-size:14px;margin-bottom:32px}
"""

NAV_CSS = """
nav{padding:14px 32px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border);background:rgba(12,13,20,.85);position:sticky;top:0;z-index:50;backdrop-filter:blur(16px)}
nav .logo{font-family:'Fraunces',serif;font-size:18px;font-weight:900;color:var(--bright)}
nav .logo span{color:var(--accent)}
nav .links{display:flex;gap:4px}
nav .links a{color:var(--muted);font-size:13px;font-weight:500;padding:6px 14px;border-radius:8px;transition:all .2s}
nav .links a:hover{color:var(--bright);background:var(--accent-soft)}
nav .links a.active{color:var(--accent-glow);background:var(--accent-soft)}
"""


def _nav_html(channel, slug, active):
    base = f"/c/{slug}"
    def cls(name):
        return ' class="active"' if name == active else ''
    return f"""<nav>
<div class="logo"><span>TrueInfluence</span>AI · {channel}</div>
<div class="links">
<a href="{base}"{cls('home')}>Home</a>
<a href="{base}/dashboard"{cls('dashboard')}>Dashboard</a>
<a href="{base}/analytics"{cls('analytics')}>Analytics</a>
<a href="{base}/discuss"{cls('discuss')}>Discuss</a>
</div></nav>"""


# ─── Data Loading ───────────────────────────────────────────────
def _load_bundle(bp):
    data = {}
    for name in ["manifest", "sources", "chunks", "analytics_report",
                  "channel_metrics", "voice_profile", "insights", "comments"]:
        p = bp / f"{name}.json"
        if p.exists():
            data[name] = json.loads(p.read_text(encoding="utf-8"))
        else:
            data[name] = {} if name not in ("sources", "chunks") else []
    return data


# ─── Categorize Topics (Improved Statistics) ───────────────────
def _categorize_topics(data):
    """Analyze topics using statistically grounded methods.
    
    Drop-in replacement using improved_statistics module for:
    - Z-score based classification
    - Confidence intervals
    - Coefficient of Variation for consistency
    - Bayesian smoothing for small samples
    - IQR outlier detection
    """
    try:
        from pipeline.improved_statistics import improved_categorize_topics
        result = improved_categorize_topics(data)
        return _coerce_category_shape(result)
    except ImportError:
        try:
            from improved_statistics import improved_categorize_topics
            result = improved_categorize_topics(data)
            return _coerce_category_shape(result)
        except ImportError:
            print("WARNING: improved_statistics not found, using basic categorization")
            return _categorize_topics_basic(data)
    except Exception as e:
        print(f"WARNING: improved categorization failed ({e}); using basic categorization")
        return _categorize_topics_basic(data)


def _coerce_category_shape(categories):
    """Ensure dashboard JS always receives expected keys and numeric types."""
    normalized = {}
    for bucket in ["double_down", "untapped", "resurface", "stop_making", "investigate"]:
        items = categories.get(bucket, []) if isinstance(categories, dict) else []
        out = []
        for item in items:
            if not isinstance(item, dict):
                continue
            vs = item.get("vs_channel", item.get("vs_channel_avg", 0))
            avg = item.get("avg_views", item.get("weighted_avg_views", 0))
            out.append({
                **item,
                "vs_channel": float(vs or 0),
                "avg_views": float(avg or 0),
                "video_count": int(item.get("video_count", 0) or 0),
                "videos": item.get("videos", []) if isinstance(item.get("videos", []), list) else [],
                "reason": item.get("reason", "No rationale generated yet."),
            })
        normalized[bucket] = out
    return normalized


def _categorize_topics_basic(data):
    """Basic fallback categorization with compatibility for multiple analytics schemas."""
    analytics = data.get("analytics_report", {})
    performance = _normalize_topic_performance(
        analytics,
        data.get("sources", []),
        data.get("channel_metrics", {}).get("channel_avg_views", 0),
    )
    timeline = analytics.get("topic_timeline", {})
    sources = data.get("sources", [])
    source_map = {s["source_id"]: s for s in sources}
    double_down, untapped, resurface, stop_making = [], [], [], []

    for topic, perf in sorted(performance.items(), key=lambda x: -x[1].get("weighted_avg_views", 0)):
        vs = perf.get("vs_channel_avg", 0)
        count = perf.get("video_count", timeline.get(topic, {}).get("count", 0))
        avg_views = perf.get("weighted_avg_views", 0)
        tl = timeline.get(topic, {})
        videos = tl.get("videos", [])

        video_details = []
        for v in videos:
            vid = v.get("video_id", "")
            s = source_map.get(vid, {})
            video_details.append({
                "video_id": vid,
                "title": s.get("title", v.get("title", "")),
                "views": s.get("views", 0),
                "published": v.get("published", s.get("published_text", "")),
                "url": s.get("url", f"https://www.youtube.com/watch?v={vid}"),
            })

        entry = {"topic": topic, "vs_channel": vs, "avg_views": avg_views,
                 "video_count": count, "videos": video_details}

        if count == 1 and vs > 100:
            entry["reason"] = f"One video got {avg_views:,.0f} views — {vs:+.0f}% above average."
            untapped.append(entry)
        elif count >= 2 and vs > 20:
            entry["reason"] = f"{count} videos averaging {avg_views:,.0f} views ({vs:+.0f}% above avg)."
            double_down.append(entry)
        elif count >= 2 and vs < -40:
            entry["reason"] = f"{avg_views:,.0f} avg views — {abs(vs):.0f}% below average."
            stop_making.append(entry)
        elif count >= 2 and -40 <= vs <= 20:
            entry["reason"] = f"{count} videos at {avg_views:,.0f} avg views ({vs:+.0f}% vs avg). Mixed results worth testing." 
            resurface.append(entry)

    # Guarantee non-empty dashboard sections when data exists.
    if not (double_down or untapped or resurface or stop_making) and performance:
        seed = sorted(performance.items(), key=lambda x: -x[1].get("weighted_avg_views", 0))[:6]
        for topic, perf in seed:
            resurface.append({
                "topic": topic,
                "vs_channel": perf.get("vs_channel_avg", 0),
                "avg_views": perf.get("weighted_avg_views", 0),
                "video_count": perf.get("video_count", timeline.get(topic, {}).get("count", 0)),
                "videos": timeline.get(topic, {}).get("videos", []),
                "reason": "Baseline recommendation: this topic has historical data and should be tested with a fresh angle.",
            })

    return _coerce_category_shape({
        "double_down": double_down[:6], "untapped": untapped[:6],
        "resurface": resurface[:6], "stop_making": stop_making[:6],
        "investigate": [],
    })


def _normalize_topic_performance(analytics, sources, channel_avg_views=0):
    """Normalize topic_performance shape across legacy and current analytics schemas."""
    performance = analytics.get("topic_performance", {}) or {}
    timeline = analytics.get("topic_timeline", {}) or {}

    if not performance:
        return {}

    if not channel_avg_views:
        vv = [s.get("views", 0) for s in sources if s.get("views", 0) > 0]
        channel_avg_views = int(sum(vv) / len(vv)) if vv else 1

    # Legacy form: {"Topic": 12345}
    if isinstance(next(iter(performance.values())), (int, float)):
        topic_freq = analytics.get("topic_frequency", {})
        normalized = {}
        for topic, avg in performance.items():
            avg = int(avg or 0)
            normalized[topic] = {
                "weighted_avg_views": avg,
                "video_count": int(topic_freq.get(topic, timeline.get(topic, {}).get("count", 0)) or 0),
                "vs_channel_avg": round(((avg / channel_avg_views) - 1) * 100, 1) if channel_avg_views else 0,
            }
        return normalized

    return performance




# ─── Build All Pages ───────────────────────────────────────────
def build_all_pages(bundle_dir, slug):
    """Build all 4 creator pages."""
    bundle_dir = Path(bundle_dir)
    data = _load_bundle(bundle_dir)
    data["slug"] = slug
    data["categories"] = _categorize_topics(data)
    print(f"Building pages for {slug}...")
    _build_index(bundle_dir, data)
    _build_dashboard(bundle_dir, data)
    _build_analytics(bundle_dir, data)
    _build_discuss(bundle_dir, data)
    print(f"   All 4 pages built")


# ─── INDEX PAGE ─────────────────────────────────────────────────
def _build_index(bp, data):
    ch = data["manifest"].get("channel", "Unknown")
    slug = data["slug"]
    m = data.get("channel_metrics", {})
    v = data.get("voice_profile", {})
    tone = v.get("tone", "")
    tv = data["manifest"].get("total_videos", 0)
    tc = data["manifest"].get("total_chunks", 0)
    av = m.get("channel_avg_views", 0)
    tvw = m.get("total_views", 0)
    topics = data.get("analytics_report", {}).get("total_topics", 0)
    cats = data.get("categories", {})
    base = f"/c/{slug}"

    # Quick wins summary
    dd_count = len(cats.get("double_down", []))
    ut_count = len(cats.get("untapped", []))
    rs_count = len(cats.get("resurface", []))

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{ch} · TrueInfluenceAI</title>{FONTS}
<style>{THEME_CSS}
.hero{{text-align:center;padding:80px 24px 60px;position:relative;overflow:hidden}}
.hero::before{{content:'';position:absolute;top:0;left:50%;transform:translateX(-50%);width:600px;height:600px;background:radial-gradient(circle,rgba(99,102,241,.06) 0%,transparent 70%);pointer-events:none}}
.hero h1{{font-family:'Fraunces',serif;font-size:48px;font-weight:900;color:var(--bright);margin-bottom:8px;position:relative}}
.hero h1 span{{color:var(--accent)}}
.hero .tagline{{font-size:16px;color:var(--muted);max-width:500px;margin:0 auto 40px;line-height:1.6}}
.stats{{display:flex;justify-content:center;gap:48px;flex-wrap:wrap;margin-bottom:40px;position:relative}}
.stat{{text-align:center}}.stat .n{{font-family:'Fraunces',serif;font-size:36px;font-weight:900;color:var(--bright)}}
.stat .l{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px;margin-top:4px}}
.voice{{max-width:600px;margin:0 auto;padding:20px 24px;background:var(--surface);border:1px solid var(--border);border-radius:12px;text-align:left}}
.voice .vl{{font-size:10px;color:var(--accent);text-transform:uppercase;letter-spacing:1.5px;font-weight:700;margin-bottom:6px}}
.voice .vt{{font-size:14px;color:var(--text);line-height:1.6;font-style:italic}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;max-width:960px;margin:60px auto;padding:0 24px}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:32px 24px;text-align:center;cursor:pointer;transition:all .25s;text-decoration:none;color:inherit;position:relative;overflow:hidden}}
.card:hover{{transform:translateY(-3px);border-color:var(--accent);box-shadow:0 12px 40px rgba(99,102,241,.12)}}
.card .icon{{font-size:40px;margin-bottom:14px}}.card h3{{font-family:'Fraunces',serif;font-size:17px;color:var(--bright);margin-bottom:8px}}
.card p{{font-size:13px;color:var(--muted);line-height:1.5}}
.card .badge{{display:inline-block;margin-top:14px;padding:4px 12px;border-radius:20px;font-size:11px;font-weight:600}}
.footer{{text-align:center;padding:48px 24px;font-size:12px;color:var(--muted)}}
@media(max-width:700px){{.cards{{grid-template-columns:1fr}}.stats{{gap:24px}}}}
</style></head><body>
<div class="hero">
<h1><span>TrueInfluence</span>AI</h1>
<div class="tagline">Creator Intelligence for <strong style="color:var(--bright)">{ch}</strong></div>
<div class="stats">
<div class="stat"><div class="n">{tv}</div><div class="l">Videos</div></div>
<div class="stat"><div class="n">{av:,}</div><div class="l">Avg Views</div></div>
<div class="stat"><div class="n">{tvw:,}</div><div class="l">Total Views</div></div>
<div class="stat"><div class="n">{topics}</div><div class="l">Topics</div></div>
</div>
{'<div class="voice"><div class="vl">Voice Profile</div><div class="vt">'+tone+'</div></div>' if tone else ''}
</div>
<div class="cards">
<a class="card" href="{base}/dashboard"><div class="icon">🎯</div><h3>Dashboard</h3><p>What to make next, what to stop, and hidden gems to resurface.</p>
<span class="badge" style="background:var(--green-soft);color:var(--green)">{ut_count + dd_count} opportunities</span></a>
<a class="card" href="{base}/analytics"><div class="icon">📊</div><h3>Analytics</h3><p>Every topic scored against your channel average with trend data.</p>
<span class="badge" style="background:var(--accent-soft);color:var(--accent-glow)">{topics} topics tracked</span></a>
<a class="card" href="{base}/discuss"><div class="icon">💬</div><h3>Discuss</h3><p>Chat with AI trained on {ch}'s content and voice.</p>
<span class="badge" style="background:var(--gold-soft);color:var(--gold)">AI-Powered</span></a>
</div>
<div class="footer">Powered by <a href="/" style="color:var(--accent)">TrueInfluenceAI</a> · Built by WinTech Partners</div>
</body></html>"""
    (bp / "index.html").write_text(html, encoding="utf-8")


# ─── DASHBOARD PAGE (The Big One) ──────────────────────────────
def _build_dashboard(bp, data):
    ch = data["manifest"].get("channel", "Unknown")
    slug = data["slug"]
    cats = data.get("categories", {})
    insights_data = data.get("insights", {})
    analytics_data = data.get("analytics_report", {})
    direction = insights_data.get("strategic_direction", "")
    voice = data.get("voice_profile", {})
    future_suggestions = analytics_data.get("future_content_suggestions", [])

    # Encode data for JavaScript
    cats_json = json.dumps(cats, ensure_ascii=False)
    voice_json = json.dumps(voice, ensure_ascii=False)
    future_json = json.dumps(future_suggestions[:8], ensure_ascii=False)

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{ch} Dashboard · TrueInfluenceAI</title>{FONTS}
<style>{THEME_CSS}{NAV_CSS}

/* Section headers */
.section-head{{display:flex;align-items:center;gap:12px;margin:40px 0 20px}}
.section-head .dot{{width:10px;height:10px;border-radius:50%}}
.section-head h3{{margin:0;font-size:18px}}
.section-head .count{{font-size:12px;color:var(--muted);margin-left:auto}}

/* Topic cards - Layer 1 */
.topic-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px;margin-bottom:16px}}
.topic-card{{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:20px;cursor:pointer;transition:all .2s;position:relative}}
.topic-card:hover{{border-color:var(--accent);transform:translateY(-2px)}}
.topic-card .tc-head{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:8px}}
.topic-card h4{{font-size:15px;font-weight:600;color:var(--bright);margin:0}}
.topic-card .tc-stat{{font-size:13px;font-weight:700;padding:2px 10px;border-radius:6px}}
.topic-card .tc-reason{{font-size:13px;color:var(--text);line-height:1.5;margin-bottom:12px}}
.topic-card .tc-vids{{font-size:11px;color:var(--muted)}}
.topic-card .tc-expand{{font-size:11px;color:var(--accent);font-weight:600;display:flex;align-items:center;gap:4px;margin-top:8px}}

/* Expanded detail - Layer 2 */
.detail-overlay{{display:none;position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(6,7,11,.9);z-index:100;overflow-y:auto;backdrop-filter:blur(8px)}}
.detail-overlay.open{{display:block}}
.detail-panel{{max-width:800px;margin:60px auto;padding:40px;background:var(--surface);border:1px solid var(--border);border-radius:20px;position:relative}}
.detail-panel .close-btn{{position:absolute;top:16px;right:20px;font-size:24px;color:var(--muted);cursor:pointer;background:none;border:none;font-family:inherit}}
.detail-panel .close-btn:hover{{color:var(--bright)}}
.detail-panel h2{{font-size:24px;margin-bottom:8px}}
.detail-panel .dp-stat{{font-size:14px;margin-bottom:16px}}
.detail-panel .dp-reason{{font-size:15px;color:var(--text);line-height:1.7;margin-bottom:24px;padding:16px;background:var(--surface2);border-radius:10px;border-left:3px solid var(--accent)}}
.detail-panel .dp-videos{{margin-bottom:24px}}
.detail-panel .dp-videos h4{{font-size:14px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:12px}}
.detail-panel .vid-row{{display:flex;justify-content:space-between;padding:10px 0;border-bottom:1px solid var(--border);font-size:13px}}
.detail-panel .vid-row a{{color:var(--bright)}}
.detail-panel .vid-row .vr-views{{color:var(--green)}}

/* Action buttons */
.action-btns{{display:flex;gap:12px;margin-top:24px}}
.action-btn{{flex:1;padding:16px;border-radius:12px;border:1px solid var(--border);background:var(--surface2);cursor:pointer;text-align:center;transition:all .2s;text-decoration:none;color:inherit}}
.action-btn:hover{{border-color:var(--accent);transform:translateY(-2px)}}
.action-btn .ab-icon{{font-size:28px;margin-bottom:8px}}
.action-btn .ab-title{{font-size:14px;font-weight:600;color:var(--bright)}}
.action-btn .ab-desc{{font-size:12px;color:var(--muted);margin-top:4px}}

/* Layer 3 panels */
.l3-panel{{display:none;margin-top:24px;padding:24px;background:var(--surface2);border-radius:12px;border:1px solid var(--border)}}
.l3-panel.open{{display:block}}
.l3-panel h4{{font-size:14px;color:var(--accent);text-transform:uppercase;letter-spacing:1px;margin-bottom:16px}}

/* Content starter */
.content-starter{{line-height:1.7;color:var(--text)}}
.content-starter .cs-title{{font-size:18px;font-weight:700;color:var(--bright);margin-bottom:8px}}
.content-starter .cs-hook{{font-size:15px;color:var(--gold);font-style:italic;margin-bottom:16px;padding:12px;background:var(--gold-soft);border-radius:8px}}
.content-starter .cs-outline{{margin-top:12px}}
.content-starter .cs-outline li{{margin-bottom:6px;font-size:14px}}
.cs-loading{{color:var(--muted);font-size:14px;padding:24px;text-align:center}}

/* Direction box */
.dir-box{{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:24px;margin-bottom:8px;font-size:15px;line-height:1.7;border-left:3px solid var(--accent)}}

/* Empty state */
.empty{{color:var(--muted);font-size:14px;font-style:italic;padding:16px 0}}
.future-wrap{{margin:18px 0 6px;background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:18px}}
.future-wrap h3{{margin:0 0 6px;font-size:16px}}
.future-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:10px;margin-top:12px}}
.future-card{{background:var(--surface2);border:1px solid var(--border);border-radius:10px;padding:12px}}
.future-card .fc-top{{display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:6px}}
.future-card .fc-topic{{font-size:13px;color:var(--bright);font-weight:600}}
.future-card .fc-score{{font-size:11px;color:var(--accent-glow);font-weight:700}}
.future-card .fc-meta{{font-size:11px;color:var(--muted);margin-bottom:6px}}
.future-card .fc-idea{{font-size:12px;color:var(--text);line-height:1.4}}
.quick-actions{{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 20px}}
.qa-btn{{padding:10px 14px;border-radius:10px;border:1px solid var(--border);background:var(--surface2);color:var(--bright);font-size:12px;cursor:pointer;font-family:inherit}}
.qa-btn:hover{{border-color:var(--accent);color:var(--accent-glow)}}
</style></head><body>
{_nav_html(ch, slug, 'dashboard')}
<div class="container">
<h2>Your Dashboard</h2>
<p class="sub">What to make next — based on what's actually working</p>

{'<div class="dir-box">'+direction+'</div>' if direction else ''}

<div class="quick-actions">
  <button class="qa-btn" onclick="quickGenerate('story')">🧠 AI Story Starter</button>
  <button class="qa-btn" onclick="quickGenerate('full')">📝 AI Full Content Writer</button>
</div>

<div id="futureIdeas"></div>

<div id="dashboard-content"></div>
</div>

<!-- Detail Overlay -->
<div class="detail-overlay" id="detailOverlay">
<div class="detail-panel" id="detailPanel"></div>
</div>

<div class="detail-overlay" id="quickAIModal">
  <div class="detail-panel" id="quickAIPanel"></div>
</div>

<script>
const CATS = {cats_json};
const VOICE = {voice_json};
const FUTURE = {future_json};
const API_KEY = '{OPENROUTER_API_KEY}';
const MODEL = '{OPENROUTER_MODEL_ID}';
const CHANNEL = '{ch}';

function renderDashboard() {{
  const el = document.getElementById('dashboard-content');
  let html = '';

  // Double Down
  if (CATS.double_down && CATS.double_down.length) {{
    html += sectionHTML('🔥', 'Double Down', 'var(--green)', CATS.double_down, 'These topics consistently outperform. Make more.');
  }}

  // Untapped
  if (CATS.untapped && CATS.untapped.length) {{
    html += sectionHTML('💎', 'Untapped Opportunities', 'var(--gold)', CATS.untapped, 'One video crushed it. Your audience wants more.');
  }}

  // Resurface & Refresh
  if (CATS.resurface && CATS.resurface.length) {{
    html += sectionHTML('♻️', 'Resurface & Refresh', 'var(--blue)', CATS.resurface, 'Old hits ready for a 2026 update.');
  }}

  // Stop Making
  if (CATS.stop_making && CATS.stop_making.length) {{
    html += sectionHTML('🚫', 'Consider Dropping', 'var(--red)', CATS.stop_making.slice(0, 4), 'Consistently below average. Your audience isn\\'t here for this.');
  }}

  // Investigate (new: mixed signals)
  if (CATS.investigate && CATS.investigate.length) {{
    html += sectionHTML('🔍', 'Needs Investigation', 'var(--muted)', CATS.investigate.slice(0, 4), 'Mixed signals — one video crushed it, another flopped. Dig into what made the winner work.');
  }}

  if (!html || html.trim().length === 0) {{
    el.innerHTML = '<div class="empty">No categorized topics were generated yet. Re-run analytics, or use AI Story Starter / Full Content Writer above.</div>';
  }} else {{
    el.innerHTML = html;
  }}
}}

function renderFutureIdeas() {{
  const el = document.getElementById('futureIdeas');
  if (!FUTURE || !FUTURE.length) {{
    el.innerHTML = '';
    return;
  }}

  const cards = FUTURE.map(s => `
    <div class="future-card">
      <div class="fc-top">
        <div class="fc-topic">${{s.topic}}</div>
        <div class="fc-score">Score ${{(s.opportunity_score || 0).toFixed(1)}}</div>
      </div>
      <div class="fc-meta">${{(s.category || 'education')}} · ${{(s.trend || 'steady')}} · ${{(s.avg_engagement_rate || 0).toFixed(2)}}% engagement</div>
      <div class="fc-idea">${{(s.idea_angles && s.idea_angles[0]) || 'Create a fresh angle based on this topic\'s recent audience response.'}}</div>
    </div>
  `).join('');

  el.innerHTML = `
    <div class="future-wrap">
      <h3>🚀 Recommended Future Content</h3>
      <p class="sub" style="margin:0;color:var(--muted)">Ranked using historical topic performance + follower engagement signals.</p>
      <div class="future-grid">${{cards}}</div>
    </div>
  `;
}}

function sectionHTML(icon, title, color, items, subtitle) {{
  let cards = '';
  items.forEach((item, i) => {{
    const vsColor = item.vs_channel > 0 ? 'var(--green)' : 'var(--red)';
    const sign = item.vs_channel > 0 ? '+' : '';
    const confBadge = item.confidence_level === 'high'
      ? '<span style="background:var(--green-soft);color:var(--green);padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600">High confidence</span>'
      : item.confidence_level === 'medium'
      ? '<span style="background:var(--gold-soft);color:var(--gold);padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600">Medium confidence</span>'
      : item.confidence_level
      ? '<span style="background:var(--red-soft);color:var(--red);padding:2px 8px;border-radius:4px;font-size:10px;font-weight:600">Low confidence</span>'
      : '';
    cards += `
      <div class="topic-card" onclick="openDetail('${{title}}', ${{i}})">
        <div class="tc-head">
          <h4>${{item.topic}}</h4>
          <span class="tc-stat" style="background:${{item.vs_channel > 0 ? 'var(--green-soft)' : 'var(--red-soft)'}};color:${{vsColor}}">${{sign}}${{item.vs_channel.toFixed(0)}}%</span>
        </div>
        <div class="tc-reason">${{item.reason}}</div>
        <div class="tc-vids">${{item.video_count}} video${{item.video_count !== 1 ? 's' : ''}} · ${{item.avg_views.toLocaleString()}} avg views ${{confBadge}}</div>
        <div class="tc-expand">Click to explore →</div>
      </div>`;
  }});

  return `
    <div class="section-head">
      <span style="font-size:20px">${{icon}}</span>
      <h3 style="color:${{color}}">${{title}}</h3>
      <span class="count">${{items.length}} topic${{items.length !== 1 ? 's' : ''}}</span>
    </div>
    <p style="font-size:13px;color:var(--muted);margin-bottom:16px">${{subtitle}}</p>
    <div class="topic-grid">${{cards}}</div>`;
}}

function openDetail(section, index) {{
  let items;
  if (section.includes('Double')) items = CATS.double_down;
  else if (section.includes('Untapped')) items = CATS.untapped;
  else if (section.includes('Resurface')) items = CATS.resurface;
  else if (section.includes('Investigation') || section.includes('Investigate')) items = CATS.investigate;
  else items = CATS.stop_making;

  const item = items[index];
  if (!item) return;

  const vsColor = item.vs_channel > 0 ? 'var(--green)' : 'var(--red)';
  const sign = item.vs_channel > 0 ? '+' : '';

  let videoRows = '';
  (item.videos || []).forEach(v => {{
    videoRows += `<div class="vid-row">
      <a href="${{v.url}}" target="_blank">${{v.title || v.video_id}}</a>
      <span class="vr-views">${{(v.views || 0).toLocaleString()}} views</span>
    </div>`;
  }});

  const panel = document.getElementById('detailPanel');
  panel.innerHTML = `
    <button class="close-btn" onclick="closeDetail()">✕</button>
    <h2>${{item.topic}}</h2>
    <div class="dp-stat">
      <span style="color:${{vsColor}};font-weight:700;font-size:18px">${{sign}}${{item.vs_channel.toFixed(0)}}%</span>
      <span style="color:var(--muted)"> vs your channel average · ${{item.video_count}} video${{item.video_count !== 1 ? 's' : ''}} · ${{item.avg_views.toLocaleString()}} avg views</span>
    </div>
    <div class="dp-reason">${{item.reason}}</div>
    ${{item.z_score !== undefined ? `
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:20px">
      <div style="background:var(--surface2);padding:12px;border-radius:8px;text-align:center">
        <div style="font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Z-Score</div>
        <div style="font-size:18px;font-weight:700;color:${{item.z_score > 1 ? 'var(--green)' : item.z_score < -0.5 ? 'var(--red)' : 'var(--bright)'}}">${{item.z_score.toFixed(1)}}</div>
      </div>
      <div style="background:var(--surface2);padding:12px;border-radius:8px;text-align:center">
        <div style="font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Consistency</div>
        <div style="font-size:18px;font-weight:700;color:${{(item.consistency_cv || 0) < 50 ? 'var(--green)' : (item.consistency_cv || 0) > 100 ? 'var(--red)' : 'var(--gold)'}}">${{(item.consistency_cv || 0).toFixed(0)}}%</div>
      </div>
      <div style="background:var(--surface2);padding:12px;border-radius:8px;text-align:center">
        <div style="font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Confidence</div>
        <div style="font-size:14px;font-weight:600;color:${{item.confidence_level === 'high' ? 'var(--green)' : item.confidence_level === 'medium' ? 'var(--gold)' : 'var(--red)'}}">${{(item.confidence_level || 'unknown').toUpperCase()}}</div>
      </div>
      <div style="background:var(--surface2);padding:12px;border-radius:8px;text-align:center">
        <div style="font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">Trend</div>
        <div style="font-size:14px;font-weight:600;color:${{item.trend_direction === 'rising' ? 'var(--green)' : item.trend_direction === 'declining' ? 'var(--red)' : 'var(--muted)'}}">${{(item.trend_direction || 'unknown').toUpperCase()}}</div>
      </div>
    </div>` : ''}}
    ${{videoRows ? '<div class="dp-videos"><h4>Videos</h4>' + videoRows + '</div>' : ''}}
    <div class="action-btns">
      <div class="action-btn" onclick="showStats('${{item.topic}}')">
        <div class="ab-icon">📊</div>
        <div class="ab-title">Show Me the Data</div>
        <div class="ab-desc">Deep dive into the numbers</div>
      </div>
      <div class="action-btn" onclick="showStoryStarter('${{item.topic}}')">
        <div class="ab-icon">🧠</div>
        <div class="ab-title">AI Story Starter</div>
        <div class="ab-desc">Hook + narrative arc in your voice</div>
      </div>
      <div class="action-btn" onclick="showContentStarter('${{item.topic}}')">
        <div class="ab-icon">✍️</div>
        <div class="ab-title">Help Me Write This</div>
        <div class="ab-desc">Get titles, hooks & outlines in your voice</div>
      </div>
      <div class="action-btn" onclick="showFullWriter('${{item.topic}}')">
        <div class="ab-icon">📝</div>
        <div class="ab-title">Write Full Content</div>
        <div class="ab-desc">Generate a complete script draft</div>
      </div>
    </div>
    <div class="l3-panel" id="l3Stats"></div>
    <div class="l3-panel" id="l3Content"></div>
  `;

  document.getElementById('detailOverlay').classList.add('open');
  document.body.style.overflow = 'hidden';
}}

function closeDetail() {{
  document.getElementById('detailOverlay').classList.remove('open');
  document.body.style.overflow = '';
}}

// Close on overlay click (not panel click)
document.getElementById('detailOverlay').addEventListener('click', function(e) {{
  if (e.target === this) closeDetail();
}});

// Close on Escape
document.addEventListener('keydown', function(e) {{
  if (e.key === 'Escape') closeDetail();
}});

function showStats(topic) {{
  const el = document.getElementById('l3Stats');
  document.getElementById('l3Content').classList.remove('open');
  el.classList.toggle('open');
  if (!el.classList.contains('open')) return;

  // Show extended stats from analytics data
  el.innerHTML = `
    <h4>📊 Deep Stats: ${{topic}}</h4>
    <table style="width:100%;font-size:13px;border-collapse:collapse">
      <tr style="color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:1px">
        <th style="text-align:left;padding:8px 0">Metric</th>
        <th style="text-align:right;padding:8px 0">Value</th>
      </tr>
      <tr><td style="padding:6px 0;border-top:1px solid var(--border)">Topic</td><td style="text-align:right;color:var(--bright)">${{topic}}</td></tr>
      <tr><td style="padding:6px 0;border-top:1px solid var(--border)">Channel Average</td><td style="text-align:right;color:var(--muted)">Baseline</td></tr>
      <tr><td style="padding:6px 0;border-top:1px solid var(--border)">Topic is recency-weighted</td><td style="text-align:right;color:var(--accent)">Recent = 5x weight</td></tr>
    </table>
    <p style="margin-top:16px;font-size:13px;color:var(--muted)">Full topic breakdown available on the <a href="/${slug}/analytics">Analytics page</a>.</p>
  `;
}}

async function showContentStarter(topic) {{
  const el = document.getElementById('l3Content');
  document.getElementById('l3Stats').classList.remove('open');
  el.classList.toggle('open');
  if (!el.classList.contains('open')) return;

  el.innerHTML = '<div class="cs-loading">✍️ Writing in ' + CHANNEL + '\\'s voice...</div>';

  const voiceDesc = VOICE.tone || VOICE.description || 'Direct, practical, conversational';
  const phrases = (VOICE.signature_phrases || []).join(', ') || 'None identified';

  const prompt = `You are a content strategist helping the YouTube creator "${{CHANNEL}}".

CREATOR VOICE PROFILE:
${{JSON.stringify(VOICE, null, 2)}}

The creator needs help creating content about: "${{topic}}"

Generate the following IN THE CREATOR'S VOICE AND STYLE:
1. Three compelling video title options (the kind that get clicks for this creator's audience)
2. An opening hook (the first 15 seconds of the video - what they'd actually say on camera)
3. A rough outline (5-7 key points to cover)
4. One surprising angle most creators would miss

Keep it practical, not generic. Sound like ${{CHANNEL}}, not like a consultant.

Respond in this exact JSON format:
{{
  "titles": ["title1", "title2", "title3"],
  "hook": "The opening 15 seconds...",
  "outline": ["Point 1", "Point 2", "Point 3", "Point 4", "Point 5"],
  "surprise_angle": "The unexpected take..."
}}

Return ONLY valid JSON.`;

  try {{
    const r = await fetch('https://openrouter.ai/api/v1/chat/completions', {{
      method: 'POST',
      headers: {{ 'Authorization': 'Bearer ' + API_KEY, 'Content-Type': 'application/json' }},
      body: JSON.stringify({{
        model: MODEL,
        messages: [{{ role: 'user', content: prompt }}],
        temperature: 0.5,
        max_tokens: 1500
      }})
    }});
    const d = await r.json();
    let text = d.choices[0].message.content;
    if (text.includes('```')) {{
      text = text.includes('```json') ? text.split('```json')[1].split('```')[0] : text.split('```')[1].split('```')[0];
    }}
    const cs = JSON.parse(text.trim());

    let titlesHTML = cs.titles.map((t, i) => `<div style="padding:10px 14px;background:var(--surface);border:1px solid var(--border);border-radius:8px;margin-bottom:8px;color:var(--bright);font-weight:600">Option ${{i+1}}: ${{t}}</div>`).join('');

    let outlineHTML = cs.outline.map(p => `<li>${{p}}</li>`).join('');

    el.innerHTML = `
      <div class="content-starter">
        <h4 style="color:var(--accent);margin-bottom:16px">✍️ Content Starter: ${{topic}}</h4>
        <div style="margin-bottom:20px">
          <div style="font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Title Options</div>
          ${{titlesHTML}}
        </div>
        <div style="margin-bottom:20px">
          <div style="font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Opening Hook</div>
          <div class="cs-hook">"${{cs.hook}}"</div>
        </div>
        <div style="margin-bottom:20px">
          <div style="font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Outline</div>
          <ol class="cs-outline" style="padding-left:20px">${{outlineHTML}}</ol>
        </div>
        <div>
          <div style="font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">Surprise Angle</div>
          <div style="padding:12px;background:var(--accent-soft);border-radius:8px;color:var(--accent-glow);font-weight:500">${{cs.surprise_angle}}</div>
        </div>
      </div>
    `;
  }} catch (e) {{
    el.innerHTML = '<div style="color:var(--red);padding:16px">Error generating content: ' + e.message + '</div>';
  }}
}}

async function showStoryStarter(topic) {{
  const el = document.getElementById('l3Content');
  document.getElementById('l3Stats').classList.remove('open');
  el.classList.add('open');
  el.innerHTML = '<div class="cs-loading">🧠 Building story starter for ' + topic + '...</div>';

  const prompt = 'You are helping ' + CHANNEL + ' craft a STORY STARTER for YouTube topic "' + topic + '".\\n\\n' +
    'VOICE PROFILE:\\n' + JSON.stringify(VOICE, null, 2) + '\\n\\n' +
    'Return ONLY JSON:\\n' +
    '{{"opening_scene":"1-2 sentence cold open","story_arc":["beat1","beat2","beat3","beat4"],"audience_tension":"What pain/question keeps viewer watching","cta":"Natural call-to-action in creator\\'s voice"}}';

  try {{
    const r = await fetch('https://openrouter.ai/api/v1/chat/completions', {{
      method: 'POST',
      headers: {{ 'Authorization': 'Bearer ' + API_KEY, 'Content-Type': 'application/json' }},
      body: JSON.stringify({{
        model: MODEL,
        messages: [{{ role: 'user', content: prompt }}],
        temperature: 0.5,
        max_tokens: 900
      }})
    }});
    const d = await r.json();
    let text = d.choices[0].message.content;
    if (text.includes('```')) text = text.includes('```json') ? text.split('```json')[1].split('```')[0] : text.split('```')[1].split('```')[0];
    const s = JSON.parse(text.trim());
    const arc = (s.story_arc || []).map(a => '<li>' + a + '</li>').join('');
    el.innerHTML = '<div class="content-starter">' +
      '<h4 style="color:var(--accent);margin-bottom:16px">🧠 Story Starter: ' + topic + '</h4>' +
      '<div class="cs-hook">' + (s.opening_scene || '') + '</div>' +
      '<div style="margin:10px 0 6px;font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:1px">Story Arc</div>' +
      '<ol class="cs-outline" style="padding-left:20px">' + arc + '</ol>' +
      '<div style="margin-top:12px"><strong style="color:var(--bright)">Audience tension:</strong> ' + (s.audience_tension || '') + '</div>' +
      '<div style="margin-top:8px"><strong style="color:var(--bright)">CTA:</strong> ' + (s.cta || '') + '</div>' +
      '</div>';
  }} catch (e) {{
    el.innerHTML = '<div style="color:var(--red);padding:16px">Error generating story starter: ' + e.message + '</div>';
  }}
}}

async function showFullWriter(topic) {{
  const el = document.getElementById('l3Content');
  document.getElementById('l3Stats').classList.remove('open');
  el.classList.add('open');
  el.innerHTML = '<div class="cs-loading">📝 Writing full content draft for ' + topic + '...</div>';

  const prompt = 'Write a complete YouTube script draft for ' + CHANNEL + ' on topic "' + topic + '".\\n' +
    'Use creator voice from profile:\\n' + JSON.stringify(VOICE, null, 2) + '\\n\\n' +
    'Return ONLY JSON:\\n' +
    '{{"title":"","script":"full script with sections","description":"youtube description","cta":"end CTA"}}';

  try {{
    const r = await fetch('https://openrouter.ai/api/v1/chat/completions', {{
      method: 'POST',
      headers: {{ 'Authorization': 'Bearer ' + API_KEY, 'Content-Type': 'application/json' }},
      body: JSON.stringify({{
        model: MODEL,
        messages: [{{ role: 'user', content: prompt }}],
        temperature: 0.6,
        max_tokens: 1800
      }})
    }});
    const d = await r.json();
    let text = d.choices[0].message.content;
    if (text.includes('```')) text = text.includes('```json') ? text.split('```json')[1].split('```')[0] : text.split('```')[1].split('```')[0];
    const s = JSON.parse(text.trim());
    el.innerHTML = '<div class="content-starter">' +
      '<h4 style="color:var(--accent);margin-bottom:10px">📝 Full Content Draft: ' + topic + '</h4>' +
      '<div style="margin-bottom:10px"><strong style="color:var(--bright)">Title:</strong> ' + (s.title || '') + '</div>' +
      '<div style="white-space:pre-wrap;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px">' + (s.script || '') + '</div>' +
      '<div style="margin-top:10px"><strong style="color:var(--bright)">Description:</strong> ' + (s.description || '') + '</div>' +
      '<div style="margin-top:8px"><strong style="color:var(--bright)">CTA:</strong> ' + (s.cta || '') + '</div>' +
      '</div>';
  }} catch (e) {{
    el.innerHTML = '<div style="color:var(--red);padding:16px">Error generating full content: ' + e.message + '</div>';
  }}
}}

function quickGenerate(mode) {{
  const panel = document.getElementById('quickAIPanel');
  const modal = document.getElementById('quickAIModal');
  const title = mode === 'story' ? 'AI Story Starter' : 'AI Full Content Writer';
  const action = mode === 'story' ? 'AI Story Starter' : 'Write Full Content';
  panel.innerHTML = '<button class="close-btn" onclick="document.getElementById(\'quickAIModal\').classList.remove(\'open\')">✕</button>' +
    '<h2>' + title + '</h2>' +
    '<div class="dp-reason">Open any topic card and choose <strong>' + action + '</strong> to generate output for that specific topic.</div>' +
    '<div class="dp-reason">Tip: use the new <strong>Recommended Future Content</strong> section to pick the topic with the highest opportunity score first.</div>';
  modal.classList.add('open');
}}

// Init
renderFutureIdeas();
renderDashboard();
</script></body></html>"""
    (bp / "dashboard.html").write_text(html, encoding="utf-8")


# ─── ANALYTICS PAGE ─────────────────────────────────────────────
def _build_analytics(bp, data):
    ch = data["manifest"].get("channel", "Unknown")
    slug = data["slug"]
    analytics = data.get("analytics_report", {})
    timeline = analytics.get("topic_timeline", {})
    sources = data.get("sources", [])
    performance = _normalize_topic_performance(
        analytics,
        sources,
        data.get("channel_metrics", {}).get("channel_avg_views", 0),
    )
    content_categories = analytics.get("content_categories", {})
    future_suggestions = analytics.get("future_content_suggestions", [])
    source_map = {s["source_id"]: s for s in sources}
    all_topics = set(timeline.keys()) | set(performance.keys())

    rows = ""
    for topic in sorted(all_topics, key=lambda t: -performance.get(t,{}).get("weighted_avg_views",0)):
        tl = timeline.get(topic, {})
        perf = performance.get(topic, {})
        count = tl.get("count", perf.get("video_count", 0))
        avg = perf.get("weighted_avg_views", 0)
        vs = perf.get("vs_channel_avg", 0)
        vids = tl.get("videos", [])

        if len(vids) >= 3:
            sv = sorted(vids, key=lambda v: v.get("published", ""))
            fh = len(sv) // 2
            sh = len(sv) - fh
            if sh > fh: tr, ti, tc = "rising", "↑ Rising", "var(--green)"
            elif fh > sh: tr, ti, tc = "declining", "↓ Declining", "var(--red)"
            else: tr, ti, tc = "steady", "→ Steady", "var(--gold)"
        elif count == 0:
            tr, ti, tc = "dormant", "◌ Dormant", "var(--muted)"
        else:
            tr, ti, tc = "steady", "→ Steady", "var(--gold)"

        vc = "var(--green)" if vs > 0 else "var(--red)" if vs < 0 else "var(--muted)"
        sign = "+" if vs > 0 else ""

        # Get video titles for tooltip
        vid_titles = []
        for v in vids[:3]:
            vid = v.get("video_id", "")
            s = source_map.get(vid, {})
            vid_titles.append(s.get("title", vid)[:40])

        rows += f'<tr data-trend="{tr}"><td style="color:var(--bright);font-weight:500">{topic}</td><td>{count}</td><td>{avg:,}</td><td style="color:{vc};font-weight:600">{sign}{vs}%</td><td><span style="color:{tc};font-size:12px">{ti}</span></td></tr>'

    if not rows:
        rows = '<tr data-trend="steady"><td colspan="5" style="color:var(--muted)">No topic performance data available yet.</td></tr>'

    category_rows = ""
    for topic, meta in sorted(content_categories.items(), key=lambda kv: -kv[1].get("weighted_avg_views", 0))[:20]:
        category_rows += (
            f'<tr><td style="color:var(--bright);font-weight:500">{topic}</td>'
            f'<td>{meta.get("category", "education")}</td>'
            f'<td>{meta.get("video_count", 0)}</td>'
            f'<td>{meta.get("weighted_avg_views", 0):,}</td>'
            f'<td style="color:{"var(--green)" if meta.get("momentum_flag") == "hot" else "var(--muted)"}">{meta.get("momentum_flag", "stable")}</td></tr>'
        )

    suggestion_rows = ""
    for s in future_suggestions[:10]:
        suggestion_rows += (
            f'<tr><td style="color:var(--bright);font-weight:500">{s.get("topic", "")}</td>'
            f'<td>{s.get("category", "education")}</td>'
            f'<td>{s.get("trend", "steady")}</td>'
            f'<td>{s.get("avg_engagement_rate", 0):.2f}%</td>'
            f'<td>{s.get("opportunity_score", 0):.1f}</td>'
            f'<td style="max-width:280px">{(s.get("idea_angles") or [""])[0]}</td></tr>'
        )

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{ch} Analytics · TrueInfluenceAI</title>{FONTS}
<style>{THEME_CSS}{NAV_CSS}
table{{width:100%;border-collapse:collapse;margin-top:16px}}
th{{text-align:left;padding:14px 16px;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:var(--muted);border-bottom:2px solid var(--border);font-weight:600}}
td{{padding:12px 16px;font-size:13px;border-bottom:1px solid rgba(26,28,42,.5)}}
tr:hover{{background:rgba(99,102,241,.03)}}
.fbar{{display:flex;gap:8px;margin-bottom:24px;flex-wrap:wrap}}
.fb{{padding:8px 16px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--muted);cursor:pointer;font-size:12px;font-weight:500;transition:all .2s;font-family:inherit}}
.fb:hover,.fb.active{{border-color:var(--accent);color:var(--accent-glow);background:var(--accent-soft)}}
.note{{font-size:12px;color:var(--muted);margin-bottom:24px;padding:12px 16px;background:var(--surface);border-radius:8px;border:1px solid var(--border)}}
</style></head><body>
{_nav_html(ch, slug, 'analytics')}
<div class="container">
<h2>Content Analytics</h2>
<p class="sub">Every topic scored and weighted — recent content counts 5x more</p>
<div class="note">💡 Views are recency-weighted. A topic that performs well in recent videos scores higher than the same views from a year ago.</div>
<div class="fbar">
<button class="fb active" onclick="ft('all',this)">All ({len(all_topics)})</button>
<button class="fb" onclick="ft('rising',this)">↑ Rising</button>
<button class="fb" onclick="ft('declining',this)">↓ Declining</button>
<button class="fb" onclick="ft('steady',this)">→ Steady</button>
</div>
<table><thead><tr><th>Topic</th><th>Videos</th><th>Wtd Avg Views</th><th>vs Channel Avg</th><th>Trend</th></tr></thead>
<tbody id="topicRows">{rows}</tbody></table>

<h3 style="margin-top:28px">Topic Categories</h3>
<p class="sub" style="margin-bottom:10px">Topics grouped by intent so strategy is easier to execute.</p>
<table><thead><tr><th>Topic</th><th>Category</th><th>Videos</th><th>Wtd Avg Views</th><th>Momentum</th></tr></thead>
<tbody>{category_rows or '<tr><td colspan="5" style="color:var(--muted)">No category data yet.</td></tr>'}</tbody></table>

<h3 style="margin-top:28px">Future Content Suggestions</h3>
<p class="sub" style="margin-bottom:10px">Prioritized by historical performance + follower engagement.</p>
<table><thead><tr><th>Topic</th><th>Category</th><th>Trend</th><th>Engagement</th><th>Score</th><th>Suggested Angle</th></tr></thead>
<tbody>{suggestion_rows or '<tr><td colspan="6" style="color:var(--muted)">No future suggestions available yet.</td></tr>'}</tbody></table>
</div>
<script>
function ft(t,el){{document.querySelectorAll('.fb').forEach(b=>b.classList.remove('active'));el.classList.add('active');document.querySelectorAll('#topicRows tr').forEach(r=>{{r.style.display=(t==='all'||r.dataset.trend===t)?'':'none';}});}}
</script></body></html>"""
    (bp / "analytics.html").write_text(html, encoding="utf-8")


# ─── DISCUSS PAGE ───────────────────────────────────────────────
def _build_discuss(bp, data):
    ch = data["manifest"].get("channel", "Unknown")
    slug = data["slug"]
    voice = data.get("voice_profile", {})
    chunks = data.get("chunks", [])
    sources = data.get("sources", [])

    src_map = json.dumps({s["source_id"]: {"title": s.get("title", ""), "url": s.get("url", "")} for s in sources})
    chunks_js = json.dumps([{"id": c["chunk_id"], "vid": c["video_id"], "text": c["text"], "ts": c.get("timestamp", 0), "emb": c.get("embedding", [])} for c in chunks])
    voice_js = json.dumps(voice)

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Discuss {ch} · TrueInfluenceAI</title>{FONTS}
<style>{THEME_CSS}{NAV_CSS}
body{{display:flex;flex-direction:column;height:100vh}}
.chat-wrap{{flex:1;max-width:760px;width:100%;margin:0 auto;display:flex;flex-direction:column;padding:24px;overflow:hidden}}
.chat-intro{{text-align:center;padding:32px 0 16px}}
.chat-intro h3{{font-family:'Fraunces',serif;font-size:22px;color:var(--bright);margin-bottom:8px}}
.chat-intro p{{font-size:14px;color:var(--muted)}}
.msgs{{flex:1;overflow-y:auto;padding-bottom:16px;scroll-behavior:smooth}}
.msg{{margin-bottom:14px;padding:16px 18px;border-radius:14px;max-width:85%;line-height:1.6;font-size:14px}}
.msg.user{{background:var(--accent-soft);border:1px solid rgba(99,102,241,.2);margin-left:auto;color:var(--bright)}}
.msg.ai{{background:var(--surface);border:1px solid var(--border)}}
.msg .refs{{margin-top:10px;padding-top:8px;border-top:1px solid var(--border);font-size:11px;color:var(--muted)}}
.msg .refs a{{color:var(--accent)}}
.starters{{display:flex;gap:8px;flex-wrap:wrap;justify-content:center;margin-bottom:16px}}
.st{{padding:8px 16px;background:var(--surface);border:1px solid var(--border);border-radius:20px;font-size:12px;color:var(--muted);cursor:pointer;transition:all .2s;font-family:inherit}}
.st:hover{{border-color:var(--accent);color:var(--accent-glow)}}
.ibar{{display:flex;gap:10px;padding:16px 0;border-top:1px solid var(--border);flex-shrink:0}}
.ibar input{{flex:1;padding:14px 18px;background:var(--surface);border:1px solid var(--border);border-radius:12px;color:var(--bright);font-size:14px;outline:none;font-family:inherit}}
.ibar input:focus{{border-color:var(--accent)}}
.ibar button{{padding:14px 24px;background:var(--accent);color:#fff;border:none;border-radius:12px;font-weight:600;cursor:pointer;font-family:inherit;transition:background .2s}}
.ibar button:hover{{background:var(--accent-glow)}}
</style></head><body>
{_nav_html(ch, slug, 'discuss')}
<div class="chat-wrap">
<div class="chat-intro">
<h3>Ask {ch} Anything</h3>
<p>AI trained on their content, speaking in their voice</p>
</div>
<div class="starters">
<span class="st" onclick="askQ('What topics does {ch} focus on most?')">Top topics</span>
<span class="st" onclick="askQ('What advice does {ch} give to beginners?')">Beginner advice</span>
<span class="st" onclick="askQ('How has {ch}\\'s content evolved recently?')">Content evolution</span>
<span class="st" onclick="askQ('What\\'s {ch}\\'s take on cost of living abroad?')">Cost of living</span>
</div>
<div class="msgs" id="msgs"></div>
<div class="ibar"><input id="qi" placeholder="Ask about {ch}'s content..." onkeydown="if(event.key==='Enter')askQ()"><button onclick="askQ()">Ask</button></div>
</div>

<script>
const CHUNKS={chunks_js};
const SOURCES={src_map};
const VOICE={voice_js};
const API_KEY='{OPENROUTER_API_KEY}';
const MODEL='{OPENROUTER_MODEL_ID}';

function dot(a,b){{let s=0;for(let i=0;i<a.length;i++)s+=a[i]*b[i];return s}}
function mag(a){{return Math.sqrt(a.reduce((s,v)=>s+v*v,0))}}
function cosine(a,b){{if(!a.length||!b.length)return 0;return dot(a,b)/(mag(a)*mag(b))}}

async function getEmbedding(text){{
  const r=await fetch('https://openrouter.ai/api/v1/embeddings',{{
    method:'POST',headers:{{'Authorization':'Bearer '+API_KEY,'Content-Type':'application/json'}},
    body:JSON.stringify({{model:'{EMBEDDING_MODEL}',input:[text]}})
  }});
  const d=await r.json();return d.data[0].embedding;
}}

function searchChunks(qEmb,k=5){{
  const scored=CHUNKS.map(c=>{{
    const sim=cosine(qEmb,c.emb);
    return{{...c,score:sim}};
  }});
  scored.sort((a,b)=>b.score-a.score);
  return scored.slice(0,k);
}}

async function askQ(q){{
  const input=document.getElementById('qi');
  if(!q)q=input.value.trim();
  if(!q)return;
  input.value='';

  const md=document.getElementById('msgs');
  md.innerHTML+=`<div class="msg user">${{q}}</div>`;
  md.innerHTML+=`<div class="msg ai" id="thinking">Thinking...</div>`;
  md.scrollTop=md.scrollHeight;

  try{{
    const qEmb=await getEmbedding(q);
    const hits=searchChunks(qEmb,5);
    const context=hits.map(h=>`[Source: ${{SOURCES[h.vid]?.title||h.vid}}]\\n${{h.text}}`).join('\\n---\\n');

    const sysPrompt=`You ARE ${{'{ch}'}}. You are speaking directly to a viewer as yourself.

YOUR VOICE:
${{JSON.stringify(VOICE)}}

RULES:
- Speak as ${{'{ch}'}} in first person. Use "I", "my experience", "when I moved to...", etc.
- Draw from ALL your knowledge as one unified expertise.
- NEVER cite sources inline. No "[Source: ...]" or "[thestar.com.my]" or "In my video about..." or any bracketed references. Just speak naturally.
- Do NOT mention video titles anywhere in your response. The UI will add relevant video links automatically below your answer.
- Be direct, practical, and conversational — the way you talk in your videos.
- Use your signature phrases naturally when they fit.
- Keep responses focused and actionable. No fluff.
- Do NOT end with video recommendations — the system handles that separately.
- Do NOT use bullet points or numbered lists. Talk naturally in paragraphs like you would on camera.`;

    // Build the video references separately
    const relevantVids = [];
    const seenVids = new Set();
    hits.forEach(h => {{
      if (!seenVids.has(h.vid)) {{
        seenVids.add(h.vid);
        const s = SOURCES[h.vid];
        if (s) relevantVids.push(s);
      }}
    }});

    const r=await fetch('https://openrouter.ai/api/v1/chat/completions',{{
      method:'POST',headers:{{'Authorization':'Bearer '+API_KEY,'Content-Type':'application/json'}},
      body:JSON.stringify({{model:MODEL,messages:[
        {{role:'system',content:sysPrompt}},
        {{role:'user',content:`Here is your knowledge to draw from (do NOT cite these individually — synthesize into one natural response):\\n\\n${{context}}\\n\\nViewer question: ${{q}}`}}
      ],temperature:0.5,max_tokens:1200}})
    }});
    const d=await r.json();
    let answer=d.choices[0].message.content;

    // Build video links footer
    let refs = '';
    if (relevantVids.length > 0) {{
      refs = '<div class="refs">📺 Related videos: ';
      relevantVids.slice(0, 3).forEach(v => {{
        refs += `<a href="${{v.url}}" target="_blank">${{v.title}}</a> · `;
      }});
      refs += '</div>';
    }}

    // Strip any video recommendations the LLM added despite instructions
    answer = answer.replace(/You might want to check out.*$/s, '').replace(/Check out these videos.*$/s, '').trim();
    document.getElementById('thinking').outerHTML=`<div class="msg ai">${{answer.replace(/\\n/g,'<br>')}}${{refs}}</div>`;
  }}catch(e){{
    document.getElementById('thinking').outerHTML=`<div class="msg ai" style="color:var(--red)">Error: ${{e.message}}</div>`;
  }}
  md.scrollTop=md.scrollHeight;
}}
</script></body></html>"""
    (bp / "discuss.html").write_text(html, encoding="utf-8")
