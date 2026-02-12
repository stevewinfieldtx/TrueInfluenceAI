"""
Build a voice/style profile from a creator's content bundle.
Analyzes their actual speech patterns, vocabulary, tone, catchphrases.
Saves profile to the bundle for use by chat.py.

Usage:
  py build_voice.py                          (latest bundle)
  py build_voice.py bundles/SunnyLenarduzzi_20260211_164612
"""

import sys, os, json, random
from pathlib import Path
import requests

from dotenv import load_dotenv
load_dotenv(Path(r"C:\Users\steve\Documents\.env"))
load_dotenv(Path(r"C:\Users\steve\Documents\TruePlatformAI\.env"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
ANALYSIS_MODEL = "google/gemini-2.5-flash-lite:online"
BUNDLE_DIR = Path(r"C:\Users\steve\Documents\TrueInfluenceAI\bundles")


def find_latest_bundle():
    bundles = sorted(BUNDLE_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for b in bundles:
        if (b / 'ready.flag').exists():
            return b
    return None


def load_chunks(bundle_path):
    with open(bundle_path / 'chunks.json') as f:
        return json.load(f)


def load_sources(bundle_path):
    with open(bundle_path / 'sources.json') as f:
        return json.load(f)


def sample_content(chunks, sources, num_samples=30):
    """Pull a recency-weighted sample of chunks for style analysis.
    Recent content gets 5x the sampling weight of old content,
    so the voice profile reflects who the creator is NOW."""
    from recency_utils import rank_sources_by_date, compute_recency_weight, weighted_sample
    
    if len(chunks) <= num_samples:
        return chunks
    
    # Build source rank map
    source_ranks = rank_sources_by_date(sources)
    total_sources = len(sources)
    
    # Assign recency weights to each chunk based on its source video date
    weights = []
    for c in chunks:
        rank = source_ranks.get(c.get('source_id', ''), total_sources - 1)
        weights.append(compute_recency_weight(rank, total_sources))
    
    # Weighted sampling — recent chunks much more likely to be selected
    sampled = weighted_sample(chunks, weights, num_samples)
    return sampled


def analyze_voice(chunks, sources, channel_name):
    """Use LLM to analyze the creator's speaking style.
    Heavily weights recent content to capture current voice."""
    
    samples = sample_content(chunks, sources, 30)
    sample_text = "\n\n---\n\n".join([c['text'][:500] for c in samples])
    
    prompt = f"""You are a linguistics and communication expert. Analyze the following transcript excerpts 
from {channel_name}'s YouTube videos and create a detailed voice/style profile.

TRANSCRIPT SAMPLES:
{sample_text}

Create a comprehensive voice profile covering:

1. **TONE & ENERGY**: Overall vibe (motivational? casual? authoritative? warm? etc.)
2. **VOCABULARY LEVEL**: Reading level, jargon usage, technical vs accessible
3. **SENTENCE STRUCTURE**: Short punchy? Long flowing? Mix? Fragments?
4. **SIGNATURE PHRASES**: Catchphrases, repeated expressions, verbal tics
5. **SPEAKING PATTERNS**: How they open topics, transition, emphasize points
6. **AUDIENCE RELATIONSHIP**: How they address viewers (you guys, friend, etc.)
7. **PERSUASION STYLE**: How they convince (stories? data? authority? social proof?)
8. **UNIQUE QUIRKS**: Anything distinctive about how they communicate

Then write a SYSTEM PROMPT (200-300 words) that would instruct an AI to respond 
exactly like {channel_name}. The prompt should capture their authentic voice so well 
that a fan would recognize it. Write it in second person ("You are {channel_name}...").

Format your response as JSON:
{{
  "tone": "...",
  "vocabulary_level": "...",
  "sentence_style": "...",
  "signature_phrases": ["...", "..."],
  "speaking_patterns": "...",
  "audience_relationship": "...",
  "persuasion_style": "...",
  "unique_quirks": "...",
  "system_prompt": "..."
}}

Return ONLY valid JSON, no markdown fences."""

    resp = requests.post(
        'https://openrouter.ai/api/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {OPENROUTER_API_KEY}',
            'Content-Type': 'application/json',
        },
        json={
            'model': ANALYSIS_MODEL,
            'messages': [{"role": "user", "content": prompt}],
            'max_tokens': 2000,
            'temperature': 0.3,
        },
        timeout=120
    )
    
    if resp.status_code != 200:
        print(f"❌ API error: {resp.status_code} - {resp.text[:200]}")
        return None
    
    text = resp.json()['choices'][0]['message']['content'].strip()
    
    # Clean markdown fences if present
    if text.startswith('```'):
        text = text.split('\n', 1)[1]
    if text.endswith('```'):
        text = text.rsplit('```', 1)[0]
    text = text.strip()
    
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        print(f"⚠️ Couldn't parse JSON, saving raw analysis")
        return {"raw_analysis": text, "system_prompt": ""}


def main():
    if len(sys.argv) > 1:
        bundle_path = Path(sys.argv[1])
        if not bundle_path.is_absolute():
            bundle_path = BUNDLE_DIR / bundle_path
    else:
        bundle_path = find_latest_bundle()
    
    if not bundle_path or not bundle_path.exists():
        print("❌ No bundle found.")
        sys.exit(1)
    
    manifest = json.loads((bundle_path / 'manifest.json').read_text())
    channel = manifest.get('channel', 'Unknown')
    
    print(f"🎤 Building voice profile for: {channel}")
    print(f"   Bundle: {bundle_path.name}")
    
    chunks = load_chunks(bundle_path)
    sources = load_sources(bundle_path)
    print(f"   Analyzing {len(chunks)} chunks (recency-weighted)...")
    
    profile = analyze_voice(chunks, sources, channel)
    
    if profile:
        # Save to bundle
        with open(bundle_path / 'voice_profile.json', 'w') as f:
            json.dump(profile, f, indent=2)
        
        print(f"\n✅ Voice profile saved!")
        print(f"\n--- PROFILE ---")
        print(f"Tone: {profile.get('tone', 'N/A')}")
        print(f"Vocabulary: {profile.get('vocabulary_level', 'N/A')}")
        print(f"Sentence style: {profile.get('sentence_style', 'N/A')}")
        phrases = profile.get('signature_phrases', [])
        if phrases:
            print(f"Signature phrases: {', '.join(phrases[:5])}")
        print(f"\n--- SYSTEM PROMPT ---")
        print(profile.get('system_prompt', 'N/A'))
    else:
        print("❌ Failed to build profile.")


if __name__ == '__main__':
    main()
