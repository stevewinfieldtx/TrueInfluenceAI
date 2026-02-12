"""
TrueInfluenceAI - Cloud Voice Profile Builder
===============================================
Analyzes creator content via LLM to build a voice profile.
Cloud-ready version of build_voice.py with recency weighting.
"""

import os, json, random
from pathlib import Path

import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL_ID = os.getenv("OPENROUTER_MODEL_ID", "anthropic/claude-sonnet-4-20250514")


def build_voice_profile(bundle_dir):
    """Build an LLM-generated voice profile from creator content."""
    bundle_dir = Path(bundle_dir)

    chunks = json.loads((bundle_dir / "chunks.json").read_text(encoding="utf-8"))
    sources = json.loads((bundle_dir / "sources.json").read_text(encoding="utf-8"))
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))

    if not chunks:
        print("No chunks to analyze for voice profile")
        return

    # Recency-weighted sampling: recent content counts ~5x more
    sampled = _recency_weighted_sample(chunks, sources, n=25)
    content_block = "\n---\n".join(c["text"][:600] for c in sampled)

    prompt = f"""Analyze this creator's content and produce a detailed voice profile.

CREATOR: {manifest.get('channel', 'Unknown')}

CONTENT SAMPLES (weighted toward recent content):
{content_block}

Respond in JSON with these fields:
{{
  "tone": "2-3 sentence description of overall tone",
  "vocabulary_level": "simple|moderate|advanced|technical",
  "signature_phrases": ["list of 5-8 recurring phrases or verbal habits"],
  "communication_style": "2-3 sentences on how they structure arguments and explain things",
  "personality_traits": ["list of 5-7 personality traits evident in content"],
  "content_themes": ["list of 5-8 major themes they return to"],
  "audience_relationship": "how they relate to their audience",
  "unique_differentiator": "what makes their voice distinct from others in their space",
  "evolution_note": "any notable shift in recent vs older content focus"
}}

Return ONLY valid JSON, no markdown."""

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
                "max_tokens": 2000,
            },
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]

        # Clean markdown fencing if present
        if "```" in text:
            text = text.split("```json")[-1].split("```")[0] if "```json" in text else text.split("```")[1].split("```")[0]

        profile = json.loads(text.strip())
        profile["generated_at"] = __import__("datetime").datetime.utcnow().isoformat()
        profile["model"] = OPENROUTER_MODEL_ID
        profile["sample_count"] = len(sampled)

        (bundle_dir / "voice_profile.json").write_text(
            json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Voice profile built ({len(sampled)} samples)")

    except Exception as e:
        print(f"Voice profile failed: {e}")
        (bundle_dir / "voice_profile.json").write_text(
            json.dumps({"tone": "Analysis pending", "error": str(e)}, indent=2),
            encoding="utf-8",
        )


def _recency_weighted_sample(chunks, sources, n=25):
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
        vid = c.get("video_id", "")
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
