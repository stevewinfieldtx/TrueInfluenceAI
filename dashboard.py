"""
TrueInfluenceAI - Interactive Treemap Dashboard v4
====================================================
- Full-page drill-down: click topic → entire page becomes that topic
- Timeline with approximate dates
- AI-powered content strategy per topic
- Clickable content ideas → Content Summary or Social Media Plan
  written in the influencer's voice

Usage:
  py dashboard.py                          (latest bundle with analytics)
  py dashboard.py SunnyLenarduzzi_20260211_164612
"""

import sys, os, json, re
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timedelta

from dotenv import load_dotenv
load_dotenv(Path(r"C:\Users\steve\Documents\.env"))
load_dotenv(Path(r"C:\Users\steve\Documents\TruePlatformAI\.env"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
BUNDLE_DIR = Path(r"C:\Users\steve\Documents\TrueInfluenceAI\bundles")


def find_latest_bundle():
    bundles = sorted(BUNDLE_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for b in bundles:
        if (b / 'analytics_report.json').exists():
            return b
    return None


def parse_relative_date(text):
    if not text:
        return None
    text = text.lower().strip()
    now = datetime.now()
    m = re.search(r'(\d+)\s*(second|minute|hour|day|week|month|year)s?\s*ago', text)
    if not m:
        m = re.search(r'streamed\s*(\d+)\s*(second|minute|hour|day|week|month|year)s?\s*ago', text)
    if not m:
        return None
    num = int(m.group(1))
    unit = m.group(2)
    deltas = {'second': timedelta(seconds=num), 'minute': timedelta(minutes=num),
              'hour': timedelta(hours=num), 'day': timedelta(days=num),
              'week': timedelta(weeks=num), 'month': timedelta(days=num*30),
              'year': timedelta(days=num*365)}
    dt = now - deltas.get(unit, timedelta(0))
    return dt.strftime('%Y-%m-%d')


def load_data(bundle_path):
    bundle_path = Path(bundle_path)
    with open(bundle_path / 'manifest.json') as f:
        manifest = json.load(f)
    with open(bundle_path / 'sources.json') as f:
        sources = json.load(f)
    with open(bundle_path / 'chunks.json') as f:
        chunks = json.load(f)
    report = {}
    rp = bundle_path / 'analytics_report.json'
    if rp.exists():
        with open(rp) as f:
            report = json.load(f)
    # Load voice profile if exists
    voice = {}
    vp = bundle_path / 'voice_profile.json'
    if vp.exists():
        with open(vp) as f:
            voice = json.load(f)
    return manifest, sources, chunks, report, voice


def build_topic_data(report, sources, chunks):
    source_map = {s['source_id']: s for s in sources}
    chunk_by_source = defaultdict(list)
    for c in chunks:
        chunk_by_source[c['source_id']].append(c.get('text', ''))

    video_topics = report.get('video_topics', {})
    topic_freq = report.get('topic_frequency', {})
    topic_perf = report.get('topic_performance', {})
    topic_timeline = report.get('topic_timeline', {})

    topics = []
    for topic, count in sorted(topic_freq.items(), key=lambda x: x[1], reverse=True):
        videos = []
        sample_quotes = []
        for vid, tags in video_topics.items():
            clean_tags = [t.strip().title() for t in tags]
            if topic in clean_tags:
                src = source_map.get(vid, {})
                pub_text = src.get('published_text', '')
                approx_date = parse_relative_date(pub_text)
                videos.append({
                    'title': src.get('title', 'Unknown'),
                    'views': src.get('views', 0),
                    'url': src.get('url', ''),
                    'published': pub_text,
                    'approx_date': approx_date or '',
                    'position': src.get('position', 0),
                })
                vid_chunks = chunk_by_source.get(vid, [])
                if vid_chunks:
                    sample_quotes.append(f"[{src.get('title', '')}]: {vid_chunks[0][:250]}")

        videos.sort(key=lambda x: x.get('approx_date', '') or '0000', reverse=True)
        topics.append({
            'name': topic, 'count': count,
            'avg_views': topic_perf.get(topic, 0),
            'timeline': topic_timeline.get(topic, {}),
            'videos': videos,
            'sample_quotes': sample_quotes[:5],
        })
    return topics


def generate_html(channel, topics, manifest, sources, voice):
    total_vl = [t['avg_views'] for t in topics if t['avg_views'] > 0]
    channel_avg = int(sum(total_vl) / len(total_vl)) if total_vl else 0

    all_dates = [d for d in (parse_relative_date(s.get('published_text', '')) for s in sources) if d]
    dr_min = min(all_dates) if all_dates else ''
    dr_max = max(all_dates) if all_dates else ''

    quotes_lookup = {}
    topics_for_js = []
    for t in topics:
        quotes_lookup[t['name']] = t.get('sample_quotes', [])
        t2 = {k: v for k, v in t.items() if k != 'sample_quotes'}
        topics_for_js.append(t2)

    # Voice profile for prompts
    voice_prompt = voice.get('system_prompt', '')
    voice_summary = ''
    if voice:
        parts = []
        for k in ['tone_and_energy', 'vocabulary_level', 'signature_phrases', 'speaking_patterns', 'audience_relationship', 'unique_quirks']:
            if k in voice:
                parts.append(f"{k}: {voice[k]}")
        voice_summary = '\\n'.join(parts)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{channel} — Content Intelligence</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0f1117;color:#e0e0e0;overflow:hidden;height:100vh}}
.header{{padding:12px 24px;background:#161822;border-bottom:1px solid #2a2d3a;display:flex;justify-content:space-between;align-items:center;height:50px;z-index:100;position:relative}}
.header h1{{font-size:18px;font-weight:600;color:#fff}}
.header h1 span{{color:#6c63ff}}
.hstats{{display:flex;gap:18px;font-size:11px;color:#666}}
.hstats b{{color:#fff}}
#treemapView{{position:absolute;top:50px;left:0;right:0;bottom:0;transition:opacity .3s,transform .3s}}
#treemapView.hidden{{opacity:0;pointer-events:none;transform:scale(.97)}}
.treemap-item{{position:absolute;display:flex;align-items:center;justify-content:center;flex-direction:column;cursor:pointer;padding:6px;text-align:center;overflow:hidden;border:1px solid rgba(0,0,0,.25);transition:filter .12s}}
.treemap-item:hover{{filter:brightness(1.25);z-index:10}}
.t-name{{font-weight:700;color:#fff;text-shadow:0 1px 4px rgba(0,0,0,.7);line-height:1.15;word-break:break-word}}
.t-sub{{font-size:10px;color:rgba(255,255,255,.5);margin-top:2px}}
#topicView{{position:absolute;top:50px;left:0;right:0;bottom:0;overflow-y:auto;background:#0f1117;transition:opacity .3s,transform .3s}}
#topicView.hidden{{opacity:0;pointer-events:none;transform:scale(1.03)}}
.back-btn{{display:inline-flex;align-items:center;gap:6px;padding:8px 16px;background:#1e2030;border:1px solid #2a2d3a;color:#aaa;border-radius:8px;cursor:pointer;font-size:13px;transition:background .15s}}
.back-btn:hover{{background:#2a2d3a;color:#fff}}
.topic-hero{{padding:32px 40px 24px;background:linear-gradient(135deg,#161822,#1a1d30);border-bottom:1px solid #2a2d3a}}
.topic-hero h2{{font-size:28px;color:#fff;margin:16px 0 8px}}
.topic-hero .trend-label{{font-size:13px}}
.metrics-row{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;padding:20px 40px}}
.metric-card{{background:#161822;border:1px solid #2a2d3a;border-radius:12px;padding:16px 20px;text-align:center}}
.metric-card .mv{{font-size:28px;font-weight:700;color:#fff}}
.metric-card .ml{{font-size:10px;color:#555;text-transform:uppercase;margin-top:4px}}
.metric-card.hot .mv{{color:#ff6b6b}}
.metric-card.cool .mv{{color:#6bcb77}}
.timeline-section{{padding:20px 40px}}
.timeline-section h3{{font-size:13px;color:#888;margin-bottom:12px}}
.timeline-chart{{display:flex;align-items:flex-end;gap:4px;height:120px;padding:0 4px}}
.tbar{{display:flex;flex-direction:column;align-items:center;flex:1}}
.tbar-fill{{width:100%;background:#6c63ff;border-radius:4px 4px 0 0;min-height:2px;transition:height .3s;position:relative}}
.tbar-fill:hover{{filter:brightness(1.3)}}
.tbar-fill .tbar-tip{{display:none;position:absolute;bottom:100%;left:50%;transform:translateX(-50%);background:#000;color:#fff;padding:4px 8px;border-radius:4px;font-size:10px;white-space:nowrap;margin-bottom:4px}}
.tbar-fill:hover .tbar-tip{{display:block}}
.tbar-label{{font-size:9px;color:#444;margin-top:4px;writing-mode:vertical-rl;text-orientation:mixed;max-height:50px;overflow:hidden}}
.content-grid{{display:grid;grid-template-columns:1fr 1fr;gap:24px;padding:0 40px 24px}}
.section-card{{background:#161822;border:1px solid #2a2d3a;border-radius:12px;padding:24px;overflow:hidden}}
.section-card h3{{font-size:12px;color:#6c63ff;text-transform:uppercase;letter-spacing:1px;margin-bottom:14px;display:flex;align-items:center;gap:6px}}
.section-card .sc-body{{font-size:13px;line-height:1.65;color:#ccc}}
.section-card .sc-body strong{{color:#fff}}

/* ─── CLICKABLE IDEA CARDS ─── */
.idea-card{{background:#1a1d2e;border-radius:8px;margin:10px 0;border-left:3px solid #6c63ff;overflow:hidden;transition:border-color .2s}}
.idea-card:hover{{border-left-color:#a29bfe}}
.idea-top{{padding:14px 16px;cursor:pointer;transition:background .15s}}
.idea-top:hover{{background:#22263a}}
.ic-title{{font-weight:600;color:#fff;font-size:14px;margin-bottom:4px;display:flex;align-items:center;justify-content:space-between}}
.ic-title .ic-arrow{{font-size:10px;color:#555;transition:transform .2s}}
.idea-card.open .ic-title .ic-arrow{{transform:rotate(90deg);color:#6c63ff}}
.ic-why{{font-size:12px;color:#777;line-height:1.4}}
.ic-points{{margin-top:8px;display:none}}
.idea-card.open .ic-points{{display:block}}
.ic-point{{font-size:12px;color:#999;line-height:1.5;padding:2px 0 2px 8px}}
.idea-actions{{display:none;padding:0 16px 14px;gap:10px}}
.idea-card.open .idea-actions{{display:flex}}
.idea-btn{{flex:1;padding:14px;border-radius:10px;border:1px solid #2a2d3a;background:#161822;color:#bbb;font-size:12px;cursor:pointer;transition:all .15s;text-align:center;font-weight:500}}
.idea-btn:hover{{background:#2a2d3a;color:#fff;border-color:#6c63ff}}
.idea-btn.active{{border-color:#6c63ff;background:#1a1d40;color:#fff}}
.idea-btn.loading{{opacity:.6;pointer-events:none}}
.btn-icon{{font-size:20px;display:block;margin-bottom:6px}}
.btn-label{{font-size:11px;color:#666;margin-top:2px}}
.idea-result{{display:none;padding:0 16px 16px}}
.idea-card.has-result .idea-result{{display:block}}
.result-content{{background:#12141f;border:1px solid #2a2d3a;border-radius:8px;padding:16px 18px;font-size:13px;line-height:1.7;color:#ccc;max-height:600px;overflow-y:auto}}
.result-content h4{{color:#6c63ff;font-size:11px;text-transform:uppercase;letter-spacing:.5px;margin:14px 0 6px;font-weight:700}}
.result-content h4:first-child{{margin-top:0}}
.result-content strong{{color:#fff}}
.result-content em{{color:#a9a3ff;font-style:normal}}
.post-block{{background:#1a1d2e;border-radius:6px;padding:12px 14px;margin:8px 0;border-left:2px solid #4a4580;font-size:12px;white-space:pre-wrap;line-height:1.6}}
.post-platform{{font-size:10px;color:#6c63ff;text-transform:uppercase;font-weight:700;letter-spacing:1px;margin-bottom:6px}}
.result-tabs{{display:flex;gap:6px;margin-bottom:12px}}
.result-tab{{padding:6px 14px;border-radius:6px;font-size:11px;cursor:pointer;background:#1a1d2e;color:#666;border:1px solid #2a2d3a;transition:all .15s}}
.result-tab.active{{background:#6c63ff;color:#fff;border-color:#6c63ff}}

/* Platform accordion boxes */
.platform-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:8px}}
.plat-box{{background:#1a1d2e;border-radius:10px;border:1px solid #2a2d3a;overflow:hidden;cursor:pointer;transition:all .2s}}
.plat-box:hover{{border-color:var(--plat-color,#6c63ff)}}
.plat-box.open{{grid-column:span 3;cursor:default}}
.plat-box.open .plat-header{{border-bottom:1px solid #2a2d3a}}
.plat-header{{padding:14px 16px;display:flex;align-items:center;gap:10px;transition:background .15s}}
.plat-header:hover{{background:#22263a}}
.plat-icon{{font-size:22px}}
.plat-name{{font-size:13px;font-weight:600;color:#ddd;flex:1}}
.plat-arrow{{font-size:10px;color:#555;transition:transform .2s}}
.plat-box.open .plat-arrow{{transform:rotate(90deg);color:var(--plat-color,#6c63ff)}}
.plat-body{{display:none;padding:12px 16px}}
.plat-box.open .plat-body{{display:block}}

.video-item{{padding:10px 14px;background:#1a1d2e;border-radius:8px;margin-bottom:8px;cursor:pointer;transition:background .15s;display:flex;justify-content:space-between;align-items:center}}
.video-item:hover{{background:#22263a}}
.vi-left{{flex:1}}
.vi-title{{font-size:13px;color:#ddd;line-height:1.3}}
.vi-meta{{font-size:11px;color:#555;margin-top:3px}}
.vi-views{{color:#6c63ff}}
.vi-date{{font-size:11px;color:#444;white-space:nowrap;margin-left:16px}}
.badge{{display:inline-block;padding:3px 12px;border-radius:12px;font-size:12px;font-weight:600}}
.badge.rising{{background:#1a3a2a;color:#6bcb77}}
.badge.declining{{background:#3a1a1a;color:#ff6b6b}}
.badge.dormant{{background:#3a3a1a;color:#ffd93d}}
.badge.steady{{background:#1a2a3a;color:#6ba3cb}}
.spinner{{display:inline-block;width:18px;height:18px;border:2px solid #333;border-top-color:#6c63ff;border-radius:50%;animation:spin .8s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
.ai-loading{{text-align:center;padding:20px;color:#555}}
</style>
</head>
<body>

<div class="header">
  <h1><span>TrueInfluence</span>AI — {channel}</h1>
  <div class="hstats">
    <span>Videos: <b>{manifest.get('total_videos', 0)}</b></span>
    <span>Topics: <b>{len(topics)}</b></span>
    <span>Avg Views: <b>{channel_avg:,}</b></span>
    {f'<span>Range: <b>{dr_min} → {dr_max}</b></span>' if dr_min else ''}
  </div>
</div>

<div id="treemapView"></div>
<div id="topicView" class="hidden"></div>

<script>
const TOPICS = {json.dumps(topics_for_js)};
const QUOTES = {json.dumps(quotes_lookup)};
const ALL_TOPICS = {json.dumps([t['name'] for t in topics])};
const CHANNEL = "{channel}";
const CHANNEL_AVG = {channel_avg};
const API_KEY = "{OPENROUTER_API_KEY}";
const VOICE_SUMMARY = {json.dumps(voice_summary)};

const TREND_EMOJI = {{ rising:'🚀', declining:'📉', dormant:'💤', steady:'⚖️' }};
let currentTopic = null;

function getTrend(tl) {{
  const r=tl.recent||0,m=tl.middle||0,o=tl.older||0;
  if(r>o&&r>m)return'rising';if(o>r&&o>m)return'declining';
  if(o>0&&r===0)return'dormant';return'steady';
}}
function getColor(av,idx) {{
  if(CHANNEL_AVG===0)return`hsl(245,${{55+(idx%5)*6}}%,${{Math.max(18,52-idx*1.1)}}%)`;
  const r=av/CHANNEL_AVG;
  if(r>1.5)return'#e84355';if(r>1.2)return'#c74b8a';if(r>.9)return'#6c63ff';if(r>.6)return'#4a4580';return'#2d2a50';
}}
function fmtV(v){{if(v>=1e6)return(v/1e6).toFixed(1)+'M';if(v>=1e3)return(v/1e3).toFixed(0)+'k';return v.toString()}}

// ─── SQUARIFIED TREEMAP ──────────────────────────────────────────
function squarify(data,x,y,w,h){{if(!data.length)return[];if(data.length===1)return[{{...data[0],rx:x,ry:y,rw:w,rh:h}}];const t=data.reduce((s,d)=>s+d.area,0);if(t<=0)return[];return lay(data,x,y,w,h)}}
function lay(items,x,y,w,h){{
  if(!items.length)return[];if(items.length===1)return[{{...items[0],rx:x,ry:y,rw:w,rh:h}}];
  const vert=w>=h,side=vert?h:w;
  let row=[items[0]],rowA=items[0].area;
  for(let i=1;i<items.length;i++){{const test=[...row,items[i]],testA=rowA+items[i].area;if(wst(row,rowA,side)>=wst(test,testA,side)){{row.push(items[i]);rowA+=items[i].area}}else break}}
  const rects=[],depth=rowA/side;let pos=0;
  for(const it of row){{const sz=it.area/depth;if(vert)rects.push({{...it,rx:x,ry:y+pos,rw:depth,rh:sz}});else rects.push({{...it,rx:x+pos,ry:y,rw:sz,rh:depth}});pos+=sz}}
  const rest=items.slice(row.length);
  if(rest.length){{if(vert)rects.push(...lay(rest,x+depth,y,w-depth,h));else rects.push(...lay(rest,x,y+depth,w,h-depth))}}
  return rects;
}}
function wst(row,totalA,side){{const s2=side*side;let w=0;for(const it of row){{w=Math.max(w,Math.max((s2*it.area)/(totalA*totalA),(totalA*totalA)/(s2*it.area)))}}return w}}

function renderTreemap(){{
  const el=document.getElementById('treemapView'),W=el.clientWidth,H=el.clientHeight;el.innerHTML='';
  const tv=TOPICS.reduce((s,t)=>s+t.count,0),area=W*H;
  const items=TOPICS.map((t,i)=>({{...t,idx:i,area:(t.count/tv)*area}})).sort((a,b)=>b.area-a.area);
  const rects=squarify(items,0,0,W,H);
  rects.forEach(r=>{{
    const div=document.createElement('div');div.className='treemap-item';
    div.style.cssText=`left:${{r.rx}}px;top:${{r.ry}}px;width:${{r.rw}}px;height:${{r.rh}}px;background:${{getColor(r.avg_views,r.idx)}}`;
    let h='';
    if(r.rw>50&&r.rh>26)h+=`<div class="t-name" style="font-size:${{Math.min(18,Math.max(9,Math.sqrt(r.rw*r.rh)/6.5))}}px">${{r.name}}</div>`;
    if(r.rw>65&&r.rh>42)h+=`<div class="t-sub">${{r.count}} vids ${{TREND_EMOJI[getTrend(r.timeline||{{}})]||''}}</div>`;
    if(r.rw>90&&r.rh>58&&r.videos.length&&r.videos[0].approx_date)h+=`<div class="t-sub">Latest: ${{r.videos[0].approx_date}}</div>`;
    div.innerHTML=h;div.title=r.name;div.onclick=()=>openTopic(r);el.appendChild(div);
  }});
}}

// ─── TOPIC DEEP DIVE ─────────────────────────────────────────────
function openTopic(topic){{
  currentTopic=topic;
  document.getElementById('treemapView').classList.add('hidden');
  const tv=document.getElementById('topicView');tv.classList.remove('hidden');tv.scrollTop=0;
  const trend=getTrend(topic.timeline||{{}});
  const tl=topic.timeline||{{}},r=tl.recent||0,m=tl.middle||0,o=tl.older||0;
  const vr=CHANNEL_AVG>0?topic.avg_views/CHANNEL_AVG:0;
  const pc=vr>1.2?'hot':(vr<.8&&vr>0?'cool':'');

  const mb={{}};topic.videos.forEach(v=>{{if(v.approx_date){{const ym=v.approx_date.substring(0,7);mb[ym]=(mb[ym]||0)+1}}}});
  const mos=Object.keys(mb).sort();let allM=[];
  if(mos.length>=2){{let c=new Date(mos[0]+'-01');const e=new Date(mos[mos.length-1]+'-01');while(c<=e){{const k=c.toISOString().substring(0,7);allM.push({{month:k,count:mb[k]||0}});c.setMonth(c.getMonth()+1)}}}}
  else allM=mos.map(x=>({{month:x,count:mb[x]}}));
  const mx=Math.max(...allM.map(x=>x.count),1);
  const ds=topic.videos.filter(v=>v.approx_date).map(v=>v.approx_date).sort();
  const earliest=ds[0]||'?',latest=ds[ds.length-1]||'?';

  tv.innerHTML=`
    <div class="topic-hero">
      <div class="back-btn" onclick="closeTopic()">← Back to all topics</div>
      <h2>${{topic.name}}</h2>
      <div class="trend-label">
        <span class="badge ${{trend}}">${{TREND_EMOJI[trend]}} ${{trend}}</span>
        &nbsp; ${{ds.length?`First: <b>${{earliest}}</b> · Latest: <b>${{latest}}</b>`:''}}
      </div>
    </div>
    <div class="metrics-row">
      <div class="metric-card"><div class="mv">${{topic.count}}</div><div class="ml">Videos</div></div>
      <div class="metric-card ${{pc}}"><div class="mv">${{topic.avg_views>0?fmtV(topic.avg_views):'N/A'}}</div><div class="ml">Avg Views</div></div>
      <div class="metric-card ${{pc}}"><div class="mv">${{vr>0?vr.toFixed(1)+'x':'—'}}</div><div class="ml">vs Channel</div></div>
      <div class="metric-card"><div class="mv">${{topic.count}}/${{TOPICS.length}}</div><div class="ml">Topic Share</div></div>
    </div>
    ${{allM.length>1?`
    <div class="timeline-section">
      <h3>📅 When "${{topic.name}}" was discussed</h3>
      <div class="timeline-chart">
        ${{allM.map(x=>`<div class="tbar"><div class="tbar-fill" style="height:${{Math.max(2,(x.count/mx)*100)}}%;${{x.count===0?'opacity:.2;background:#333;':''}}"><div class="tbar-tip">${{x.month}}: ${{x.count}} video${{x.count!==1?'s':''}}</div></div><div class="tbar-label">${{x.month.substring(5)}}</div></div>`).join('')}}
      </div>
      <div style="display:flex;justify-content:space-between;font-size:10px;color:#444;margin-top:4px;padding:0 4px"><span>${{allM[0]?.month||''}}</span><span>${{allM[allM.length-1]?.month||''}}</span></div>
    </div>`:''}}
    <div class="content-grid" id="contentGrid">
      <div class="section-card" id="aiStance"><h3>🎯 Creator's Stance</h3><div class="ai-loading"><div class="spinner"></div><div style="margin-top:8px">Analyzing...</div></div></div>
      <div class="section-card" id="aiMarket"><h3>📡 Market Pulse</h3><div class="ai-loading"><div class="spinner"></div><div style="margin-top:8px">Scanning...</div></div></div>
      <div class="section-card" id="aiIdeas" style="grid-column:span 2"><h3>💡 Content Ideas — click any idea to expand</h3><div class="ai-loading"><div class="spinner"></div><div style="margin-top:8px">Generating ideas...</div></div></div>
      <div class="section-card" id="aiEdge" style="grid-column:span 2"><h3>⚔️ Competitive Edge</h3><div class="ai-loading"><div class="spinner"></div><div style="margin-top:8px">Analyzing...</div></div></div>
    </div>
    <div style="padding:0 40px 40px">
      <div class="section-card">
        <h3>📹 Videos on "${{topic.name}}" (${{topic.videos.length}})</h3>
        ${{topic.videos.map(v=>`<div class="video-item" onclick="window.open('${{v.url}}','_blank')"><div class="vi-left"><div class="vi-title">${{v.title}}</div><div class="vi-meta">${{v.views>0?`<span class="vi-views">${{fmtV(v.views)}} views</span> · `:''}}${{v.published||''}}</div></div>${{v.approx_date?`<div class="vi-date">${{v.approx_date}}</div>`:''}}</div>`).join('')}}
      </div>
    </div>`;
  generateInsights(topic);
}}

function closeTopic(){{
  document.getElementById('topicView').classList.add('hidden');
  document.getElementById('treemapView').classList.remove('hidden');
  currentTopic=null;
}}

// ─── AI INSIGHTS ─────────────────────────────────────────────────
async function generateInsights(topic){{
  const quotes=QUOTES[topic.name]||[];
  const trend=getTrend(topic.timeline||{{}});
  const titles=topic.videos.map(v=>v.title).join('\\n');
  const dates=topic.videos.filter(v=>v.approx_date).map(v=>`${{v.approx_date}}: ${{v.title}}`).join('\\n');

  const prompt=`You are a content strategist analyzing "${{CHANNEL}}"'s YouTube channel.

CRITICAL: Apply RECENCY BIAS. Recent content (last 6 months) reflects the creator's CURRENT direction. Older content is historical context only. If a topic is declining or dormant, respect that pivot. Do NOT recommend going back to abandoned topics unless performance data is overwhelming. Creators evolve - honor where they are NOW, not where they were.

TOPIC: "${{topic.name}}"
FREQUENCY: ${{topic.count}} videos out of ~${{TOPICS.reduce((s,t)=>s+t.count,0)}} total
TREND: ${{trend}}
AVG VIEWS: ${{topic.avg_views>0?topic.avg_views.toLocaleString():'N/A'}}
CHANNEL AVG VIEWS: ${{CHANNEL_AVG>0?CHANNEL_AVG.toLocaleString():'N/A'}}

TIMELINE: ${{dates||'No date data'}}
ALL TOPICS: ${{ALL_TOPICS.join(', ')}}
VIDEOS: ${{titles}}
SAMPLE CONTENT: ${{quotes.join('\\n')}}

Respond in EXACT JSON, no markdown fences:
{{
  "stance":"2-3 sentences on creator's unique angle on this topic.",
  "market":"2-3 sentences on current market demand for this topic. Rising or falling? What's driving interest?",
  "ideas":[
    {{"title":"Specific video title","why":"One-sentence data-driven rationale","talking_points":["Key point 1 they should cover","Key point 2","Key point 3","Key point 4"]}},
    {{"title":"Second title","why":"Rationale","talking_points":["Point 1","Point 2","Point 3","Point 4"]}},
    {{"title":"Third title","why":"Rationale","talking_points":["Point 1","Point 2","Point 3","Point 4"]}}
  ],
  "edge":"2 sentences on competitive advantage and what others are missing."
}}`;

  try{{
    const resp=await fetch('https://openrouter.ai/api/v1/chat/completions',{{method:'POST',headers:{{'Authorization':`Bearer ${{API_KEY}}`,'Content-Type':'application/json'}},body:JSON.stringify({{model:'google/gemini-2.5-flash-lite:online',messages:[{{role:'user',content:prompt}}],max_tokens:1200,temperature:.4}})}});
    if(!resp.ok)throw new Error('API '+resp.status);
    const data=await resp.json();
    let text=data.choices?.[0]?.message?.content||'';
    text=text.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim();
    let p;try{{p=JSON.parse(text)}}catch(e){{document.getElementById('aiStance').innerHTML=`<h3>🎯 Analysis</h3><div class="sc-body">${{text}}</div>`;return}}

    document.getElementById('aiStance').innerHTML=`<h3>🎯 Creator's Stance</h3><div class="sc-body">${{p.stance||''}}</div>`;
    document.getElementById('aiMarket').innerHTML=`<h3>📡 Market Pulse</h3><div class="sc-body">${{p.market||''}}</div>`;
    document.getElementById('aiEdge').innerHTML=`<h3>⚔️ Competitive Edge</h3><div class="sc-body">${{p.edge||''}}</div>`;

    // Render clickable idea cards
    let ih='<h3>💡 Content Ideas — click to expand</h3>';
    if(p.ideas&&p.ideas.length){{
      p.ideas.forEach((idea,i)=>{{
        const id='idea_'+i;
        let tpHtml='';
        if(idea.talking_points&&idea.talking_points.length){{
          tpHtml=`<div class="ic-points">`;
          idea.talking_points.forEach(tp=>{{tpHtml+=`<div class="ic-point">• ${{tp}}</div>`}});
          tpHtml+=`</div>`;
        }}
        ih+=`
        <div class="idea-card" id="${{id}}">
          <div class="idea-top" onclick="toggleIdea('${{id}}')">
            <div class="ic-title">${{idea.title}} <span class="ic-arrow">▶</span></div>
            <div class="ic-why">${{idea.why}}</div>
            ${{tpHtml}}
          </div>
          <div class="idea-actions">
            <div class="idea-btn" onclick="event.stopPropagation();generateIdeaContent('${{id}}','summary','${{escHtml(idea.title)}}')">
              <span class="btn-icon">📋</span>
              Strategic Brief
              <div class="btn-label">Why now, past proof, gap analysis</div>
            </div>
            <div class="idea-btn" onclick="event.stopPropagation();generateIdeaContent('${{id}}','social','${{escHtml(idea.title)}}')">
              <span class="btn-icon">📱</span>
              Platform Strategy
              <div class="btn-label">Where to distribute, priority & angles</div>
            </div>
            <div class="idea-btn" onclick="event.stopPropagation();generateIdeaContent('${{id}}','writeit','${{escHtml(idea.title)}}')">
              <span class="btn-icon">✍️</span>
              Write It For Me
              <div class="btn-label">Full script in their voice & style</div>
            </div>
          </div>
          <div class="idea-result"></div>
        </div>`;
      }});
    }}
    document.getElementById('aiIdeas').innerHTML=ih;
  }}catch(e){{
    ['aiStance','aiMarket','aiIdeas','aiEdge'].forEach(id=>{{const el=document.getElementById(id);if(el){{const ld=el.querySelector('.ai-loading');if(ld)ld.innerHTML=`<div style="color:#555">Unavailable: ${{e.message}}</div>`}}}});
  }}
}}

function escHtml(s){{return s.replace(/'/g,"\\\\'").replace(/"/g,"&quot;")}}

function toggleIdea(id){{
  const el=document.getElementById(id);
  el.classList.toggle('open');
}}

// ─── GENERATE IDEA CONTENT ───────────────────────────────────────
async function generateIdeaContent(cardId, type, title){{
  const card=document.getElementById(cardId);
  const resultDiv=card.querySelector('.idea-result');
  const btns=card.querySelectorAll('.idea-btn');

  btns.forEach(b=>b.classList.remove('active'));
  const btnIdx=type==='summary'?0:type==='social'?1:2;
  btns[btnIdx].classList.add('active');
  btns[btnIdx].classList.add('loading');

  card.classList.add('has-result');
  const loadMsg=type==='summary'?'Building strategic brief...':type==='social'?'Analyzing platform strategy...':'Writing full content in their voice...';
  resultDiv.innerHTML=`<div class="ai-loading"><div class="spinner"></div><div style="margin-top:8px">${{loadMsg}}</div></div>`;

  const topicName=currentTopic?.name||'';
  const quotes=QUOTES[topicName]||[];
  const topicVideos=currentTopic?.videos||[];
  const topicTitles=topicVideos.map(v=>v.title+(v.views>0?' ('+fmtV(v.views)+' views)':'')).join('\\n');
  const topicDates=topicVideos.filter(v=>v.approx_date).map(v=>v.approx_date);
  const lastCovered=topicDates.length?topicDates[0]:'unknown';
  const trend=getTrend(currentTopic?.timeline||{{}});
  const viewRatio=CHANNEL_AVG>0&&currentTopic?.avg_views>0?(currentTopic.avg_views/CHANNEL_AVG).toFixed(1)+'x':'N/A';

  let prompt;
  if(type==='summary'){{
    prompt=`You are a data-driven content strategy advisor (APPLY RECENCY BIAS: recent content reflects current direction, older content is historical context only) (APPLY RECENCY BIAS: recent content reflects current direction, older content is historical context only) (APPLY RECENCY BIAS: recent content reflects current direction, older content is historical context only) for YouTube creator "${{CHANNEL}}". You are NOT writing content. You are giving strategic intelligence to help them decide what to create next.

VIDEO IDEA: "${{title}}"
TOPIC: "${{topicName}}"

DATA:
- Videos on this topic: ${{currentTopic?.count||'?'}} / ~${{TOPICS.reduce((s,t)=>s+t.count,0)}} total
- Trend: ${{trend}}
- Topic avg views: ${{currentTopic?.avg_views>0?currentTopic.avg_views.toLocaleString():'N/A'}}
- Channel avg views: ${{CHANNEL_AVG>0?CHANNEL_AVG.toLocaleString():'N/A'}}
- Performance vs channel: ${{viewRatio}}
- Last covered: ${{lastCovered}}

PAST VIDEOS ON THIS TOPIC:
${{topicTitles}}

SAMPLE CONTENT:
${{quotes.join('\\n')}}

ALL CHANNEL TOPICS: ${{ALL_TOPICS.join(', ')}}

Respond in EXACT JSON, no markdown:
{{
  "why_now": "2-3 sentences: Why make this NOW? Market timing, seasonal opportunity, or audience demand signal?",
  "past_proof": "2-3 sentences: Which of their OWN past videos on this topic performed best and why? What pattern in their data supports this idea? Reference specific titles.",
  "gap": "2 sentences: What angle on this topic have they NOT covered that their audience would want? What is the hole in their content library?",
  "differentiation": "2 sentences: What do competitors say about this and how should this creator approach it differently?",
  "risk": "1-2 sentences: Any reason NOT to make this? Oversaturated? Audience fatigue? Cannibalize existing content?",
  "format": "1 sentence: Based on what worked before, what format fits? (long tutorial, case study, story-driven, etc.)"
}}`;
  }}else if(type==='writeit'){{
    const voiceCtx=VOICE_SUMMARY?`\\nCREATOR VOICE PROFILE:\\n${{VOICE_SUMMARY}}`:'';
    prompt=`You are writing AS ${{CHANNEL}}, the YouTube creator. Write in FIRST PERSON using their exact voice and style.${{voiceCtx}}

Write a complete YouTube video script for:
Title: "${{title}}"
Topic: "${{topicName}}"

Their existing content for voice reference:
${{quotes.join('\\n')}}

Write the COMPLETE ready-to-film script with:
1. INTRO HOOK (first 15 seconds to grab attention)
2. MAIN CONTENT (organized sections with key talking points)
3. OUTRO + CTA (how they close and what they ask viewers to do)

Match their tone, energy, phrases, and style exactly. Write as if they are speaking directly to camera.`;
  }}else if(type==='social'){{
    prompt=`You are a platform distribution strategist advising (RECENCY MATTERS: base strategy on creator's recent focus, not historical topics they've moved away from) (RECENCY MATTERS: base strategy on creator's recent focus, not historical topics they've moved away from) (RECENCY MATTERS: base strategy on creator's recent focus, not historical topics they've moved away from) YouTube creator "${{CHANNEL}}". You are NOT writing posts. You are advising which platforms to prioritize and what strategy to use, backed by data.

VIDEO IDEA: "${{title}}"
TOPIC: "${{topicName}}"

DATA:
- Videos: ${{currentTopic?.count||'?'}} / ~${{TOPICS.reduce((s,t)=>s+t.count,0)}} total
- Avg views: ${{currentTopic?.avg_views>0?currentTopic.avg_views.toLocaleString():'N/A'}}
- vs Channel: ${{viewRatio}}
- Trend: ${{trend}}
- Last covered: ${{lastCovered}}

PAST CONTENT:
${{quotes.join('\\n')}}

For each platform, give STRATEGIC GUIDANCE not copy. Respond in EXACT JSON, no markdown:
{{
  "youtube": {{"priority":"high/medium/low","strategy":"1-2 sentences: approach for this topic on YT","title_directions":[{{"title":"A specific suggested video title","talking_points":["Key point they should cover in this video","Second key point to address","Third key point or angle to explore","Closing point or call-to-action idea"]}},{{"title":"Second title option","talking_points":["Point 1","Point 2","Point 3","Point 4"]}},{{"title":"Third title option","talking_points":["Point 1","Point 2","Point 3","Point 4"]}}],"tip":"1 SEO or thumbnail tip"}},
  "instagram": {{"priority":"high/medium/low","strategy":"1-2 sentences: Reel vs carousel vs static and why","hook":"The emotional angle for IG","talking_points":["What to show/say in the first 3 seconds","Key message to convey","CTA approach"]}},
  "twitter": {{"priority":"high/medium/low","strategy":"1-2 sentences: Thread vs single vs quote-tweet","hook":"The debate or hot take angle","talking_points":["Opening hook concept","Value point to make","Engagement driver"]}},
  "linkedin": {{"priority":"high/medium/low","strategy":"1-2 sentences: Right for LinkedIn? What framing?","hook":"Professional angle","talking_points":["Professional framing concept","Key insight to share","CTA approach"]}},
  "tiktok": {{"priority":"high/medium/low","strategy":"1-2 sentences: Format that fits","hook":"3-second hook concept","talking_points":["Hook moment","Key reveal or point","Trending format to use"]}},
  "email": {{"priority":"high/medium/low","strategy":"1-2 sentences: Standalone or series? What converts?","hook":"Subject line direction","talking_points":["Opening line concept","Value proposition","CTA approach"]}}
}}`;
  }}

  try{{
    const resp=await fetch('https://openrouter.ai/api/v1/chat/completions',{{method:'POST',headers:{{'Authorization':`Bearer ${{API_KEY}}`,'Content-Type':'application/json'}},body:JSON.stringify({{model:'google/gemini-2.5-flash-lite:online',messages:[{{role:'user',content:prompt}}],max_tokens:2000,temperature:.5}})}});
    if(!resp.ok)throw new Error('API '+resp.status);
    const data=await resp.json();
    let text=data.choices?.[0]?.message?.content||'';

    btns.forEach(b=>b.classList.remove('loading'));

    if(type==='writeit'){{
      text=text.replace(/\\*\\*(.+?)\\*\\*/g,'<strong>$1</strong>').replace(/\\n/g,'<br>');
      resultDiv.innerHTML=`<div class="result-content" style="max-height:800px">${{text}}</div>`;
    }}else if(type==='summary'){{
      text=text.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim();
      let sb;
      try{{sb=JSON.parse(text)}}catch(e){{resultDiv.innerHTML=`<div class="result-content">${{text.replace(/\\n/g,'<br>')}}</div>`;return}}
      resultDiv.innerHTML=`<div class="result-content">
        <h4>Why Now</h4><p>${{sb.why_now||''}}</p>
        <h4>Past Proof (from your data)</h4><p>${{sb.past_proof||''}}</p>
        <h4>Gap Analysis</h4><p>${{sb.gap||''}}</p>
        <h4>Differentiation</h4><p>${{sb.differentiation||''}}</p>
        <h4>Risk Check</h4><p>${{sb.risk||''}}</p>
        <h4>Recommended Format</h4><p>${{sb.format||''}}</p>
      </div>`;
    }}else{{
      // Parse social media JSON
      text=text.replace(/```json\\n?/g,'').replace(/```\\n?/g,'').trim();
      let sm;
      try{{sm=JSON.parse(text)}}catch(e){{
        resultDiv.innerHTML=`<div class="result-content">${{text.replace(/\\n/g,'<br>')}}</div>`;
        return;
      }}

      // Build platform strategy boxes
      const pconf = [
        {{key:'youtube',icon:'🎬',name:'YouTube',color:'#ff4444'}},
        {{key:'instagram',icon:'📸',name:'Instagram',color:'#e1306c'}},
        {{key:'twitter',icon:'𝕏',name:'Twitter / X',color:'#1da1f2'}},
        {{key:'linkedin',icon:'💼',name:'LinkedIn',color:'#0077b5'}},
        {{key:'tiktok',icon:'🎵',name:'TikTok',color:'#00f2ea'}},
        {{key:'email',icon:'📧',name:'Email',color:'#6c63ff'}},
      ];
      const platforms = [];
      pconf.forEach(pc=>{{const d=sm[pc.key];if(!d)return;
        const pri=d.priority||'medium';
        const priColor=pri==='high'?'#6bcb77':pri==='low'?'#ff6b6b':'#ffd93d';
        let body=`<div style="margin-bottom:8px"><span style="display:inline-block;padding:2px 10px;border-radius:10px;font-size:10px;font-weight:700;background:${{priColor}}22;color:${{priColor}}">${{pri.toUpperCase()}} PRIORITY</span></div>`;
        body+=`<p style="margin:8px 0;font-size:13px;line-height:1.6;color:#ccc">${{d.strategy||''}}</p>`;
        if(d.title_directions&&Array.isArray(d.title_directions)){{
          body+=`<h4 style="color:#6c63ff;font-size:10px;text-transform:uppercase;margin:10px 0 4px">Title Directions</h4>`;
          d.title_directions.forEach((td,ti)=>{{
            if(typeof td==='object'&&td.title){{
              body+=`<div class="post-block"><strong>${{td.title}}</strong>`;
              if(td.talking_points&&td.talking_points.length){{
                body+=`<div style="margin-top:6px">`;
                td.talking_points.forEach(tp=>{{body+=`<div style="color:#999;font-size:11px;padding:1px 0 1px 10px">&bull; ${{tp}}</div>`}});
                body+=`</div>`;
              }}
              const writeId=`write_${{cardId}}_${{pc.key}}_${{ti}}`;
              body+=`<div style="margin-top:8px"><span id="${{writeId}}" onclick="event.stopPropagation();writeContentForMe('${{writeId}}','${{escHtml(td.title)}}','${{pc.key}}')" style="display:inline-block;padding:4px 12px;border-radius:6px;background:#6c63ff22;color:#a29bfe;font-size:10px;font-weight:600;cursor:pointer;border:1px solid #6c63ff44;transition:all .15s"onmouseover="this.style.background='#6c63ff44'"onmouseout="this.style.background='#6c63ff22'">\u270d\ufe0f Write this for me</span></div>`;
              body+=`</div>`;
            }}else{{
              body+=`<div class="post-block">${{td}}</div>`;
            }}
          }});
        }}
        if(d.tip)body+=`<div class="post-block" style="border-left-color:#ffd93d"><strong>Tip:</strong> ${{d.tip}}</div>`;
        if(d.hook)body+=`<div class="post-block"><strong>Angle:</strong> ${{d.hook}}</div>`;
        if(d.talking_points&&!d.title_directions){{
          body+=`<div style="margin-top:6px">`;
          d.talking_points.forEach(tp=>{{body+=`<div style="color:#999;font-size:11px;padding:1px 0 1px 10px">&bull; ${{tp}}</div>`}});
          const writeId2=`write_${{cardId}}_${{pc.key}}`;
          body+=`<div style="margin-top:8px"><span id="${{writeId2}}" onclick="event.stopPropagation();writeContentForMe('${{writeId2}}','${{escHtml(title)}}','${{pc.key}}')" style="display:inline-block;padding:4px 12px;border-radius:6px;background:#6c63ff22;color:#a29bfe;font-size:10px;font-weight:600;cursor:pointer;border:1px solid #6c63ff44;transition:all .15s"onmouseover="this.style.background='#6c63ff44'"onmouseout="this.style.background='#6c63ff22'">\u270d\ufe0f Write this for me</span></div>`;
          body+=`</div>`;
        }}
        platforms.push({{...pc,content:body,pri}});
      }});

      let html=`<div class="result-content"><div class="platform-grid">`;
      platforms.forEach((pl,i)=>{{
        html+=`
        <div class="plat-box" id="plat_${{cardId}}_${{i}}" onclick="togglePlat('plat_${{cardId}}_${{i}}')" style="--plat-color:${{pl.color}}">
          <div class="plat-header">
            <span class="plat-icon">${{pl.icon}}</span>
            <span class="plat-name">${{pl.name}}</span>
            <span class="plat-arrow">▶</span>
          </div>
          <div class="plat-body">${{pl.content}}</div>
        </div>`;
      }});
      html+=`</div></div>`;
      resultDiv.innerHTML=html;
    }}
  }}catch(e){{
    btns.forEach(b=>b.classList.remove('loading'));
    resultDiv.innerHTML=`<div class="result-content" style="color:#666">Failed: ${{e.message}}</div>`;
  }}
}}

// ─── WRITE CONTENT FOR ME (per title direction) ─────────────
async function writeContentForMe(btnId, contentTitle, platform){{
  const btn=document.getElementById(btnId);
  if(!btn)return;
  const parent=btn.closest('.post-block')||btn.parentElement;
  btn.innerHTML=`<div class="spinner" style="width:14px;height:14px;display:inline-block;vertical-align:middle"></div> Writing...`;
  btn.style.pointerEvents='none';

  const topicName=currentTopic?.name||'';
  const quotes=QUOTES[topicName]||[];
  const voiceCtx=VOICE_SUMMARY?`\\nCREATOR VOICE PROFILE:\\n${{VOICE_SUMMARY}}`:'';

  const platNames={{youtube:'YouTube video script',instagram:'Instagram post',twitter:'Twitter/X thread',linkedin:'LinkedIn post',tiktok:'TikTok script',email:'email to their list'}};

  const prompt=`You are writing AS ${{CHANNEL}}, the YouTube creator. Write in FIRST PERSON using their exact voice and style.${{voiceCtx}}

Write a complete ${{platNames[platform]||'post'}} for this content idea:
Title: "${{contentTitle}}"
Topic: "${{topicName}}"

Their existing content for voice reference:
${{quotes.join('\\n')}}

Write the COMPLETE ready-to-use content. Match their tone, energy, phrases, and style exactly. For YouTube scripts include intro hook, main content sections, and outro/CTA. For social posts make them ready to paste and publish.`;

  try{{
    const resp=await fetch('https://openrouter.ai/api/v1/chat/completions',{{method:'POST',headers:{{'Authorization':`Bearer ${{API_KEY}}`,'Content-Type':'application/json'}},body:JSON.stringify({{model:'google/gemini-2.5-flash-lite:online',messages:[{{role:'user',content:prompt}}],max_tokens:3000,temperature:.5}})}});
    if(!resp.ok)throw new Error('API '+resp.status);
    const data=await resp.json();
    let text=data.choices?.[0]?.message?.content||'';
    text=text.replace(/\\*\\*(.+?)\\*\\*/g,'<strong>$1</strong>').replace(/\\n/g,'<br>');
    const resultDiv=document.createElement('div');
    resultDiv.style.cssText='margin-top:10px;background:#12141f;border:1px solid #2a2d3a;border-radius:8px;padding:14px;font-size:12px;line-height:1.7;color:#ccc;max-height:400px;overflow-y:auto';
    resultDiv.innerHTML=text;
    btn.style.display='none';
    parent.appendChild(resultDiv);
  }}catch(e){{
    btn.innerHTML='\u270d\ufe0f Write this for me';
    btn.style.pointerEvents='auto';
  }}
}}

// ─── PLATFORM TOGGLE ─────────────────────────────────────────
function togglePlat(id){{
  const el=document.getElementById(id);
  if(el.classList.contains('open')){{el.classList.remove('open')}}
  else{{
    // Close siblings
    el.parentElement.querySelectorAll('.plat-box.open').forEach(b=>b.classList.remove('open'));
    el.classList.add('open');
  }}
}}

// ─── NAV ─────────────────────────────────────────────────────────
document.addEventListener('keydown',e=>{{if(e.key==='Escape')closeTopic()}});
renderTreemap();
window.addEventListener('resize',()=>{{if(!document.getElementById('treemapView').classList.contains('hidden'))renderTreemap()}});
</script>
</body>
</html>"""
    return html


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

    print(f"[*] Loading: {bp.name}")
    manifest, sources, chunks, report, voice = load_data(bp)
    channel = manifest.get('channel', 'Unknown')

    if not report.get('video_topics'):
        print("[!] No analytics data. Run analytics.py first.")
        sys.exit(1)

    print(f"   Building dashboard for {channel}...")
    topics = build_topic_data(report, sources, chunks)
    html = generate_html(channel, topics, manifest, sources, voice)

    out_path = bp / 'dashboard.html'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"[OK] Dashboard saved: {out_path}")
    import webbrowser
    webbrowser.open(str(out_path))


if __name__ == '__main__':
    main()
