"""
TrueInfluenceAI - Chat & Write API (PostgreSQL + pgvector)
============================================================
Server-side handlers for:
  /api/chat/{slug}   -> RAG Q&A in creator's voice
  /api/write/{slug}  -> Content generation (Start It / Write It / Explain More)

ALL API keys from env vars. ZERO keys in the browser.
Vector search via PostgreSQL + pgvector. No in-memory caching needed.
"""

import os, json, re
from pathlib import Path
from datetime import datetime

import requests

try:
    from pipeline.db import search_chunks, search_disney_kb, get_creator
except ImportError:
    from db import search_chunks, search_disney_kb, get_creator

# ─── ALL config from environment — NEVER hardcoded ──────────────
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL_ID = os.getenv("OPENROUTER_MODEL_ID", "google/gemini-2.5-flash-lite:online")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen/qwen3-embedding-8b")
WRITING_MODEL = os.getenv("OPENROUTER_MODEL_ID", "google/gemini-2.5-flash-lite:online")


# ─── Low-level helpers ───────────────────────────────────────────

def _embed_text(text: str) -> list:
    """Get embedding via OpenRouter. Server-side only."""
    resp = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": EMBEDDING_MODEL, "input": [text]},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"][0]["embedding"]


def _llm_call(messages: list, model: str = None, temperature: float = 0.5,
              max_tokens: int = 1200) -> str:
    """Chat completion via OpenRouter. Server-side only."""
    resp = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": model or OPENROUTER_MODEL_ID,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


def _clean_answer(text: str) -> str:
    """Strip inline citations, source references, and trailing recommendations.
    Safety net — even if the LLM ignores prompt instructions, we clean the output."""
    # [Source: anything] or [source: anything]
    text = re.sub(r'\[Source:[^\]]*\]', '', text, flags=re.IGNORECASE)
    # [website.com] or [anything.com/org/net/io/etc]
    text = re.sub(r'\[[a-zA-Z0-9.-]+\.(com|org|net|io|co|ai|gov|edu|info|vn|uk)[^\]]*\]', '', text, flags=re.IGNORECASE)
    # (Source: anything) variant
    text = re.sub(r'\(Source:[^)]*\)', '', text, flags=re.IGNORECASE)
    # Bare domain mentions mid-sentence: "according to vnexpress.net" etc.
    text = re.sub(r'\b(?:according to|per|via|from|see|on|at)\s+[a-zA-Z0-9.-]+\.(com|org|net|io|vn|co)\b', '', text, flags=re.IGNORECASE)
    # Trailing video recommendations
    text = re.sub(r'(?:You might want to |Check out |Watch my |See my |I covered this in ).*$', '', text, flags=re.DOTALL)
    # Clean up double spaces and dangling whitespace
    text = re.sub(r'  +', ' ', text)
    text = re.sub(r' +([.,!?])', r'\1', text)
    return text.strip()


# ─── Voice loading ───────────────────────────────────────────────

def _load_voice_from_bundle(bundle_path):
    """Load voice profile + channel name from bundle JSON files (fallback when DB is empty)."""
    bp = Path(bundle_path) if bundle_path else None
    voice = {}
    channel = ""
    if bp:
        vp = bp / "voice_profile.json"
        if vp.exists():
            try:
                voice = json.loads(vp.read_text(encoding="utf-8"))
            except Exception:
                pass
        mp = bp / "manifest.json"
        if mp.exists():
            try:
                manifest = json.loads(mp.read_text(encoding="utf-8"))
                channel = manifest.get("channel", "")
            except Exception:
                pass
    return voice, channel


def _get_creator_voice(slug, bundle_path=None):
    """Get voice profile + channel name. DB first, bundle JSON fallback."""
    try:
        creator = get_creator(slug)
    except Exception:
        creator = None

    if creator:
        voice = creator["voice_profile"] if creator["voice_profile"] else {}
        channel = creator["channel_name"] or slug
        if isinstance(voice, str):
            voice = json.loads(voice)
        if not voice and bundle_path:
            voice, ch = _load_voice_from_bundle(bundle_path)
            if ch:
                channel = ch
    else:
        voice, channel = _load_voice_from_bundle(bundle_path)
        if not channel:
            channel = slug

    return voice, channel


# ─── Chat (RAG Q&A) ─────────────────────────────────────────────

def handle_chat(slug: str, question: str, bundle_path: Path = None) -> dict:
    """
    Full RAG: embed question -> pgvector search -> build context -> LLM answer.
    Returns: {answer, sources: [{title, url}]}
    """
    voice, channel = _get_creator_voice(slug, bundle_path)

    # 1. Embed the question
    try:
        q_emb = _embed_text(question)
    except Exception as e:
        return {"answer": "Sorry, I had trouble processing that. Please try again.",
                "sources": [], "error": str(e)}

    # 2. Vector search — Layer 1 (creator content) + Layer 2 (Disney KB)
    hits = search_chunks(slug, q_emb, k=5)
    if not hits and bundle_path:
        hits = _fallback_json_search(slug, q_emb, bundle_path)

    # Layer 2: Disney Knowledge Base (shared across all agents)
    kb_hits = []
    try:
        kb_hits = search_disney_kb(q_emb, k=3)
    except Exception as e:
        print(f"   [ChatAPI] Disney KB search skipped: {e}")

    if not hits and not kb_hits:
        return {"answer": "I don't have enough information on that topic yet. "
                          "Try asking about something I've covered in my videos.",
                "sources": []}

    # 3. Build context — creator content (Layer 1) + Disney KB (Layer 2)
    creator_context = "\n---\n".join(
        f"[Your personal experience]\n{h['text']}" for h in hits
    ) if hits else ""

    kb_context = "\n---\n".join(
        f"[Disney reference: {h.get('category', 'general')}]\n{h['text']}" for h in kb_hits
    ) if kb_hits else ""

    context = ""
    if creator_context and kb_context:
        context = f"YOUR PERSONAL EXPERIENCE AND KNOWLEDGE (prioritize this):\n{creator_context}\n\nGENERAL DISNEY REFERENCE (use to supplement):\n{kb_context}"
    elif creator_context:
        context = creator_context
    elif kb_context:
        context = f"DISNEY REFERENCE KNOWLEDGE:\n{kb_context}"
    seen = set()
    relevant_sources = []
    for h in hits:
        vid = h.get("video_id", "")
        title = h.get("source_title", "")
        url = h.get("source_url", "")
        if vid not in seen and (title or url):
            seen.add(vid)
            relevant_sources.append({"title": title, "url": url})

    # 4. Detect if this is a chat-widget conversation or a standalone Q&A
    is_chat_widget = "CONVERSATION RULES" in question or "CONVERSATION SO FAR" in question or "Guest just said" in question
    
    voice_json = json.dumps(voice) if voice else "{}"
    year = datetime.now().year
    
    # Extract just the personality traits, NOT the video script instructions
    tone = voice.get('tone', '') if voice else ''
    phrases = voice.get('signature_phrases', []) if voice else []
    quirks = voice.get('unique_quirks', '') if voice else ''
    never_do = voice.get('what_they_never_do', '') if voice else ''
    audience_rel = voice.get('audience_relationship', '') if voice else ''

    if is_chat_widget:
        # CHAT MODE: human-sounding, opinionated, conversational
        sys_prompt = f"""You are {channel}. You're texting with someone on your website about Disney vacations.

WHO YOU ARE:
{tone}
{audience_rel}

HOW TO SOUND HUMAN (this is critical — you MUST pass as a real person):
- Write like you're texting a friend. Short. Casual. Sometimes a fragment.
- Have OPINIONS. Don't list five options. Pick ONE and tell them why.
- Say "honestly" or "okay so" or "here's the thing" sometimes. Real people hedge differently than AI.
- If you don't know something specific, say so. "I haven't stayed there myself but I've heard great things" is more human than making something up.
- Reference SPECIFIC things you've actually seen: actual room numbers, actual restaurant names, actual experiences from the knowledge provided. Never invent details.
- ONE enthusiasm word per message max. Not everything is "amazing" and "fantastic" and "incredible." Pick one.
- Never say "absolute pleasure" or "I'd be happy to help" or "great question" — those are AI tells.
- Don't cover every angle. A real person gives their take, not a Wikipedia article.
- Mix up sentence length. Short one. Then maybe a longer one that explains your thinking. Then short again.
- Use contractions always. It's, don't, won't, can't, you'll.
- The word "fantastic" is banned. So is "wonderful." So is "incredible." Find better words or just skip the adjective.
- Never end with a generic offer to help. Either ask a specific question or make a specific recommendation.

CHAT RULES:
1. 2-3 sentences max per message. This is texting.
2. Never introduce yourself. They know who you are.
3. ONE question per message.
4. When you recommend something, say WHY it fits THIS person based on what they told you. Not generic reasons.
5. If they give you enough info, commit to a recommendation. "Honestly for your family I'd look at..." not "There are several options..."
6. Signature phrases to use naturally but SPARINGLY (max one per message, skip most messages): {', '.join(phrases[:4])}
7. Never use bullet points or numbered lists.
8. Never cite sources, mention videos, or reference where you learned something.
9. Current year is {year}.

THINGS YOU NEVER DO: {never_do}

You've personally toured dozens of Disney resorts, sailed on the cruise ships, and planned hundreds of vacations. Talk from that experience."""
    else:
        # STANDARD Q&A MODE: longer but still human-sounding
        sys_prompt = f"""You are {channel}. Someone asked you a question and you're answering like you would on a livestream or in a DM — from experience, with opinions, like a real person.

YOUR VOICE:
- Tone: {tone}
- Relationship with audience: {audience_rel}
- Quirks: {quirks}
- Things you never do: {never_do}

HOW TO SOUND HUMAN (critical):
- Lead with YOUR opinion. "Okay so honestly..." or "Here's what I'd actually do..." 
- Pick a side. Don't present "Option A vs Option B" like a textbook. Tell them what YOU would pick and why.
- Reference SPECIFIC details from your experience. Actual resort names, actual restaurants, actual room types. Never invent details you don't have in your knowledge.
- If you haven't personally experienced something, say so: "I haven't done that one yet but from what I've seen..."
- Max ONE enthusiasm word per paragraph. Ban these words entirely: fantastic, wonderful, incredible, amazing. Use real reactions instead: "this blew me away", "totally worth it", "I was not expecting this."
- Never say "great question" or "I'd be happy to help" or "absolute pleasure" — dead AI giveaways.
- Vary sentence length. Short punchy ones mixed with longer explanations.
- Use contractions. Always.
- Talk in paragraphs, never bullet points or numbered lists.
- Don't cover everything. Cover what matters most and go deeper on that.
- End with a specific thought or recommendation, not a generic offer to help.
- Never cite sources, mention websites, reference videos, or use square brackets.
- Current year is {year}.

Signature phrases (use 1-2 naturally, skip if they don't fit): {', '.join(phrases[:5])}

You've personally toured these places, sailed these ships, eaten at these restaurants. Talk from real experience."""

    user_msg = (
        "Here is your knowledge to draw from "
        "(do NOT cite these — synthesize into one natural response):\n\n"
        f"{context}\n\nViewer question: {question}"
    )

    try:
        answer = _llm_call([
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_msg},
        ], temperature=0.5, max_tokens=200 if is_chat_widget else 1200)
        answer = _clean_answer(answer)
    except Exception as e:
        return {"answer": "Sorry, I'm having trouble responding right now. Please try again.",
                "sources": relevant_sources[:3], "error": str(e)}

    return {"answer": answer, "sources": relevant_sources[:3]}


def _fallback_json_search(slug, query_embedding, bundle_path):
    """Fallback: search chunks.json directly if DB is empty (pre-migration)."""
    import numpy as np
    cp = Path(bundle_path) / "chunks.json"
    sp = Path(bundle_path) / "sources.json"
    if not cp.exists():
        return []

    try:
        chunks = json.loads(cp.read_text(encoding="utf-8"))
        sources = json.loads(sp.read_text(encoding="utf-8")) if sp.exists() else []
        src_map = {s.get("source_id", ""): s for s in sources}

        texts, vids, embs = [], [], []
        for c in chunks:
            emb = c.get("embedding", [])
            if not emb:
                continue
            texts.append(c.get("text", ""))
            vids.append(c.get("video_id", ""))
            embs.append(emb)

        if not embs:
            return []

        mat = np.array(embs, dtype=np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1
        mat = mat / norms

        q = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []
        q = q / q_norm

        scores = mat @ q
        top_idx = np.argsort(scores)[::-1][:5]

        hits = []
        for idx in top_idx:
            i = int(idx)
            vid = vids[i]
            src = src_map.get(vid, {})
            hits.append({
                "text": texts[i],
                "video_id": vid,
                "source_title": src.get("title", vid),
                "source_url": src.get("url", ""),
                "score": float(scores[i]),
            })
        return hits
    except Exception as e:
        print(f"   [ChatAPI] JSON fallback error: {e}")
        return []


# ─── Write / Start / Explain ─────────────────────────────────────

def handle_write(slug: str, topic: str, write_type: str, bundle_path: Path = None,
                 extra_context: str = "", card_type: str = "", views: str = "",
                 big_bet: str = "", label: str = "") -> dict:
    """
    Generate content in the creator's voice.
    write_type: 'start' | 'write' | 'explain'
    Returns: {content: str}
    """
    voice, channel = _get_creator_voice(slug, bundle_path)

    year = datetime.now().year
    voice_json = json.dumps(voice) if voice else "{}"
    ctx = f"\nAdditional context: {extra_context}" if extra_context else ""

    if write_type == "start":
        user_prompt = f"""Create a content STARTER for a video about: {topic}{ctx}

Provide:
1. A suggested angle or hook (1-2 sentences)
2. Three possible title options
3. 5-7 key bullet points to cover, with a brief explanation of WHY each matters
4. A suggested opening hook (first 30 seconds)

Keep everything in {channel}'s authentic voice and style. The current year is {year}.
Do NOT write the full script — just give them the framework to build from."""

    elif write_type == "explain":
        user_prompt = f"""Provide a deep strategic explanation for why {channel} should create content about: {topic}{ctx}

Cover:
1. What data patterns suggest this is a strong move
2. Why this approach vs alternatives
3. What success looks like (metrics, audience response)
4. Risk of NOT doing this
5. How it connects to their overall channel strategy
6. Expected timeline for results

Be specific and data-informed. The current year is {year}."""

    else:  # "write"
        user_prompt = f"""Write a complete video script/outline about: {topic}{ctx}

Write this ENTIRELY in {channel}'s voice and style. Include:
- A compelling hook/opener
- Key talking points with natural transitions
- Personal anecdotes or examples they would use
- A strong call-to-action ending

The current year is {year}. Make it sound exactly like {channel} speaking."""

    sys_prompt = f"""You write EXCLUSIVELY in the voice and style of {channel}.

VOICE PROFILE:
{voice_json}

RULES:
- Match their exact tone, vocabulary, sentence patterns, personality
- Use their signature phrases naturally
- Write as if {channel} is speaking directly to their audience
- Be authentic to their brand and perspective"""

    try:
        content = _llm_call([
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user_prompt},
        ], model=WRITING_MODEL, temperature=0.6, max_tokens=2000)
        return {"content": content}
    except Exception as e:
        return {"content": "Sorry, content generation failed. Please try again.",
                "error": str(e)}
