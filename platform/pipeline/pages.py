"""
TrueInfluenceAI - Page Builder (Merged)
========================================
Three pages: Index, Dashboard (actionable intelligence), Discuss.
Dashboard and Analytics are MERGED — one page, one code path.
All actionable intelligence powered by build_actionable_core.py.
"""

import os, json
from pathlib import Path
from datetime import datetime

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL_ID = os.getenv("OPENROUTER_MODEL_ID", "google/gemini-2.5-flash-lite:online")
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


# ─── Build All Pages ───────────────────────────────────────────
def build_all_pages(bundle_dir, slug):
    """Build all creator pages: index, dashboard, discuss."""
    bundle_dir = Path(bundle_dir)
    data = _load_bundle(bundle_dir)
    data["slug"] = slug

    print(f"Building pages for {slug}...")
    _build_index(bundle_dir, data)
    _build_dashboard(bundle_dir, data)
    _build_discuss(bundle_dir, data)
    print(f"   All pages built")


# ─── INDEX PAGE ─────────────────────────────────────────────────
def _build_index(bp, data):
    ch = data["manifest"].get("channel", "Unknown")
    slug = data["slug"]
    m = data.get("channel_metrics", {})
    v = data.get("voice_profile", {})
    tone = v.get("tone", "")
    tv = data["manifest"].get("total_videos", 0)
    av = m.get("channel_avg_views", 0)
    tvw = m.get("total_views", 0)

    topics = data.get("analytics_report", {}).get("topic_frequency", {})
    topic_count = len(topics) if isinstance(topics, dict) else 0

    base = f"/c/{slug}"

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
.cards{{display:grid;grid-template-columns:repeat(2,1fr);gap:20px;max-width:700px;margin:60px auto;padding:0 24px}}
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
<div class="stat"><div class="n">{topic_count}</div><div class="l">Topics</div></div>
</div>
{'<div class="voice"><div class="vl">Voice Profile</div><div class="vt">'+tone+'</div></div>' if tone else ''}
</div>
<div class="cards">
<a class="card" href="{base}/dashboard"><div class="icon">🎯</div><h3>Dashboard</h3><p>Actionable intelligence — what to make next, hidden gems, and content in your voice.</p>
<span class="badge" style="background:var(--green-soft);color:var(--green)">{topic_count} topics analyzed</span></a>
<a class="card" href="{base}/discuss"><div class="icon">💬</div><h3>Discuss</h3><p>Chat with AI trained on {ch}'s content and voice.</p>
<span class="badge" style="background:var(--gold-soft);color:var(--gold)">AI-Powered</span></a>
</div>
<div class="footer">Powered by <a href="/" style="color:var(--accent)">TrueInfluenceAI</a> · Built by WinTech Partners</div>
</body></html>"""
    (bp / "index.html").write_text(html, encoding="utf-8")
    print(f"   [OK] index.html")


# ─── DASHBOARD PAGE (the one page to rule them all) ─────────────
def _build_dashboard(bp, data):
    """Single actionable intelligence page. Replaces old dashboard + analytics."""
    try:
        from pipeline.build_actionable_core import build_analytics_html
    except ImportError:
        from build_actionable_core import build_analytics_html
    html = build_analytics_html(bp, data)
    (bp / "dashboard.html").write_text(html, encoding="utf-8")
    print(f"   [OK] dashboard.html ({len(html):,} bytes)")


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
    base = f"/c/{slug}"

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
<span class="st" onclick="askQ('What makes {ch}\\'s perspective unique?')">Unique perspective</span>
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
- Speak as ${{'{ch}'}} in first person. Use "I", "my experience", etc.
- Draw from ALL your knowledge as one unified expertise.
- NEVER cite sources inline. No "[Source: ...]" or bracketed references. Just speak naturally.
- Do NOT mention video titles in your response. The UI adds relevant links below.
- Be direct, practical, and conversational.
- Use your signature phrases naturally when they fit.
- Keep responses focused and actionable. No fluff.
- Do NOT end with video recommendations.
- Do NOT use bullet points or numbered lists. Talk naturally in paragraphs.`;

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

    let refs = '';
    if (relevantVids.length > 0) {{
      refs = '<div class="refs">📺 Related videos: ';
      relevantVids.slice(0, 3).forEach(v => {{
        refs += `<a href="${{v.url}}" target="_blank">${{v.title}}</a> · `;
      }});
      refs += '</div>';
    }}

    answer = answer.replace(/You might want to check out.*$/s, '').replace(/Check out these videos.*$/s, '').trim();
    document.getElementById('thinking').outerHTML=`<div class="msg ai">${{answer.replace(/\\n/g,'<br>')}}${{refs}}</div>`;
  }}catch(e){{
    document.getElementById('thinking').outerHTML=`<div class="msg ai" style="color:var(--red)">Error: ${{e.message}}</div>`;
  }}
  md.scrollTop=md.scrollHeight;
}}
</script></body></html>"""
    (bp / "discuss.html").write_text(html, encoding="utf-8")
    print(f"   [OK] discuss.html")
