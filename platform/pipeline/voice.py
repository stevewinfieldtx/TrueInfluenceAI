"""
TrueInfluenceAI - Cloud Voice Profile Builder
===============================================
Analyzes creator content via LLM to build a deep voice profile.
Uses a stronger model (VOICE_MODEL) for linguistic analysis since
this is a one-time cost per creator and quality matters most here.

Cloud-ready version with recency weighting and 3-level analysis.
"""

import os, json, random
from pathlib import Path
from datetime import datetime

import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
# Voice analysis uses a stronger model — one-time cost per creator, quality matters
VOICE_MODEL = os.getenv("VOICE_MODEL", "anthropic/claude-sonnet-4")
# Fallback for non-voice tasks
OPENROUTER_MODEL_ID = os.getenv("OPENROUTER_MODEL_ID", "google/gemini-2.5-flash-lite:online")


def build_voice_profile(bundle_dir):
    """Build a deep LLM-generated voice profile from creator content."""
    bundle_dir = Path(bundle_dir)

    chunks = json.loads((bundle_dir / "chunks.json").read_text(encoding="utf-8"))
    sources = json.loads((bundle_dir / "sources.json").read_text(encoding="utf-8"))
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    channel = manifest.get('channel', 'Unknown')

    if not chunks:
        print("No chunks to analyze for voice profile")
        return

    # Recency-weighted sampling: recent content counts ~5x more
    # Use 50% of available chunks for richer analysis
    half_count = max(35, len(chunks) // 2)
    sampled = _recency_weighted_sample(chunks, sources, n=half_count)
    content_block = "\n---\n".join(c["text"][:500] for c in sampled)

    prompt = f"""You are a world-class forensic linguist and ghostwriter. Your job is to dissect {channel}'s 
communication DNA so precisely that content written from your analysis would be indistinguishable 
from {channel}'s own words to their most dedicated fans.

TRANSCRIPT SAMPLES (recency-weighted — more recent content sampled more heavily):
{content_block}

Analyze at THREE levels of depth:

=== LEVEL 1: MACRO VOICE (overall impression) ===
1. **TONE & ENERGY**: Not just "motivational" — describe the specific emotional register. Are they a 
   fired-up coach? A wise friend? A no-BS mentor? What's the ratio of encouragement to challenge?
2. **VOCABULARY LEVEL**: Reading level, jargon patterns, invented terms, borrowed terms from other fields
3. **AUDIENCE RELATIONSHIP**: How do they address viewers? What power dynamic exists? Peer, mentor, 
   guru, friend, older sibling? Do they use "you" vs "we" vs "I"?

=== LEVEL 2: STRUCTURAL DNA (how they build arguments) ===
4. **OPENING PATTERNS**: How do they start a topic? Myth-bust? Personal story? Bold claim? Question? 
   Identify their top 2-3 opening moves with specific examples from the transcripts.
5. **ARGUMENT ARCHITECTURE**: What's their typical flow? (e.g., Problem → Failed solutions → Their 
   framework → Case study → Action steps). Map the actual structure they repeat.
6. **TRANSITION PATTERNS**: Exact phrases they use to shift between sections. Not generic ones — their 
   specific verbal bridges.
7. **CLOSING PATTERNS**: How do they wrap up? CTA style? Final encouragement? Challenge to the viewer?

=== LEVEL 3: MICRO PATTERNS (the fingerprints) ===
8. **SIGNATURE PHRASES**: Not just catchphrases — include verbal tics, filler patterns, emphasis words 
   they overuse ("literally", "actually", "here's the thing"), and phrases that signal transitions.
9. **SENTENCE RHYTHM**: Map the actual short-long-short pattern. Do they use fragments for emphasis? 
   Do they stack rhetorical questions? Do they use lists of three?
10. **PERSUASION FINGERPRINT**: What's their specific evidence style? Client stories with exact numbers? 
    Personal vulnerability? Contrarian reframes? Authority citations? Rank their persuasion tools.
11. **UNIQUE QUIRKS**: Anything that's distinctly THEM — humor style, metaphor preferences, topics they 
    always circle back to, emotional beats they hit repeatedly.
12. **WHAT THEY NEVER DO**: Equally important — what's absent from their style? (e.g., never uses 
    academic citations, never swears, never gets deeply personal about family, etc.)

Then write TWO system prompts:

a) **system_prompt** (300-400 words): A comprehensive prompt that instructs an AI to write long-form 
   content (scripts, articles, emails) indistinguishable from {channel}. Include specific 
   structural rules, phrase examples, and anti-patterns (what NOT to do).

b) **system_prompt_short** (150 words): A condensed version for quick social media posts, comments, 
   and short replies that still sound authentically like {channel}.

Format your response as JSON:
{{
  "tone": "...",
  "vocabulary_level": "...",
  "sentence_style": "...",
  "signature_phrases": ["...", "...", "..."],
  "opening_patterns": "...",
  "argument_architecture": "...",
  "transition_phrases": ["...", "..."],
  "closing_patterns": "...",
  "speaking_patterns": "...",
  "audience_relationship": "...",
  "persuasion_style": "...",
  "unique_quirks": "...",
  "what_they_never_do": "...",
  "system_prompt": "...",
  "system_prompt_short": "..."
}}

Return ONLY valid JSON, no markdown fences."""

    try:
        print(f"Voice analysis using {VOICE_MODEL} ({len(sampled)} samples)...")
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": VOICE_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3,
                "max_tokens": 4000,
            },
            timeout=180,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]

        # Clean markdown fencing if present
        if "```" in text:
            text = text.split("```json")[-1].split("```")[0] if "```json" in text else text.split("```")[1].split("```")[0]

        profile = json.loads(text.strip())
        profile["generated_at"] = datetime.utcnow().isoformat()
        profile["model"] = VOICE_MODEL
        profile["sample_count"] = len(sampled)

        (bundle_dir / "voice_profile.json").write_text(
            json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Voice profile built ({len(sampled)} samples, {VOICE_MODEL})")

    except Exception as e:
        print(f"Voice profile failed with {VOICE_MODEL}: {e}")
        # Fallback: try with the cheaper model
        print(f"Falling back to {OPENROUTER_MODEL_ID}...")
        try:
            resp = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": OPENROUTER_MODEL_ID,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3,
                    "max_tokens": 3000,
                },
                timeout=120,
            )
            resp.raise_for_status()
            text = resp.json()["choices"][0]["message"]["content"]
            if "```" in text:
                text = text.split("```json")[-1].split("```")[0] if "```json" in text else text.split("```")[1].split("```")[0]
            profile = json.loads(text.strip())
            profile["generated_at"] = datetime.utcnow().isoformat()
            profile["model"] = OPENROUTER_MODEL_ID + " (fallback)"
            profile["sample_count"] = len(sampled)
            (bundle_dir / "voice_profile.json").write_text(
                json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8"
            )
            print(f"Voice profile built with fallback model ({len(sampled)} samples)")
        except Exception as e2:
            print(f"Fallback also failed: {e2}")
            (bundle_dir / "voice_profile.json").write_text(
                json.dumps({"tone": "Analysis pending", "error": str(e2)}, indent=2),
                encoding="utf-8",
            )


def _recency_weighted_sample(chunks, sources, n=50):
    """Sample chunks with recency bias (recent content ~5x more likely)."""
    sorted_sources = sorted(
        [s for s in sources if s.get("published_at") or s.get("published_text")],
        key=lambda s: s.get("published_at", s.get("published_text", "")),
        reverse=True,
    )
    position_map = {s["source_id"]: i for i, s in enumerate(sorted_sources)}
    total = max(len(sorted_sources), 1)

    weights = []
    for c in chunks:
        vid = c.get("video_id", c.get("source_id", ""))
        pos = position_map.get(vid, total)
        pct = pos / total
        if pct < 0.25:
            w = 1.0
        elif pct < 0.50:
            w = 0.7
        elif pct < 0.75:
            w = 0.4
        else:
            w = 0.2
        weights.append(w)

    if len(chunks) <= n:
        return chunks

    selected = set()
    attempts = 0
    while len(selected) < n and attempts < n * 10:
        idx = random.choices(range(len(chunks)), weights=weights, k=1)[0]
        selected.add(idx)
        attempts += 1

    return [chunks[i] for i in sorted(selected)]
