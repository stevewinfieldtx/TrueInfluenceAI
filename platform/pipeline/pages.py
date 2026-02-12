"""
TrueInfluenceAI - Cloud Page Builder
======================================
Generates all creator HTML pages for cloud serving.
Pages use /c/{slug}/ paths for navigation.
"""

import os, json
from pathlib import Path
from datetime import datetime

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen/qwen3-embedding-8b")

# Shared CSS variables
THEME_CSS = """
:root{--bg:#0a0b10;--surface:#0f1118;--border:#1c1f2e;--accent:#7c6aff;--accent-glow:#9d8fff;
--text:#c8c8d4;--bright:#f0f0f8;--muted:#5a5b70;--green:#6bcb77;--red:#ff6b6b;--gold:#ffc857}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
a{color:var(--accent-glow);text-decoration:none}a:hover{color:var(--bright)}
"""

NAV_CSS = """
nav{padding:16px 32px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border);background:var(--surface);position:sticky;top:0;z-index:50;backdrop-filter:blur(12px)}
nav .logo{font-family:'Playfair Display',serif;font-size:20px;font-weight:900;color:var(--bright)}
nav .logo span{color:var(--accent)}
nav .links a{color:var(--muted);font-size:14px;text-decoration:none;margin-left:24px;transition:color .2s}
nav .links a:hover{color:var(--bright)}
nav .links a.active{color:var(--accent);font-weight:600}
"""

FONTS = '<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;700&family=Playfair+Display:wght@700;900&display=swap" rel="stylesheet">'


def _nav_html(channel, slug, active):
    base = f"/c/{slug}"
    def cls(name):
        return ' class="active"' if name == active else ''
    return f"""<nav>
<div class="logo"><span>TrueInfluence</span>AI - {channel}</div>
<div class="links">
<a href="{base}"{cls('home')}>Home</a>
<a href="{base}/dashboard"{cls('dashboard')}>Dashboard</a>
<a href="{base}/analytics"{cls('analytics')}>Analytics</a>
<a href="{base}/discuss"{cls('discuss')}>Discuss</a>
</div></nav>"""


def build_all_pages(bundle_dir, slug):
    """Build all 4 creator pages."""
    bundle_dir = Path(bundle_dir)
    data = _load_bundle(bundle_dir)
    data["slug"] = slug
    print(f"Building pages for {slug}...")
    _build_index(bundle_dir, data)
    _build_dashboard(bundle_dir, data)
    _build_analytics(bundle_dir, data)
    _build_discuss(bundle_dir, data)
    print(f"   All 4 pages built")


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
    eng = m.get("channel_engagement_rate", 0)
    topics = data.get("analytics_report", {}).get("total_topics", 0)
    base = f"/c/{slug}"

    voice_block = f'<div class="voice-bar"><div class="vl">Voice Profile</div><div class="vt">{tone}</div></div>' if tone else ""

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{ch} -- TrueInfluenceAI</title>{FONTS}
<style>{THEME_CSS}
.hero{{text-align:center;padding:60px 24px 40px;background:linear-gradient(135deg,var(--surface) 0%,#141630 50%,var(--surface) 100%);border-bottom:1px solid var(--border)}}
.hero h1{{font-family:'Playfair Display',serif;font-size:42px;font-weight:900;color:var(--bright);margin-bottom:8px}}
.hero h1 span{{color:var(--accent)}}
.hero .sub{{font-size:15px;color:var(--muted);max-width:600px;margin:0 auto 24px;line-height:1.6}}
.stats-row{{display:flex;justify-content:center;gap:32px;flex-wrap:wrap;margin-top:24px}}
.stat{{text-align:center}}.stat .sv{{font-size:28px;font-weight:700;color:var(--bright)}}
.stat .sl{{font-size:11px;color:var(--muted);text-transform:uppercase;margin-top:2px;letter-spacing:.5px}}
.cards{{display:grid;grid-template-columns:repeat(3,1fr);gap:24px;max-width:1000px;margin:48px auto;padding:0 24px}}
.card{{background:var(--surface);border:1px solid var(--border);border-radius:16px;padding:36px 28px;text-align:center;cursor:pointer;transition:all .2s;text-decoration:none;color:inherit}}
.card:hover{{transform:translateY(-4px);border-color:var(--accent);box-shadow:0 8px 32px rgba(124,106,255,.15)}}
.card .icon{{font-size:48px;margin-bottom:16px}}.card h3{{font-size:18px;color:var(--bright);margin-bottom:8px}}
.card p{{font-size:13px;color:var(--muted);line-height:1.5}}
.card .tag{{display:inline-block;margin-top:14px;padding:4px 14px;border-radius:20px;font-size:11px;font-weight:600;background:rgba(124,106,255,.12);color:var(--accent-glow)}}
.voice-bar{{max-width:700px;margin:28px auto 0;padding:16px 24px;background:#141630;border-radius:12px;border:1px solid var(--border);text-align:left}}
.voice-bar .vl{{font-size:10px;color:var(--accent);text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:6px}}
.voice-bar .vt{{font-size:13px;color:var(--muted);line-height:1.5;font-style:italic}}
.footer{{text-align:center;padding:40px 24px;font-size:11px;color:#333}}
@media(max-width:700px){{.cards{{grid-template-columns:1fr}}.stats-row{{gap:20px}}}}
</style></head><body>
<div class="hero">
<h1><span>TrueInfluence</span>AI</h1>
<div class="sub">Creator Intelligence Platform for <strong style="color:var(--bright)">{ch}</strong></div>
<div class="stats-row">
<div class="stat"><div class="sv">{tv}</div><div class="sl">Videos Analyzed</div></div>
<div class="stat"><div class="sv">{tc:,}</div><div class="sl">Content Chunks</div></div>
<div class="stat"><div class="sv">{av:,}</div><div class="sl">Avg Views</div></div>
<div class="stat"><div class="sv">{tvw:,}</div><div class="sl">Total Views</div></div>
<div class="stat"><div class="sv">{eng}%</div><div class="sl">Engagement</div></div>
<div class="stat"><div class="sv">{topics}</div><div class="sl">Topics Tracked</div></div>
</div>{voice_block}</div>
<div class="cards">
<a class="card" href="{base}/dashboard"><div class="icon">&#128202;</div><h3>Dashboard</h3><p>Strategic insights, content gaps, and AI-powered recommendations.</p><span class="tag">Interactive</span></a>
<a class="card" href="{base}/analytics"><div class="icon">&#128200;</div><h3>Analytics</h3><p>Topic trends, performance vs channel average, content evolution.</p><span class="tag">{topics} Topics</span></a>
<a class="card" href="{base}/discuss"><div class="icon">&#128172;</div><h3>Discuss</h3><p>Chat with AI trained on {ch}'s content and expertise.</p><span class="tag">AI-Powered</span></a>
</div>
<div class="footer"><a href="/" style="color:var(--muted);font-size:13px">Back to TrueInfluenceAI Platform</a><br><br>Powered by <a href="/" style="color:var(--accent)">TrueInfluenceAI</a> - Built by WinTech Partners</div>
</body></html>"""
    (bp / "index.html").write_text(html, encoding="utf-8")


def _build_dashboard(bp, data):
    ch = data["manifest"].get("channel", "Unknown")
    slug = data["slug"]
    insights_data = data.get("insights", {})
    analytics = data.get("analytics_report", {})
    direction = insights_data.get("strategic_direction", "")
    insight_list = insights_data.get("insights", [])
    gaps = insights_data.get("content_gaps", [])
    recs = analytics.get("recommendations", {}).get("recommendations", [])

    insight_html = ""
    for ins in insight_list[:12]:
        c = {"opportunity":"var(--green)","warning":"var(--red)","strength":"var(--accent)","trend":"var(--gold)"}.get(ins.get("type",""),"var(--accent)")
        p = {"high":"HIGH","medium":"MED","low":"LOW"}.get(ins.get("priority",""),"")
        insight_html += f'<div class="icard" style="border-left:3px solid {c}"><div class="ih"><span>{p}</span><span style="color:{c}">{ins.get("type","")}</span></div><h4>{ins.get("title","")}</h4><p>{ins.get("description","")}</p><div class="ia">Action: {ins.get("action","")}</div></div>'

    gap_html = ""
    for g in gaps[:8]:
        gap_html += f'<div class="gcard"><div class="gscore">{g.get("opportunity_score",0)}</div><div><h4>{g.get("topic","")}</h4><p>{g.get("reasoning","")}</p></div></div>'

    rec_html = ""
    for r in recs[:7]:
        icon = {"double_down":"TARGET","explore":"EXPLORE","evolve":"EVOLVE","optimize":"OPTIMIZE"}.get(r.get("category",""),"TIP")
        rec_html += f'<div class="rcard"><span style="font-size:14px;color:var(--accent)">[{icon}]</span><h4>{r.get("title","")}</h4><p>{r.get("description","")}</p><span class="rimpact">Impact: {r.get("expected_impact","").upper()}</span></div>'

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{ch} Dashboard -- TrueInfluenceAI</title>{FONTS}
<style>{THEME_CSS}{NAV_CSS}
.container{{max-width:1100px;margin:0 auto;padding:32px 24px}}
h2{{font-family:'Playfair Display',serif;font-size:28px;color:var(--bright);margin-bottom:8px}}
.ssub{{color:var(--muted);font-size:14px;margin-bottom:24px}}
.dir-box{{background:#141630;border:1px solid var(--border);border-radius:12px;padding:24px;margin-bottom:40px;font-size:15px;line-height:1.7}}
.igrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px;margin-bottom:48px}}
.icard{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px}}
.ih{{display:flex;justify-content:space-between;font-size:11px;margin-bottom:8px;text-transform:uppercase;letter-spacing:.5px}}
.icard h4{{color:var(--bright);font-size:15px;margin-bottom:6px}}
.icard p{{font-size:13px;color:var(--muted);line-height:1.5;margin-bottom:8px}}
.ia{{font-size:12px;color:var(--accent);font-weight:500}}
.ggrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:16px;margin-bottom:48px}}
.gcard{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px;display:flex;gap:16px;align-items:flex-start}}
.gscore{{font-family:'Playfair Display',serif;font-size:32px;font-weight:900;color:var(--green);min-width:50px}}
.gcard h4{{color:var(--bright);font-size:14px;margin-bottom:4px}}
.gcard p{{font-size:12px;color:var(--muted);line-height:1.4}}
.rgrid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:16px;margin-bottom:48px}}
.rcard{{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:20px}}
.rcard h4{{color:var(--bright);font-size:15px;margin:8px 0 6px}}.rcard p{{font-size:13px;color:var(--muted);line-height:1.5;margin-bottom:8px}}
.rimpact{{font-size:11px;color:var(--gold);font-weight:600}}
h3{{color:var(--bright);margin-bottom:16px;font-size:18px}}
</style></head><body>
{_nav_html(ch, slug, 'dashboard')}
<div class="container">
<h2>Strategic Dashboard</h2><p class="ssub">AI-powered insights and recommendations</p>
{'<div class="dir-box"><strong>Strategic Direction:</strong> '+direction+'</div>' if direction else ''}
<h3>Content Insights</h3><div class="igrid">{insight_html}</div>
<h3>Content Opportunities</h3><div class="ggrid">{gap_html}</div>
<h3>Recommendations</h3><div class="rgrid">{rec_html}</div>
</div></body></html>"""
    (bp / "dashboard.html").write_text(html, encoding="utf-8")


def _build_analytics(bp, data):
    ch = data["manifest"].get("channel", "Unknown")
    slug = data["slug"]
    analytics = data.get("analytics_report", {})
    timeline = analytics.get("topic_timeline", {})
    performance = analytics.get("topic_performance", {})
    all_topics = set(timeline.keys()) | set(performance.keys())

    rows = ""
    for topic in sorted(all_topics, key=lambda t: -performance.get(t,{}).get("weighted_avg_views",0)):
        tl = timeline.get(topic,{})
        perf = performance.get(topic,{})
        count = tl.get("count", perf.get("video_count",0))
        avg = perf.get("weighted_avg_views",0)
        vs = perf.get("vs_channel_avg",0)
        vids = tl.get("videos",[])
        if len(vids)>=3:
            sv = sorted(vids, key=lambda v:v.get("published",""))
            fh = len(sv)//2; sh = len(sv)-fh
            if sh>fh: tr,ti,tc="rising","UP","var(--green)"
            elif fh>sh: tr,ti,tc="declining","DOWN","var(--red)"
            else: tr,ti,tc="steady","FLAT","var(--gold)"
        elif count==0: tr,ti,tc="dormant","ZZZ","var(--muted)"
        else: tr,ti,tc="steady","FLAT","var(--gold)"
        vc = "var(--green)" if vs>0 else "var(--red)" if vs<0 else "var(--muted)"
        sign = "+" if vs>0 else ""
        rows += f'<tr data-trend="{tr}"><td>{topic}</td><td>{count}</td><td>{avg:,}</td><td style="color:{vc}">{sign}{vs}%</td><td><span style="color:{tc}">{ti} {tr}</span></td></tr>'

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{ch} Analytics -- TrueInfluenceAI</title>{FONTS}
<style>{THEME_CSS}{NAV_CSS}
.container{{max-width:1100px;margin:0 auto;padding:32px 24px}}
h2{{font-family:'Playfair Display',serif;font-size:28px;color:var(--bright);margin-bottom:8px}}
.ssub{{color:var(--muted);font-size:14px;margin-bottom:24px}}
table{{width:100%;border-collapse:collapse;margin-top:16px}}
th{{text-align:left;padding:12px 16px;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--muted);border-bottom:2px solid var(--border)}}
td{{padding:12px 16px;font-size:14px;border-bottom:1px solid rgba(28,31,46,.4)}}
tr:hover{{background:rgba(15,17,24,.6)}}
.fbar{{display:flex;gap:12px;margin-bottom:24px;flex-wrap:wrap}}
.fb{{padding:8px 16px;border-radius:8px;border:1px solid var(--border);background:var(--surface);color:var(--muted);cursor:pointer;font-size:12px;font-weight:500;transition:all .2s}}
.fb:hover,.fb.active{{border-color:var(--accent);color:var(--accent);background:rgba(124,106,255,.05)}}
</style></head><body>
{_nav_html(ch, slug, 'analytics')}
<div class="container">
<h2>Content Analytics</h2><p class="ssub">Recency-weighted topic performance and evolution</p>
<div class="fbar">
<button class="fb active" onclick="ft('all',this)">All ({len(all_topics)})</button>
<button class="fb" onclick="ft('rising',this)">Rising</button>
<button class="fb" onclick="ft('declining',this)">Declining</button>
<button class="fb" onclick="ft('steady',this)">Steady</button>
<button class="fb" onclick="ft('dormant',this)">Dormant</button>
</div>
<table><thead><tr><th>Topic</th><th>Videos</th><th>Wtd Avg Views</th><th>vs Channel</th><th>Trend</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<script>
function ft(t,el){{document.querySelectorAll('.fb').forEach(b=>b.classList.remove('active'));el.classList.add('active');
document.querySelectorAll('tbody tr').forEach(r=>{{r.style.display=t==='all'||r.dataset.trend===t?'':'none'}})}}
</script></body></html>"""
    (bp / "analytics.html").write_text(html, encoding="utf-8")


def _build_discuss(bp, data):
    ch = data["manifest"].get("channel", "Unknown")
    slug = data["slug"]
    voice = data.get("voice_profile", {})
    chunks = data.get("chunks", [])
    sources = data.get("sources", [])

    src_map = json.dumps({s["source_id"]:{"title":s.get("title",""),"url":s.get("url","")} for s in sources})
    chunks_js = json.dumps([{"id":c["chunk_id"],"vid":c["video_id"],"text":c["text"],"ts":c.get("timestamp",0),"emb":c.get("embedding",[])} for c in chunks])
    voice_js = json.dumps(voice)

    html = f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Discuss {ch} -- TrueInfluenceAI</title>{FONTS}
<style>{THEME_CSS}{NAV_CSS}
body{{display:flex;flex-direction:column}}
.chat-wrap{{flex:1;max-width:800px;width:100%;margin:0 auto;display:flex;flex-direction:column;padding:24px}}
.msgs{{flex:1;overflow-y:auto;padding-bottom:16px}}
.msg{{margin-bottom:16px;padding:16px;border-radius:12px;max-width:85%;line-height:1.6;font-size:14px}}
.msg.user{{background:rgba(124,106,255,.12);border:1px solid rgba(124,106,255,.25);margin-left:auto;color:var(--bright)}}
.msg.ai{{background:var(--surface);border:1px solid var(--border)}}
.msg .refs{{margin-top:12px;padding-top:8px;border-top:1px solid var(--border);font-size:11px;color:var(--muted)}}
.msg .refs a{{color:var(--accent)}}
.ibar{{display:flex;gap:12px;padding:16px 0;border-top:1px solid var(--border)}}
.ibar input{{flex:1;padding:14px 18px;background:var(--surface);border:1px solid var(--border);border-radius:10px;color:var(--bright);font-size:14px;outline:none;font-family:inherit}}
.ibar input:focus{{border-color:var(--accent)}}
.ibar button{{padding:14px 28px;background:var(--accent);color:#fff;border:none;border-radius:10px;font-weight:600;cursor:pointer}}
.ibar button:hover{{background:var(--accent-glow)}}
.starters{{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:16px}}
.st{{padding:8px 16px;background:var(--surface);border:1px solid var(--border);border-radius:20px;font-size:12px;color:var(--muted);cursor:pointer;transition:all .2s}}
.st:hover{{border-color:var(--accent);color:var(--accent)}}
</style></head><body>
{_nav_html(ch, slug, 'discuss')}
<div class="chat-wrap">
<div style="text-align:center;padding:24px 0;color:var(--muted);font-size:14px">Ask anything about <strong style="color:var(--bright)">{ch}</strong>'s content</div>
<div class="starters">
<span class="st" onclick="askQ('What topics does {ch} focus on most?')">Top topics</span>
<span class="st" onclick="askQ('What is {ch}\\'s approach to growing an audience?')">Growth strategy</span>
<span class="st" onclick="askQ('What advice does {ch} give to beginners?')">Beginner advice</span>
<span class="st" onclick="askQ('How has {ch}\\'s content evolved recently?')">Content evolution</span>
</div>
<div class="msgs" id="msgs"></div>
<div class="ibar"><input id="qi" placeholder="Ask about {ch}'s content..." onkeydown="if(event.key==='Enter')askQ()"><button onclick="askQ()">Ask</button></div>
</div>

<script>
const CHUNKS={chunks_js};
const SOURCES={src_map};
const VOICE={voice_js};
const API_KEY='{OPENROUTER_API_KEY}';
const MODEL='{os.getenv("OPENROUTER_MODEL_ID","anthropic/claude-sonnet-4-20250514")}';

function dot(a,b){{let s=0;for(let i=0;i<a.length;i++)s+=a[i]*b[i];return s}}
function mag(a){{return Math.sqrt(a.reduce((s,v)=>s+v*v,0))}}
function cosine(a,b){{if(!a.length||!b.length)return 0;return dot(a,b)/(mag(a)*mag(b))}}

function recencyWeight(vid){{
  const s=SOURCES[vid];if(!s)return 0.5;return 1.0;
}}

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
    const rw=recencyWeight(c.vid);
    return{{...c,score:sim*rw}};
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

    const sysPrompt=`You are an AI assistant that answers questions based on ${{'{ch}'}}'s content.
Voice profile: ${{JSON.stringify(VOICE)}}
Answer in their voice and style. Cite specific content when possible. Be helpful and concise.`;

    const r=await fetch('https://openrouter.ai/api/v1/chat/completions',{{
      method:'POST',headers:{{'Authorization':'Bearer '+API_KEY,'Content-Type':'application/json'}},
      body:JSON.stringify({{model:MODEL,messages:[
        {{role:'system',content:sysPrompt}},
        {{role:'user',content:`Context from ${{'{ch}'}}'s content:\\n${{context}}\\n\\nQuestion: ${{q}}`}}
      ],temperature:0.4,max_tokens:1000}})
    }});
    const d=await r.json();
    const answer=d.choices[0].message.content;

    let refs='<div class="refs">Sources: ';
    const seen=new Set();
    hits.forEach(h=>{{
      if(!seen.has(h.vid)){{
        seen.add(h.vid);
        const s=SOURCES[h.vid];
        if(s)refs+=`<a href="${{s.url}}" target="_blank">${{s.title}}</a> | `;
      }}
    }});
    refs+='</div>';

    document.getElementById('thinking').outerHTML=`<div class="msg ai">${{answer.replace(/\\n/g,'<br>')}}
${{refs}}</div>`;
  }}catch(e){{
    document.getElementById('thinking').outerHTML=`<div class="msg ai" style="color:var(--red)">Error: ${{e.message}}</div>`;
  }}
  md.scrollTop=md.scrollHeight;
}}
</script></body></html>"""
    (bp / "discuss.html").write_text(html, encoding="utf-8")
