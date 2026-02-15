"""
TrueInfluenceAI - Actionable Analytics Core
=============================================
Importable module that generates the actionable analytics HTML.
Called by pages.py: from build_actionable_core import build_analytics_html

Accepts pre-loaded data dict from _load_bundle().
"""

import os, json
from pathlib import Path
from datetime import datetime

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
VOICE_MODEL = os.getenv("VOICE_MODEL", "anthropic/claude-sonnet-4")  # Voice ANALYSIS only
WRITING_MODEL = os.getenv("OPENROUTER_MODEL_ID", "google/gemini-2.5-flash-lite:online")  # Content generation (cheap, high volume)


def esc(s):
    if not isinstance(s, str): s = str(s)
    return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')

def fmt_views(v):
    v = int(v or 0)
    if v >= 1_000_000: return f"{v/1_000_000:.1f}M"
    if v >= 1_000: return f"{v/1_000:.0f}k"
    return f"{v:,}"

def _safe_get(d, *keys, default=None):
    """Safely traverse nested dicts."""
    for k in keys:
        if isinstance(d, dict):
            d = d.get(k, default)
        else:
            return default
    return d


def build_analytics_html(bp, data):
    bp = Path(bp)
    insights = data.get('insights', {}) or {}
    report = data.get('analytics_report', {}) or {}
    metrics = data.get('channel_metrics', {}) or {}
    manifest = data.get('manifest', {}) or {}
    sources_list = data.get('sources', []) or []
    voice_profile = data.get('voice_profile', {}) or {}
    slug = data.get('slug', '')

    channel = manifest.get('channel', 'Unknown')
    channel_avg = metrics.get('channel_avg_views', 0) or 0
    total_videos = manifest.get('total_videos', 0)
    total_views = metrics.get('total_views', 0) or 0
    engagement_rate = metrics.get('channel_engagement_rate', 0) or 0

    ai_deep = insights.get('ai_deep_analysis', {}) or {}
    contrarian = insights.get('contrarian_content', {}) or {}
    title_patterns = insights.get('title_patterns', {}) or {}
    engagement = insights.get('engagement_anomalies', {}) or {}
    velocity = insights.get('content_velocity', {}) or {}
    revivals = insights.get('revival_candidates', []) or []
    cannibalization = insights.get('topic_cannibalization', []) or []
    topic_timeline = report.get('topic_timeline', {}) or {}
    topic_perf = report.get('topic_performance', {}) or {}
    topic_pairs = report.get('topic_pairs', {}) or {}

    # ─── Derived data ────────────────────────────────────────────
    def _get_perf_val(v):
        if isinstance(v, dict): return v.get('weighted_avg_views', v.get('avg_views', 0))
        return v or 0

    rising_topics = []
    for topic, tl in topic_timeline.items():
        if not isinstance(tl, dict): continue
        r, m, o = tl.get('recent',0), tl.get('middle',0), tl.get('older',0)
        if r > o and r > m and (r+m+o) >= 2:
            avg_v = _get_perf_val(topic_perf.get(topic, 0))
            rising_topics.append({'name':topic,'recent':r,'middle':m,'older':o,'avg_views':int(avg_v),
                'vs_channel':round(avg_v/channel_avg,2) if channel_avg>0 else 0})
    rising_topics.sort(key=lambda x:x['avg_views'], reverse=True)

    untapped_combos = []
    perf_items = [(t, _get_perf_val(v)) for t,v in topic_perf.items()]
    top_topics = sorted(perf_items, key=lambda x:x[1], reverse=True)[:15]
    for i,(t1,v1) in enumerate(top_topics):
        for t2,v2 in top_topics[i+1:]:
            co = topic_pairs.get(f"{t1} + {t2}",0) or topic_pairs.get(f"{t2} + {t1}",0)
            if co <= 1 and v1 > channel_avg*0.8 and v2 > channel_avg*0.8:
                untapped_combos.append({'topic_a':t1,'topic_b':t2,'views_a':int(v1),'views_b':int(v2),'co_count':co})
    untapped_combos.sort(key=lambda x:x['views_a']+x['views_b'], reverse=True)

    evergreen_decay = []
    now = datetime.utcnow()
    for s in sources_list:
        pub = s.get('published_at',''); views = s.get('views',0)
        if pub and views > channel_avg:
            try:
                dt = datetime.fromisoformat(pub.replace('Z','+00:00')).replace(tzinfo=None)
                age = (now-dt).days
                if age > 180:
                    evergreen_decay.append({'title':s.get('title',''),'views':views,'age_days':age,
                        'age_label':f"{age//30} months ago",'published_at':pub[:10]})
            except: pass
    evergreen_decay.sort(key=lambda x:x['views'], reverse=True)

    high_passion = engagement.get('high_passion',[]) or []

    # ─── Big Bet ─────────────────────────────────────────────────
    big_bet = ai_deep.get('one_big_bet', '') if isinstance(ai_deep, dict) else ''
    big_bet_html = ''
    if big_bet:
        big_bet_html = f'''<div class="big-bet">
        <div class="bb-eyebrow">🏆 THE ONE BIG BET</div>
        <div class="bb-text">{esc(big_bet)}</div>
        </div>'''

    # ─── Card builders ───────────────────────────────────────────
    def _card(topic, badge_cls, badge_text, stats, action, write_type, write_topic, write_views=0):
        stat_html = ''
        for val, label, cls in stats:
            stat_html += f'<div class="ac-stat"><div class="ac-stat-val {cls}">{val}</div><div class="ac-stat-label">{label}</div></div>'
        return f'''<div class="action-card">
            <div class="ac-header"><span class="ac-topic">{esc(topic)}</span><span class="ac-badge {badge_cls}">{badge_text}</span></div>
            <div class="ac-stat-row">{stat_html}</div>
            <div class="ac-action">{action}</div>
            <button class="write-btn" onclick="writeIt(this)" data-type="{write_type}" data-topic="{esc(write_topic)}" data-views="{write_views}">✍️ Write It For Me</button>
        </div>'''

    # Rising
    working_cards = ''
    for t in rising_topics[:6]:
        pc = 'hot' if t['vs_channel']>1.3 else ('warm' if t['vs_channel']>0.8 else 'cool')
        working_cards += _card(t['name'],'rising','▲ Rising',
            [(fmt_views(t['avg_views']),'Avg Views',''),(f"{t['vs_channel']}x",'vs Channel',pc),(f"{t['recent']}/{t['middle']}/{t['older']}",'R/M/O','')],
            '✅ Keep making this. Audience demand is growing.','rising',t['name'],t['avg_views'])

    # Revivals
    revival_cards = ''
    for rv in revivals[:6]:
        if not isinstance(rv, dict): continue
        revival_cards += _card(rv.get('topic',''),'dormant',f"💤 {rv.get('trend','dormant').title()}",
            [(fmt_views(rv.get('avg_views',0)),'Avg Views',''),(f"{rv.get('vs_channel',0)}x",'vs Channel','hot')],
            f"🔄 PROVED demand ({fmt_views(rv.get('avg_views',0))} avg) but you stopped. Bring it back.",'revival',rv.get('topic',''),rv.get('avg_views',0))

    # Evergreen
    evergreen_cards = ''
    for ev in evergreen_decay[:6]:
        evergreen_cards += _card(ev['title'][:60],'stale',f"📅 {ev['age_label']}",
            [(fmt_views(ev['views']),'Views',''),(ev['published_at'],'Published','')],
            '📝 High-performing but aging. Update for a near-guaranteed win.','evergreen',ev['title'][:60],ev['views'])

    # Combos
    combo_cards = ''
    for cb in untapped_combos[:6]:
        combo_cards += _card(f"{cb['topic_a']} + {cb['topic_b']}",'new','🆕 Untapped',
            [(fmt_views(cb['views_a']),esc(cb['topic_a'][:15]),''),(fmt_views(cb['views_b']),esc(cb['topic_b'][:15]),''),(str(cb['co_count']),'Times Combined','')],
            '🧪 Both perform well independently but rarely combined. Test the mashup.','combo',f"{cb['topic_a']} + {cb['topic_b']}",cb['views_a'])

    # Passion
    passion_cards = ''
    avg_cr = engagement.get('channel_avg_comment_rate',0) or 0
    for hp in high_passion[:5]:
        if not isinstance(hp, dict): continue
        cr = hp.get('comment_rate',0); mult = round(cr/avg_cr,1) if avg_cr>0 else 0
        passion_cards += _card(hp.get('title','')[:55],'passion',f"🔥 {mult}x comments",
            [(fmt_views(hp.get('views',0)),'Views',''),(f"{hp.get('engagement_rate',0)}%",'Engagement',''),(f"{cr}%",'Comment Rate','')],
            '💬 Your audience is TALKING about this. High engagement = strong demand.','passion',hp.get('title','')[:55],hp.get('views',0))

    # Contrarian
    contrarian_html = ''
    if contrarian and isinstance(contrarian, dict):
        c_avg = contrarian.get('avg_views_contrarian',0); n_avg = contrarian.get('avg_views_conventional',0)
        c_lift = contrarian.get('lift_pct',0); top_c = contrarian.get('top_contrarian',[]) or []
        items = ''.join(f'<div class="contrarian-item"><span class="ci-title">{esc(v.get("title",""))}</span><span class="ci-views">{fmt_views(v.get("views",0))}</span></div>' for v in top_c[:5] if isinstance(v,dict))
        if c_avg or n_avg:
            contrarian_html = f'''<div class="section"><div class="section-icon">⚡</div><h2>Your Contrarian Edge</h2>
            <p class="section-desc">Titles that challenge assumptions outperform conventional content.</p>
            <div class="mega-stat-row"><div class="mega-stat"><div class="ms-val hot">{fmt_views(c_avg)}</div><div class="ms-label">Contrarian Avg</div></div>
            <div class="mega-stat"><div class="ms-val dim">{fmt_views(n_avg)}</div><div class="ms-label">Conventional Avg</div></div>
            <div class="mega-stat"><div class="ms-val green">+{c_lift:.0f}%</div><div class="ms-label">Lift</div></div></div>
            <div class="sub-label">Top Contrarian Videos</div>{items}
            <div class="ac-action" style="margin-top:16px">🎯 Lean into challenging conventional wisdom. Your audience rewards it.</div></div>'''

    # Title Intelligence
    title_html = ''
    title_rec = ai_deep.get('title_formula_rec',{}) if isinstance(ai_deep,dict) else {}
    if title_rec:
        formula = title_rec.get('formula','') if isinstance(title_rec,dict) else str(title_rec)
        examples = title_rec.get('examples',[]) if isinstance(title_rec,dict) else []
        ex_html = ''.join(f'<div class="formula-example">"{esc(e)}"</div>' for e in (examples[:3] if isinstance(examples,list) else []))
        pat_html = ''
        if isinstance(title_patterns, dict):
            for pn,pd in sorted(title_patterns.items(), key=lambda x:x[1].get('lift_pct',0) if isinstance(x[1],dict) else 0, reverse=True)[:5]:
                if not isinstance(pd,dict): continue
                lc = '#34d399' if pd.get('lift_pct',0)>50 else ('#fbbf24' if pd.get('lift_pct',0)>0 else '#f87171')
                pat_html += f'<div class="pattern-row"><span class="pr-name">{esc(pn.replace("_"," ").title())}</span><span class="pr-count">{pd.get("count",0)} vids</span><span class="pr-views">{fmt_views(pd.get("avg_views",0))} avg</span><span class="pr-lift" style="color:{lc}">{pd.get("lift_pct",0):+.0f}%</span></div>'
        if formula or pat_html:
            title_html = f'''<div class="section"><div class="section-icon">✍️</div><h2>Title Intelligence</h2>
            <p class="section-desc">Which title formulas drive the most views for YOUR audience?</p>
            {f'<div class="formula-box"><div class="formula-label">Winning Formula</div><div class="formula-text">{esc(formula)}</div>{ex_html}</div>' if formula else ''}
            {f'<div class="sub-label">Patterns Ranked by View Lift</div>{pat_html}' if pat_html else ''}</div>'''

    # Blind spots
    blind_spots = ai_deep.get('blind_spots',[]) if isinstance(ai_deep,dict) else []
    money = ai_deep.get('money_left_on_table',[]) if isinstance(ai_deep,dict) else []
    insights_cards = ''
    for bs in (blind_spots if isinstance(blind_spots,list) else []):
        insights_cards += f'<div class="insight-card blind"><div class="ic-icon">👁️</div><div class="ic-label">Blind Spot</div><div class="ic-text">{esc(bs)}</div></div>'
    for m in (money if isinstance(money,list) else []):
        insights_cards += f'<div class="insight-card money"><div class="ic-icon">💰</div><div class="ic-label">Money on the Table</div><div class="ic-text">{esc(m)}</div></div>'

    # Cannibalization
    cannibal_html = ''
    if cannibalization and isinstance(cannibalization, list):
        ci = ''.join(f'<div class="cannibal-item"><span class="cn-pair">{esc(cn.get("topic_a",""))} ↔ {esc(cn.get("topic_b",""))}</span><span class="cn-overlap" style="color:var(--red)">{cn.get("overlap_pct",0)}%</span><span class="cn-count">{cn.get("co_occurrences",0)}x</span></div>' for cn in cannibalization[:5] if isinstance(cn,dict))
        if ci: cannibal_html = f'<div class="section"><div class="section-icon">⚠️</div><h2>Topic Cannibalization</h2><p class="section-desc">These topics overlap so much your audience may see them as the same thing.</p>{ci}</div>'

    # Posting rhythm
    rhythm_html = ''
    if velocity and isinstance(velocity, dict) and velocity.get('avg_gap_days'):
        rec = ai_deep.get('posting_rhythm_rec','') if isinstance(ai_deep,dict) else ''
        n = velocity.get('normal_posting',{}) or {}; sl = velocity.get('slow_posting',{}) or {}
        rhythm_html = f'''<div class="section"><div class="section-icon">⏱️</div><h2>Posting Rhythm</h2>
        <p class="section-desc">How posting frequency affects performance.</p>
        <div class="mega-stat-row"><div class="mega-stat"><div class="ms-val">{velocity["avg_gap_days"]}</div><div class="ms-label">Avg Days Between Posts</div></div>
        <div class="mega-stat"><div class="ms-val">{fmt_views(n.get("avg_views",0) if isinstance(n,dict) else 0)}</div><div class="ms-label">{n.get("label","Normal") if isinstance(n,dict) else "Normal"}</div></div>
        <div class="mega-stat"><div class="ms-val dim">{fmt_views(sl.get("avg_views",0) if isinstance(sl,dict) else 0)}</div><div class="ms-label">{sl.get("label","Slow") if isinstance(sl,dict) else "Slow"}</div></div></div>
        {f'<div class="ac-action">{esc(rec)}</div>' if rec else ''}</div>'''

    # Voice JSON for Write It
    voice_json = json.dumps(voice_profile, ensure_ascii=False)
    base = f"/c/{slug}" if slug else "."

    # ─── Wrap sections ─────────────────────────────────────────
    def _section(icon, title, desc, content, condition=True):
        if not condition or not content: return ''
        return f'<div class="section"><div class="section-icon">{icon}</div><h2>{title}</h2><p class="section-desc">{desc}</p>{content}</div>'

    sections = ''.join([
        big_bet_html,
        _section('🧠','What You Probably Don\'t Realize','AI-detected blind spots and missed opportunities.',f'<div class="insights-grid">{insights_cards}</div>',bool(insights_cards)),
        _section('🚀','What\'s Working NOW — Double Down','Rising topics your audience wants more of.',f'<div class="card-grid">{working_cards}</div>',bool(working_cards)),
        contrarian_html,
        _section('🔄','Resurrection Candidates — Bring These Back','Topics you stopped covering but your audience loved.',f'<div class="card-grid">{revival_cards}</div>',bool(revival_cards)),
        _section('📅','Evergreen Decay — Update These Winners','High-performing content that\'s aging. Refresh for a guaranteed win.',f'<div class="card-grid">{evergreen_cards}</div>',bool(evergreen_cards)),
        _section('🧪','Untapped Topic Combinations','Topics that perform well individually but rarely combined.',f'<div class="card-grid">{combo_cards}</div>',bool(combo_cards)),
        _section('💬','Audience Passion Signals','Videos with unusually high engagement. Your audience is telling you what they need.',f'<div class="card-grid">{passion_cards}</div>',bool(passion_cards)),
        title_html,
        cannibal_html,
        rhythm_html,
    ])

    # ─── Full page ─────────────────────────────────────────────
    return f'''<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{esc(channel)} — Content Intelligence | TrueInfluenceAI</title>
<link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=Fraunces:opsz,wght@9..144,400;9..144,700;9..144,900&display=swap" rel="stylesheet">
<style>
:root{{--bg:#06070b;--surface:#0c0d14;--surface2:#12131c;--border:#1a1c2a;--accent:#6366f1;--accent-glow:#818cf8;--accent-soft:rgba(99,102,241,.08);--text:#9ca3af;--bright:#f1f5f9;--muted:#4b5563;--green:#34d399;--red:#f87171;--gold:#fbbf24;--blue:#60a5fa}}
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:'Outfit',sans-serif;background:var(--bg);color:var(--text);line-height:1.5;-webkit-font-smoothing:antialiased}}a{{color:var(--accent-glow);text-decoration:none}}
nav{{padding:14px 32px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid var(--border);background:rgba(12,13,20,.85);position:sticky;top:0;z-index:100;backdrop-filter:blur(16px)}}nav .logo{{font-family:'Fraunces',serif;font-size:18px;font-weight:900;color:var(--bright)}}nav .logo span{{color:var(--accent)}}nav .links{{display:flex;gap:4px}}nav .links a{{color:var(--muted);font-size:13px;font-weight:500;padding:6px 14px;border-radius:8px;transition:all .2s}}nav .links a:hover{{color:var(--bright);background:var(--accent-soft)}}nav .links a.active{{color:var(--accent-glow);background:var(--accent-soft)}}
.stats-bar{{display:flex;justify-content:center;gap:40px;padding:20px 24px;background:var(--surface);border-bottom:1px solid var(--border)}}.sb-item{{text-align:center}}.sb-val{{font-family:'Fraunces',serif;font-size:22px;font-weight:900;color:var(--bright)}}.sb-label{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:1.5px;margin-top:2px}}
.container{{max-width:1100px;margin:0 auto;padding:24px}}
.big-bet{{background:linear-gradient(135deg,rgba(99,102,241,.08),rgba(139,92,246,.08));border:1px solid rgba(99,102,241,.3);border-radius:16px;padding:32px;margin-bottom:32px;text-align:center}}.bb-eyebrow{{font-size:11px;color:var(--accent);text-transform:uppercase;letter-spacing:2px;font-weight:700;margin-bottom:12px}}.bb-text{{font-size:16px;color:var(--text);line-height:1.7;max-width:800px;margin:0 auto}}
.section{{background:var(--surface);border:1px solid var(--border);border-radius:14px;padding:28px;margin-bottom:28px}}.section-icon{{font-size:24px;margin-bottom:8px}}.section h2{{font-family:'Fraunces',serif;font-size:18px;color:var(--bright);margin-bottom:4px}}.section .section-desc{{font-size:13px;color:var(--muted);margin-bottom:20px}}
.card-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}}
.action-card{{background:var(--surface2);border:1px solid var(--border);border-radius:12px;padding:18px;transition:border-color .2s}}.action-card:hover{{border-color:rgba(99,102,241,.3)}}
.ac-header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;gap:10px}}.ac-topic{{font-size:15px;font-weight:700;color:var(--bright);flex:1}}.ac-badge{{display:inline-block;padding:3px 10px;border-radius:10px;font-size:10px;font-weight:700;white-space:nowrap}}.ac-badge.rising{{background:rgba(52,211,153,.1);color:var(--green)}}.ac-badge.dormant{{background:rgba(251,191,36,.1);color:var(--gold)}}.ac-badge.stale{{background:rgba(251,146,60,.1);color:#fb923c}}.ac-badge.new{{background:rgba(96,165,250,.1);color:var(--blue)}}.ac-badge.passion{{background:rgba(248,113,113,.1);color:var(--red)}}
.ac-stat-row{{display:flex;gap:16px;margin-bottom:12px}}.ac-stat{{flex:1;text-align:center}}.ac-stat-val{{font-size:18px;font-weight:700;color:var(--bright)}}.ac-stat-val.hot{{color:var(--red)}}.ac-stat-val.warm{{color:var(--gold)}}.ac-stat-val.cool{{color:var(--blue)}}.ac-stat-val.green{{color:var(--green)}}.ac-stat-label{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.3px;margin-top:2px}}
.ac-action{{font-size:12px;color:var(--text);line-height:1.6;padding:10px 14px;background:var(--bg);border-radius:8px;border-left:3px solid var(--accent)}}
.mega-stat-row{{display:flex;gap:16px;margin-bottom:20px}}.mega-stat{{flex:1;text-align:center;background:var(--surface2);border-radius:12px;padding:20px}}.ms-val{{font-family:'Fraunces',serif;font-size:32px;font-weight:900;color:var(--bright)}}.ms-val.hot{{color:var(--red)}}.ms-val.green{{color:var(--green)}}.ms-val.dim{{color:var(--muted)}}.ms-label{{font-size:10px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-top:4px}}
.contrarian-item{{display:flex;align-items:center;padding:10px 14px;background:var(--surface2);border-radius:8px;margin-bottom:6px}}.ci-title{{flex:1;font-size:13px;color:var(--bright)}}.ci-views{{font-size:13px;font-weight:700;color:var(--accent)}}
.formula-box{{background:rgba(99,102,241,.05);border:1px solid rgba(99,102,241,.2);border-radius:12px;padding:20px;margin-bottom:20px}}.formula-label{{font-size:10px;color:var(--accent);text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:6px}}.formula-text{{font-size:18px;color:var(--bright);font-weight:700;margin-bottom:12px}}.formula-example{{font-size:12px;color:var(--muted);padding:6px 0 6px 14px;border-left:2px solid rgba(99,102,241,.2);margin:4px 0;font-style:italic}}
.pattern-row{{display:flex;align-items:center;padding:10px 14px;background:var(--surface2);border-radius:8px;margin-bottom:6px;font-size:13px}}.pr-name{{flex:1;color:var(--bright);font-weight:600}}.pr-count{{color:var(--muted);margin-right:16px;font-size:11px}}.pr-views{{color:var(--text);margin-right:16px}}.pr-lift{{font-weight:700;min-width:60px;text-align:right}}
.insights-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px}}.insight-card{{background:var(--surface2);border-radius:12px;padding:18px;border-left:4px solid var(--accent)}}.insight-card.blind{{border-left-color:var(--gold)}}.insight-card.money{{border-left-color:var(--green)}}.ic-icon{{font-size:20px;margin-bottom:4px}}.ic-label{{font-size:10px;text-transform:uppercase;letter-spacing:.5px;font-weight:700;margin-bottom:6px;color:var(--accent)}}.insight-card.blind .ic-label{{color:var(--gold)}}.insight-card.money .ic-label{{color:var(--green)}}.ic-text{{font-size:13px;color:var(--text);line-height:1.6}}
.cannibal-item{{display:flex;align-items:center;gap:12px;padding:10px 14px;background:var(--surface2);border-radius:8px;margin-bottom:6px;font-size:13px}}.cn-pair{{flex:1;color:var(--bright);font-weight:600}}.cn-overlap{{font-weight:700}}.cn-count{{color:var(--muted)}}
.sub-label{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin:16px 0 10px;font-weight:700}}
.write-btn{{display:block;width:100%;margin-top:12px;padding:10px 16px;background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.2);color:var(--accent-glow);font-size:13px;font-weight:600;border-radius:8px;cursor:pointer;transition:all .2s;font-family:inherit}}.write-btn:hover{{background:var(--accent);color:#fff;border-color:var(--accent)}}.write-btn:disabled{{opacity:.5;cursor:wait}}
.writer-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:200;backdrop-filter:blur(4px)}}.writer-overlay.active{{display:flex;align-items:center;justify-content:center}}.writer-modal{{background:var(--surface);border:1px solid var(--border);border-radius:16px;width:90%;max-width:800px;max-height:85vh;display:flex;flex-direction:column}}.wm-header{{padding:20px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px}}.wm-header h3{{flex:1;font-size:16px;color:var(--bright)}}.wm-close{{background:none;border:none;color:var(--muted);font-size:24px;cursor:pointer}}.wm-close:hover{{color:var(--bright)}}.wm-body{{flex:1;overflow-y:auto;padding:24px}}.wm-content{{font-size:14px;color:var(--text);line-height:1.8;white-space:pre-wrap}}.wm-loading{{text-align:center;padding:60px 24px;color:var(--muted)}}.wm-loading .spinner{{display:inline-block;width:32px;height:32px;border:3px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite;margin-bottom:16px}}@keyframes spin{{to{{transform:rotate(360deg)}}}}.wm-actions{{padding:16px 24px;border-top:1px solid var(--border);display:flex;gap:10px}}.wm-actions button{{padding:10px 20px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;border:none;font-family:inherit}}.wm-btn-copy{{background:var(--accent);color:#fff}}.wm-btn-close{{background:var(--surface2);color:var(--muted);border:1px solid var(--border)}}
.footer{{text-align:center;padding:40px 24px;color:var(--muted);font-size:12px}}
@media(max-width:700px){{.card-grid,.insights-grid{{grid-template-columns:1fr}}.mega-stat-row{{flex-direction:column}}.stats-bar{{gap:20px;flex-wrap:wrap}}nav{{padding:14px 16px}}}}
</style></head><body>
<nav><div class="logo"><span>TrueInfluence</span>AI · {esc(channel)}</div>
<div class="links"><a href="{base}">Home</a><a href="{base}/dashboard">Dashboard</a><a href="#" class="active">Analytics</a><a href="{base}/discuss">Discuss</a></div></nav>
<div class="stats-bar">
<div class="sb-item"><div class="sb-val">{total_videos}</div><div class="sb-label">Videos Analyzed</div></div>
<div class="sb-item"><div class="sb-val">{fmt_views(total_views)}</div><div class="sb-label">Total Views</div></div>
<div class="sb-item"><div class="sb-val">{fmt_views(channel_avg)}</div><div class="sb-label">Avg Views</div></div>
<div class="sb-item"><div class="sb-val">{engagement_rate:.1f}%</div><div class="sb-label">Engagement</div></div>
<div class="sb-item"><div class="sb-val">{len(rising_topics)}</div><div class="sb-label">Rising Topics</div></div>
<div class="sb-item"><div class="sb-val">{len(revivals)}</div><div class="sb-label">Revival Opps</div></div>
</div>
<div class="container">{sections}</div>
<div class="writer-overlay" id="writerOverlay" onclick="if(event.target===this)closeWriter()"><div class="writer-modal">
<div class="wm-header"><h3 id="wmTitle">Writing...</h3><button class="wm-close" onclick="closeWriter()">✕</button></div>
<div class="wm-body"><div id="wmContent" class="wm-content"></div></div>
<div class="wm-actions"><button class="wm-btn-copy" onclick="copyContent()">📋 Copy</button><button class="wm-btn-close" onclick="closeWriter()">Close</button></div>
</div></div>
<div class="footer">Powered by <a href="/">TrueInfluenceAI</a> · WinTech Partners · {datetime.now().strftime('%B %Y')}</div>
<script>
const VOICE={voice_json};const API_KEY='{OPENROUTER_API_KEY}';const VM='{WRITING_MODEL}';const CH='{esc(channel)}';let lastContent='';
function closeWriter(){{document.getElementById('writerOverlay').classList.remove('active')}}
function copyContent(){{navigator.clipboard.writeText(lastContent).then(()=>{{const b=document.querySelector('.wm-btn-copy');b.textContent='✅ Copied!';setTimeout(()=>b.textContent='📋 Copy',2000)}})}}
async function writeIt(btn){{const type=btn.dataset.type,topic=btn.dataset.topic,views=btn.dataset.views||'';btn.disabled=true;btn.textContent='⏳ Generating...';
const o=document.getElementById('writerOverlay'),c=document.getElementById('wmContent'),t=document.getElementById('wmTitle');
t.textContent='✍️ '+topic;c.innerHTML='<div class="wm-loading"><div class="spinner"></div><div>Writing in '+CH+'\\'s voice...</div></div>';o.classList.add('active');
const vp=VOICE.system_prompt||VOICE.system_prompt_short||('Write in a '+(VOICE.tone||'conversational')+' style.');
const yr=new Date().getFullYear();
const tp={{rising:`Script outline for "${{topic}}" — rising topic at ${{views}} avg views. 3 titles, opening hook, 5-7 points, CTA. Current year is ${{yr}}.`,revival:`Comeback script for "${{topic}}" — was dormant but proved demand (${{views}} avg). 3 fresh titles, updated angle, 5-7 points.`,evergreen:`Updated version of "${{topic}}" — original got ${{views}} views but is aging. 3 updated titles, 5-7 current points.`,combo:`Mashup script combining ${{topic}}. These work separately but rarely together. 3 creative titles, 5-7 blended points.`,passion:`Follow-up to "${{topic}}" — unusually high engagement. Go deeper. 3 titles, 5-7 advanced points, community CTA.`}};
try{{const r=await fetch('https://openrouter.ai/api/v1/chat/completions',{{method:'POST',headers:{{'Authorization':'Bearer '+API_KEY,'Content-Type':'application/json'}},body:JSON.stringify({{model:VM,messages:[{{role:'system',content:'You are a content strategist and ghostwriter. The current year is '+yr+'. Write ALL content in this voice:\\n\\n'+vp+'\\n\\nChannel: '+CH+'\\nBe specific. Sound like this creator, not generic AI. Always use the current year ('+yr+'), never reference past years as current.'}},{{role:'user',content:tp[type]||'Script outline for "'+topic+'".'}}],temperature:0.6,max_tokens:2000}})}});const d=await r.json();const text=d.choices[0].message.content;lastContent=text;c.innerHTML='<div class="wm-content">'+text.replace(/\\n/g,'<br>')+'</div>'}}catch(e){{c.innerHTML='<div style="color:var(--red)">Error: '+e.message+'</div>'}}
btn.disabled=false;btn.textContent='✍️ Write It For Me'}}
</script></body></html>'''
