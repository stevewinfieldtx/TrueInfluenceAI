"""
TrueInfluenceAI - Actionable Analytics Core
=============================================
Importable module that generates the actionable analytics HTML.
Called by pages.py: from build_actionable_core import build_analytics_html

Accepts pre-loaded data dict from _load_bundle().
"""

import os, json, traceback
from pathlib import Path
from datetime import datetime

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
VOICE_MODEL = os.getenv("VOICE_MODEL", "anthropic/claude-sonnet-4")  # Voice ANALYSIS only
WRITING_MODEL = os.getenv("OPENROUTER_MODEL_ID", "google/gemini-2.5-flash-lite:online")  # Content generation (cheap, high volume)


def esc(s):
    if not isinstance(s, str): s = str(s)
    return s.replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;').replace("'","&#39;")

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
    try:
        return _build_analytics_html_inner(bp, data)
    except Exception as e:
        print(f"ERROR building analytics: {e}")
        traceback.print_exc()
        channel = data.get('manifest', {}).get('channel', 'Unknown')
        return f'''<!DOCTYPE html><html><head><title>Error</title></head><body style="background:#06070b;color:#f87171;font-family:monospace;padding:40px">
        <h1>Dashboard Build Error</h1><pre>{traceback.format_exc()}</pre>
        <p style="color:#9ca3af">This error has been logged. The page will work once the data is fixed.</p></body></html>'''

def _build_analytics_html_inner(bp, data):
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
    # If JSON parse failed, ai_deep may have 'raw' field with the text — try to extract
    if isinstance(ai_deep, dict) and 'raw' in ai_deep and 'one_big_bet' not in ai_deep:
        raw = ai_deep.get('raw', '')
        try:
            import re
            match = re.search(r'\{[\s\S]*\}', raw)
            if match:
                parsed = json.loads(match.group())
                if isinstance(parsed, dict) and 'one_big_bet' in parsed:
                    ai_deep = parsed
                    print("  Recovered ai_deep_analysis from raw text")
        except:
            pass
    contrarian = insights.get('contrarian_content', {}) or {}
    title_patterns = insights.get('title_patterns', {}) or {}
    engagement = insights.get('engagement_anomalies', {}) or {}
    revivals = insights.get('revival_candidates', []) or []
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
            raw_co = topic_pairs.get(f"{t1} + {t2}", 0) or topic_pairs.get(f"{t2} + {t1}", 0)
            co = raw_co.get('count', 0) if isinstance(raw_co, dict) else (raw_co or 0)
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

    # ─── Big Bet + Four Follow-ups ──────────────────────────────────
    big_bet = ai_deep.get('one_big_bet', '') if isinstance(ai_deep, dict) else ''
    four_followups = ai_deep.get('four_followups', []) if isinstance(ai_deep, dict) else []
    big_bet_esc = esc(big_bet[:200]) if big_bet else ''
    big_bet_html = ''
    if big_bet:
        followups_html = ''
        if four_followups and isinstance(four_followups, list):
            followup_items = ''
            icons = ['🎯', '🔄', '🚫', '⚡']
            labels = ['Double Down', 'New Angle', 'Stop This', 'Quick Win']
            for i, fu in enumerate(four_followups[:4]):
                icon = icons[i] if i < len(icons) else '▸'
                label = labels[i] if i < len(labels) else f'Action {i+1}'
                fu_esc = esc(fu)
                fu_short = esc(fu[:60])
                fu_long = esc(fu[:80])
                bb_short = esc(big_bet[:120])
                followup_items += f'''<div class="fu-card">
                    <div class="fu-icon">{icon}</div><div class="fu-label">{label}</div><div class="fu-text">{fu_esc}</div>
                    <div class="btn-row fu-btn-row">
                        <button class="act-btn start" onclick="startIt(this)" data-type="bigbet" data-topic="{fu_short}" data-views="0">🚀 START IT</button>
                        <button class="act-btn write" onclick="writeIt(this)" data-type="bigbet" data-topic="{fu_short}" data-views="0">✍️ WRITE IT</button>
                    </div>
                    <button class="explain-btn" onclick="explainMore(this)" data-topic="{fu_long}" data-bigbet="{bb_short}" data-label="{label}">🔍 Explain More</button>
                </div>'''
            followups_html = f'<div class="fu-grid">{followup_items}</div>'
        bb_topic = esc(big_bet[:60])
        bb_long = esc(big_bet[:80])
        bb_ref = esc(big_bet[:120])
        big_bet_html = f'''<div class="big-bet">
        <div class="bb-eyebrow">🏆 THE ONE BIG BET</div>
        <div class="bb-text">{esc(big_bet)}</div>
        <div class="btn-row bb-btn-row">
            <button class="act-btn start" onclick="startIt(this)" data-type="bigbet" data-topic="{bb_topic}" data-views="0">🚀 START IT</button>
            <button class="act-btn write" onclick="writeIt(this)" data-type="bigbet" data-topic="{bb_topic}" data-views="0">✍️ WRITE IT</button>
        </div>
        <button class="explain-btn bb-explain" onclick="explainMore(this)" data-topic="{bb_long}" data-bigbet="{bb_ref}" data-label="The Big Bet">🔍 Explain More</button>
        {followups_html}
        </div>'''

    # ─── Card builders ───────────────────────────────────────────
    def _card(topic, badge_cls, badge_text, stats, action, write_type, write_topic, write_views=0):
        stat_html = ''
        for val, label, cls in stats:
            stat_html += f'<div class="ac-stat"><div class="ac-stat-val {cls}">{val}</div><div class="ac-stat-label">{label}</div></div>'
        wt = esc(write_topic)
        return f'''<div class="action-card">
            <div class="ac-header"><span class="ac-topic">{esc(topic)}</span><span class="ac-badge {badge_cls}">{badge_text}</span></div>
            <div class="ac-stat-row">{stat_html}</div>
            <div class="ac-action">{action}</div>
            <div class="btn-row">
                <button class="act-btn start" onclick="startIt(this)" data-type="{write_type}" data-topic="{wt}" data-views="{write_views}">🚀 START IT</button>
                <button class="act-btn write" onclick="writeIt(this)" data-type="{write_type}" data-topic="{wt}" data-views="{write_views}">✍️ WRITE IT</button>
            </div>
        </div>'''

    # Rising
    working_cards = ''
    rising_actions = [
        '✅ This topic is accelerating. Your recent videos outperform your older ones — double down before competitors catch on.',
        '📈 Momentum is building here. Your audience is responding more each time — ride this wave with a series.',
        '🎯 Consistent growth pattern. This isn\'t a fluke — it\'s a proven demand signal. Make this a content pillar.',
        '🔥 Recent uploads on this topic are outperforming your channel average. Your algorithm is rewarding this.',
        '🚀 The trajectory is clear — each video on this topic does better than the last. Go deeper, not wider.',
        '💡 Your audience keeps coming back for this. Consider a definitive guide or series to own this space.',
    ]
    for i, t in enumerate(rising_topics[:6]):
        pc = 'hot' if t['vs_channel']>1.3 else ('warm' if t['vs_channel']>0.8 else 'cool')
        working_cards += _card(t['name'],'rising','▲ Rising',
            [(fmt_views(t['avg_views']),'Avg Views',''),(f"{t['vs_channel']}x",'vs Channel',pc),(f"{t['recent']}/{t['middle']}/{t['older']}",'R/M/O','')],
            rising_actions[i % len(rising_actions)],'rising',t['name'],t['avg_views'])

    # Revivals
    revival_cards = ''
    revival_actions = [
        '🔄 This topic averaged {views} views and you stopped covering it. Your audience didn\'t stop caring — bring it back with a fresh angle.',
        '💰 You left {views}-view-average content on the table. A comeback video with an updated take is nearly guaranteed to perform.',
        '🎯 {views} avg views proves the demand existed. The question isn\'t IF this works — it\'s what\'s changed since you last covered it.',
        '⏰ Your audience searched for this and found silence. Fill that gap before a competitor does.',
        '🔍 This was working and you moved on. Sometimes the smartest content move is going back to what your data already proved.',
        '💡 Dormant doesn\'t mean dead. This topic has {views} avg views baked in — a fresh take reactivates that demand instantly.',
    ]
    for i, rv in enumerate(revivals[:6]):
        if not isinstance(rv, dict): continue
        views_str = fmt_views(rv.get('avg_views',0))
        action = revival_actions[i % len(revival_actions)].replace('{views}', views_str)
        revival_cards += _card(rv.get('topic',''),'dormant',f"💤 {rv.get('trend','dormant').title()}",
            [(fmt_views(rv.get('avg_views',0)),'Avg Views',''),(f"{rv.get('vs_channel',0)}x",'vs Channel','hot')],
            action,'revival',rv.get('topic',''),rv.get('avg_views',0))

    # Evergreen
    evergreen_cards = ''
    evergreen_actions = [
        '📝 This got {views} views {age} but the info is aging. An updated version captures the same audience with current data.',
        '♻️ Your {age} content still gets traffic but the facts may be stale. Refresh it and YouTube will push it again.',
        '🎯 {views} views proves this topic has evergreen demand. A "{year} Edition" update is the lowest-risk, highest-reward move.',
        '📈 Content this old with these numbers means search demand is real. Update the title, thumbnail, and data for a guaranteed boost.',
        '💡 This was a hit {age}. The audience is still searching for it — give them the version with today\'s numbers.',
        '🔄 Don\'t let your best content decay. A refresh keeps you ranking while competitors create from scratch.',
    ]
    yr = datetime.utcnow().year
    for i, ev in enumerate(evergreen_decay[:6]):
        action = evergreen_actions[i % len(evergreen_actions)].replace('{views}', fmt_views(ev['views'])).replace('{age}', ev['age_label']).replace('{year}', str(yr))
        evergreen_cards += _card(ev['title'][:60],'stale',f"📅 {ev['age_label']}",
            [(fmt_views(ev['views']),'Views',''),(ev['published_at'],'Published','')],
            action,'evergreen',ev['title'][:60],ev['views'])

    # Combos
    combo_cards = ''
    combo_actions = [
        '🧪 These topics crush it solo but you\'ve barely combined them. A mashup could outperform both.',
        '🎯 Your audience loves each topic separately — give them both in one video and watch retention spike.',
        '💡 Zero overlap so far. This is a fresh angle nobody\'s seen from you yet.',
        '🚀 Two proven winners that haven\'t met yet. This is low-risk, high-upside content.',
        '🎲 Rare combo = algorithmic novelty. YouTube rewards content that doesn\'t fit existing buckets.',
        '🔥 Each topic already has demand. Combining them creates a video with two built-in audiences.',
    ]
    for i, cb in enumerate(untapped_combos[:6]):
        action = combo_actions[i % len(combo_actions)]
        combo_cards += _card(f"{cb['topic_a']} + {cb['topic_b']}",'new','🆕 Untapped',
            [(fmt_views(cb['views_a']),esc(cb['topic_a'][:15]),''),(fmt_views(cb['views_b']),esc(cb['topic_b'][:15]),''),(str(cb['co_count']),'Times Combined','')],
            action,'combo',f"{cb['topic_a']} + {cb['topic_b']}",cb['views_a'])

    # Passion — filter out entries with no meaningful engagement data
    passion_cards = ''
    avg_cr = engagement.get('channel_avg_comment_rate',0) or 0
    avg_er = engagement.get('channel_avg_like_rate',0) or 0
    valid_passion = [hp for hp in high_passion if isinstance(hp, dict) and
                     (hp.get('comment_rate', 0) > 0 or hp.get('engagement_rate', 0) > 0)]
    passion_actions = [
        '💬 {mult}x your normal interaction rate. This topic hit a nerve — your audience wants to discuss, debate, and share this.',
        '🔥 When engagement spikes like this, it means you said something your audience NEEDED to hear. Follow up with a deeper dive.',
        '🎯 {mult}x engagement isn\'t luck — it\'s demand. Your audience is telling you exactly what they want more of.',
        '💡 High interaction = high emotional resonance. This topic makes people feel something. Explore adjacent angles.',
        '🚀 Your audience doesn\'t just watch this — they react. That\'s the strongest signal YouTube\'s algorithm responds to.',
    ]
    for pi, hp in enumerate(valid_passion[:5]):
        cr = hp.get('comment_rate',0)
        er = hp.get('engagement_rate',0)
        if cr > 0 and avg_cr > 0:
            mult = round(cr/avg_cr,1)
            badge = f"🔥 {mult}x comments"
            stat3 = (f"{cr}%", 'Comment Rate', '')
        else:
            mult = round(er/avg_er,1) if avg_er > 0 else 0
            badge = f"🔥 {er}% engaged"
            stat3 = (f"{er}%", 'Engagement', '')
        action = passion_actions[pi % len(passion_actions)].replace('{mult}', str(mult))
        passion_cards += _card(hp.get('title','')[:55],'passion',badge,
            [(fmt_views(hp.get('views',0)),'Views',''),
             (f"{hp.get('likes',0):,}",'Likes',''),
             stat3],
            action,'passion',hp.get('title','')[:55],hp.get('views',0))

    # Contrarian — only show if lift is meaningful (15%+) and enough data
    contrarian_html = ''
    if contrarian and isinstance(contrarian, dict):
        c_avg = contrarian.get('avg_views_contrarian',0); n_avg = contrarian.get('avg_views_conventional',0)
        c_lift = contrarian.get('lift_pct',0); c_count = contrarian.get('contrarian_count',0)
        top_c = contrarian.get('top_contrarian',[]) or []
        if c_lift >= 15 and c_count >= 5:
            items = ''.join(f'<div class="contrarian-item"><span class="ci-title">{esc(v.get("title",""))}</span><span class="ci-views">{fmt_views(v.get("views",0))}</span></div>' for v in top_c[:5] if isinstance(v,dict))
            contrarian_cards = ''
            contrarian_angles = [
                ('Why {topic} Is a Trap', '🚫 Take your strongest topic and argue the opposite. Your audience already trusts you on this — a contrarian take will explode.'),
                ('The Truth About {topic} Nobody Tells You', '🔍 Your audience craves insider perspective. Expose the uncomfortable reality.'),
                ('Stop Doing {topic} Wrong', '⚠️ Position yourself as the corrector. Call out the conventional advice and offer the real answer.'),
                ('I Was Wrong About {topic}', '💡 Vulnerability + reversal = massive engagement. Admitting mistakes builds more trust than being right.'),
            ]
            for i, rt in enumerate(rising_topics[:4]):
                angle_title, angle_action = contrarian_angles[i % len(contrarian_angles)]
                suggested_title = angle_title.replace('{topic}', rt['name'])
                contrarian_cards += _card(suggested_title, 'passion', f'⚡ +{c_lift:.0f}% lift',
                    [(fmt_views(rt['avg_views']), 'Base Topic Views', ''), (fmt_views(c_avg), 'Contrarian Avg', 'hot')],
                    angle_action, 'rising', suggested_title, rt['avg_views'])
            contrarian_html = f'''<div class="section"><div class="section-icon">⚡</div><h2>Your Contrarian Edge</h2>
            <p class="section-desc">When you challenge assumptions, your audience pays attention — {c_lift:.0f}% more views on average.</p>
            <div class="mega-stat-row"><div class="mega-stat"><div class="ms-val hot">{fmt_views(c_avg)}</div><div class="ms-label">Contrarian Avg</div></div>
            <div class="mega-stat"><div class="ms-val dim">{fmt_views(n_avg)}</div><div class="ms-label">Conventional Avg</div></div>
            <div class="mega-stat"><div class="ms-val green">+{c_lift:.0f}%</div><div class="ms-label">Lift</div></div></div>
            <div class="sub-label">Proven Contrarian Hits</div>{items}
            {f'<div class="sub-label" style="margin-top:24px">🎯 Try These Contrarian Angles on Your Rising Topics</div><div class="card-grid">{contrarian_cards}</div>' if contrarian_cards else ''}
            </div>'''

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

    # Blind spots + Money — with START IT / WRITE IT buttons
    blind_spots = ai_deep.get('blind_spots',[]) if isinstance(ai_deep,dict) else []
    money = ai_deep.get('money_left_on_table',[]) if isinstance(ai_deep,dict) else []
    insights_cards = ''
    for bs in (blind_spots if isinstance(blind_spots,list) else []):
        bs_esc = esc(bs)
        bs_short = esc(bs[:60])
        insights_cards += f'''<div class="insight-card blind"><div class="ic-icon">👁️</div><div class="ic-label">Blind Spot</div><div class="ic-text">{bs_esc}</div>
            <div class="btn-row ic-btn-row">
                <button class="act-btn start" onclick="startIt(this)" data-type="blindspot" data-topic="{bs_short}" data-views="0">🚀 START IT</button>
                <button class="act-btn write" onclick="writeIt(this)" data-type="blindspot" data-topic="{bs_short}" data-views="0">✍️ WRITE IT</button>
            </div></div>'''
    for m in (money if isinstance(money,list) else []):
        m_esc = esc(m)
        m_short = esc(m[:60])
        insights_cards += f'''<div class="insight-card money"><div class="ic-icon">💰</div><div class="ic-label">Money on the Table</div><div class="ic-text">{m_esc}</div>
            <div class="btn-row ic-btn-row">
                <button class="act-btn start" onclick="startIt(this)" data-type="money" data-topic="{m_short}" data-views="0">🚀 START IT</button>
                <button class="act-btn write" onclick="writeIt(this)" data-type="money" data-topic="{m_short}" data-views="0">✍️ WRITE IT</button>
            </div></div>'''

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
    ])

    # ─── Build JavaScript as a separate block to avoid f-string escaping hell ───
    js_block = _build_js_block(voice_json, OPENROUTER_API_KEY, WRITING_MODEL, esc(channel), big_bet_esc)

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
.fu-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-top:24px;text-align:left;max-width:900px;margin-left:auto;margin-right:auto}}.fu-card{{background:rgba(6,7,11,.5);border:1px solid var(--border);border-radius:10px;padding:16px}}.fu-icon{{font-size:20px;margin-bottom:6px}}.fu-label{{font-size:10px;color:var(--accent);text-transform:uppercase;letter-spacing:1.5px;font-weight:700;margin-bottom:6px}}.fu-text{{font-size:13px;color:var(--text);line-height:1.6}}@media(max-width:600px){{.fu-grid{{grid-template-columns:1fr}}}}
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
.sub-label{{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin:16px 0 10px;font-weight:700}}
.btn-row{{display:flex;gap:8px;margin-top:12px}}
.act-btn{{flex:1;padding:10px 16px;font-size:13px;font-weight:600;border-radius:8px;cursor:pointer;transition:all .2s;font-family:inherit;text-transform:uppercase;letter-spacing:.5px}}
.act-btn.start{{background:rgba(52,211,153,.08);border:1px solid rgba(52,211,153,.25);color:var(--green)}}.act-btn.start:hover{{background:rgba(52,211,153,.2);border-color:var(--green)}}
.act-btn.write{{background:rgba(99,102,241,.08);border:1px solid rgba(99,102,241,.2);color:var(--accent-glow)}}.act-btn.write:hover{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.act-btn:disabled{{opacity:.5;cursor:wait}}
.explain-btn{{display:block;width:100%;margin-top:8px;padding:8px 14px;background:rgba(251,191,36,.06);border:1px solid rgba(251,191,36,.2);color:var(--gold);font-size:11px;font-weight:600;border-radius:8px;cursor:pointer;transition:all .2s;font-family:inherit}}.explain-btn:hover{{background:rgba(251,191,36,.15);border-color:var(--gold)}}.explain-btn:disabled{{opacity:.5;cursor:wait}}
.bb-btn-row{{justify-content:center;max-width:500px;margin:16px auto 0}}.bb-explain{{max-width:300px;margin:10px auto 0}}
.fu-btn-row{{margin-top:10px}}.ic-btn-row{{margin-top:10px}}
.writer-overlay{{display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:200;backdrop-filter:blur(4px)}}.writer-overlay.active{{display:flex;align-items:center;justify-content:center}}.writer-modal{{background:var(--surface);border:1px solid var(--border);border-radius:16px;width:90%;max-width:800px;max-height:85vh;display:flex;flex-direction:column}}.wm-header{{padding:20px 24px;border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px}}.wm-header h3{{flex:1;font-size:16px;color:var(--bright)}}.wm-close{{background:none;border:none;color:var(--muted);font-size:24px;cursor:pointer}}.wm-close:hover{{color:var(--bright)}}.wm-body{{flex:1;overflow-y:auto;padding:24px}}.wm-content{{font-size:14px;color:var(--text);line-height:1.8;white-space:pre-wrap}}.wm-loading{{text-align:center;padding:60px 24px;color:var(--muted)}}.wm-loading .spinner{{display:inline-block;width:32px;height:32px;border:3px solid var(--border);border-top-color:var(--accent);border-radius:50%;animation:spin .8s linear infinite;margin-bottom:16px}}@keyframes spin{{to{{transform:rotate(360deg)}}}}.wm-actions{{padding:16px 24px;border-top:1px solid var(--border);display:flex;gap:10px}}.wm-actions button{{padding:10px 20px;border-radius:8px;font-size:13px;font-weight:600;cursor:pointer;border:none;font-family:inherit}}.wm-btn-copy{{background:var(--accent);color:#fff}}.wm-btn-close{{background:var(--surface2);color:var(--muted);border:1px solid var(--border)}}
.footer{{text-align:center;padding:40px 24px;color:var(--muted);font-size:12px}}
@media(max-width:700px){{.card-grid,.insights-grid{{grid-template-columns:1fr}}.mega-stat-row{{flex-direction:column}}.stats-bar{{gap:20px;flex-wrap:wrap}}nav{{padding:14px 16px}}}}
</style></head><body>
<nav><div class="logo"><span>True</span>Influence<span>AI</span> · {esc(channel)}</div>
<div class="links"><a href="{base}">Home</a><a href="#" class="active">Dashboard</a><a href="{base}/discuss">Discuss</a></div></nav>
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
{js_block}
</body></html>'''


def _build_js_block(voice_json, api_key, writing_model, channel, big_bet_esc):
    """Build JS as a plain string — NO f-string escaping issues."""
    return '''<script>
const VOICE=''' + voice_json + ''';
const API_KEY="''' + api_key + '''";
const VM="''' + writing_model + '''";
const CH="''' + channel + '''";
const BIGBET="''' + big_bet_esc + '''";
let lastContent="";

function closeWriter(){document.getElementById("writerOverlay").classList.remove("active")}
function copyContent(){navigator.clipboard.writeText(lastContent).then(function(){var b=document.querySelector(".wm-btn-copy");b.textContent="✅ Copied!";setTimeout(function(){b.textContent="📋 Copy"},2000)})}

function _openModal(title,loadingMsg){
  var o=document.getElementById("writerOverlay"),c=document.getElementById("wmContent"),t=document.getElementById("wmTitle");
  t.textContent=title;
  c.innerHTML='<div class="wm-loading"><div class="spinner"></div><div>'+loadingMsg+'</div></div>';
  o.classList.add("active");
  return {o:o,c:c,t:t};
}

async function _callLLM(sysPr,userPr){
  var r=await fetch("https://openrouter.ai/api/v1/chat/completions",{
    method:"POST",headers:{"Authorization":"Bearer "+API_KEY,"Content-Type":"application/json"},
    body:JSON.stringify({model:VM,messages:[{role:"system",content:sysPr},{role:"user",content:userPr}],temperature:0.5,max_tokens:2000})
  });
  var d=await r.json();
  return d.choices[0].message.content;
}

var writePrompts={
  rising:'Script outline for "TOPIC" — rising topic at VIEWS avg views. 3 titles, opening hook, 5-7 points, CTA.',
  revival:'Comeback script for "TOPIC" — was dormant but proved demand (VIEWS avg). 3 fresh titles, updated angle, 5-7 points.',
  evergreen:'Updated version of "TOPIC" — original got VIEWS views but is aging. 3 updated titles, 5-7 current points.',
  combo:'Mashup script combining TOPIC. These work separately but rarely together. 3 creative titles, 5-7 blended points.',
  passion:'Follow-up to "TOPIC" — unusually high engagement. Go deeper. 3 titles, 5-7 advanced points, community CTA.',
  bigbet:'Full script for this strategic action: "TOPIC". Complete script with 3 titles, hook, 5-7 detailed points, and CTA.',
  blindspot:'Script addressing this blind spot: "TOPIC". 3 titles, hook, 5-7 points that tackle this gap, and CTA.',
  money:'Script capturing this opportunity: "TOPIC". 3 titles, hook, 5-7 points, and CTA focused on this gap.'
};

var startPrompts={
  rising:'For the rising topic "TOPIC" (VIEWS avg views), give a STARTING FRAMEWORK only: 1) Suggested angle in 1-2 sentences 2) 3 possible titles 3) 5-7 bullet points with brief explanation of WHY each matters 4) Suggested hook. Do NOT write the full script.',
  revival:'For the revival topic "TOPIC" (VIEWS avg views, dormant), STARTING FRAMEWORK: 1) What changed since they last covered it 2) Fresh angle in 1-2 sentences 3) 3 updated titles 4) 5-7 bullet points with explanations 5) Hook idea. Do NOT write the full script.',
  evergreen:'For updating "TOPIC" (VIEWS views, aging), STARTING FRAMEWORK: 1) What needs updating 2) 3 refreshed titles 3) 5-7 bullet points with explanations 4) New hook. Do NOT write the full script.',
  combo:'For combining TOPIC, STARTING FRAMEWORK: 1) Thesis tying both together 2) 3 mashup titles 3) 5-7 blended bullet points with explanations 4) Hook. Do NOT write full script.',
  passion:'For high-engagement topic "TOPIC", STARTING FRAMEWORK for deeper follow-up: 1) Why this resonated 2) 3 follow-up titles 3) 5-7 deeper bullet points with explanations 4) CTA idea. Do NOT write full script.',
  bigbet:'For this strategic action: "TOPIC", STARTING FRAMEWORK: 1) Core thesis in 1-2 sentences 2) 3 title options 3) 5-7 bullet points with explanations of why each matters 4) Suggested hook. Do NOT write full script.',
  blindspot:'For this blind spot: "TOPIC", STARTING FRAMEWORK: 1) Why this matters 2) 3 video title ideas 3) 5-7 content bullet points with explanations 4) Hook idea. Do NOT write full script.',
  money:'For this missed opportunity: "TOPIC", STARTING FRAMEWORK: 1) The opportunity in 1-2 sentences 2) 3 title ideas 3) 5-7 bullet points with explanations 4) Hook idea. Do NOT write full script.'
};

async function writeIt(btn){
  var type=btn.dataset.type,topic=btn.dataset.topic,views=btn.dataset.views||"";
  btn.disabled=true;btn.textContent="⏳ WRITING...";
  var m=_openModal("✍️ "+topic,"Writing in "+CH+"'s voice...");
  var vp=VOICE.system_prompt||VOICE.system_prompt_short||("Write in a "+(VOICE.tone||"conversational")+" style.");
  var yr=new Date().getFullYear();
  var tpl=writePrompts[type]||('Script outline for "TOPIC".');
  var prompt=tpl.replace(/TOPIC/g,topic).replace(/VIEWS/g,views);
  try{
    var text=await _callLLM(
      "You are a content strategist and ghostwriter. Year: "+yr+". Write in this voice:\\n\\n"+vp+"\\n\\nChannel: "+CH+"\\nBe specific. Sound like this creator.",
      prompt
    );
    lastContent=text;
    m.c.innerHTML='<div class="wm-content">'+text.replace(/\\n/g,"<br>")+'</div>';
  }catch(e){m.c.innerHTML='<div style="color:#f87171">Error: '+e.message+'</div>'}
  btn.disabled=false;btn.textContent="✍️ WRITE IT";
}

async function startIt(btn){
  var type=btn.dataset.type,topic=btn.dataset.topic,views=btn.dataset.views||"";
  btn.disabled=true;btn.textContent="⏳ THINKING...";
  var m=_openModal("🚀 Getting You Started: "+topic,"Building your starting framework...");
  var yr=new Date().getFullYear();
  var tpl=startPrompts[type]||('Starting framework for "TOPIC".');
  var prompt=tpl.replace(/TOPIC/g,topic).replace(/VIEWS/g,views);
  try{
    var text=await _callLLM(
      "You are a content strategist. Year: "+yr+". Give a concise STARTING FRAMEWORK — bullet points with brief explanations, titles, and a hook. Do NOT write the full script. Channel: "+CH,
      prompt
    );
    lastContent=text;
    m.c.innerHTML='<div class="wm-content">'+text.replace(/\\n/g,"<br>")+'</div>';
  }catch(e){m.c.innerHTML='<div style="color:#f87171">Error: '+e.message+'</div>'}
  btn.disabled=false;btn.textContent="🚀 START IT";
}

async function explainMore(btn){
  var topic=btn.dataset.topic,bigbet=btn.dataset.bigbet||BIGBET,label=btn.dataset.label||"";
  btn.disabled=true;btn.textContent="⏳ ANALYZING...";
  var m=_openModal("🔍 Deep Dive: "+label,"Building deep explanation...");
  var yr=new Date().getFullYear();
  try{
    var text=await _callLLM(
      "You are a senior content strategist explaining reasoning in depth. Be thorough, cite data patterns, explain WHY. Channel: "+CH+". Year: "+yr,
      "DEEP EXPLANATION of this strategic recommendation:\\n\\nThe Big Bet: \\""+bigbet+"\\"\\n\\nSpecific action: \\""+topic+"\\" ("+label+")\\n\\nExplain:\\n1) Data pattern behind this recommendation\\n2) Why this approach vs alternatives\\n3) What success looks like\\n4) Risk of NOT doing it\\n5) How it connects to overall channel strategy\\n6) Timeline for results\\n\\nBe specific and explain the strategic logic step by step."
    );
    lastContent=text;
    m.c.innerHTML='<div class="wm-content">'+text.replace(/\\n/g,"<br>")+'</div>';
  }catch(e){m.c.innerHTML='<div style="color:#f87171">Error: '+e.message+'</div>'}
  btn.disabled=false;btn.textContent="🔍 Explain More";
}
</script>'''
