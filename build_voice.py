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

# Fix Windows encoding for emoji in print statements
if sys.stdout.encoding and sys.stdout.encoding.lower() not in ('utf-8', 'utf8'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv(Path(r"C:\Users\steve\Documents\.env"))
load_dotenv(Path(r"C:\Users\steve\Documents\TruePlatformAI\.env"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
ANALYSIS_MODEL = "google/gemini-2.5-flash-lite:online"
VOICE_MODEL = "anthropic/claude-sonnet-4"  # Stronger model for voice/tone — one-time cost per creator
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
    
    # Use 35 samples at 500 chars — enough for great analysis without hanging
    samples = sample_content(chunks, sources, 35)
    sample_text = "\n\n---\n\n".join([c['text'][:500] for c in samples])
    
    prompt = f"""You are a world-class forensic linguist and ghostwriter. Your job is to dissect {channel_name}'s 
communication DNA so precisely that content written from your analysis would be indistinguishable 
from {channel_name}'s own words to their most dedicated fans.

TRANSCRIPT SAMPLES (recency-weighted — more recent content sampled more heavily):
{sample_text}

Analyze at THREE levels of depth:

=== LEVEL 1: MACRO VOICE (overall impression) ===
1. **TONE & ENERGY**: Not just "motivational" — describe the specific emotional register. Are they a 
   fired-up coach? A wise friend? A no-BS mentor? What’s the ratio of encouragement to challenge?
2. **VOCABULARY LEVEL**: Reading level, jargon patterns, invented terms, borrowed terms from other fields
3. **AUDIENCE RELATIONSHIP**: How do they address viewers? What power dynamic exists? Peer, mentor, 
   guru, friend, older sibling? Do they use "you" vs "we" vs "I"?

=== LEVEL 2: STRUCTURAL DNA (how they build arguments) ===
4. **OPENING PATTERNS**: How do they start a topic? Myth-bust? Personal story? Bold claim? Question? 
   Identify their top 2-3 opening moves with specific examples from the transcripts.
5. **ARGUMENT ARCHITECTURE**: What’s their typical flow? (e.g., Problem → Failed solutions → Their 
   framework → Case study → Action steps). Map the actual structure they repeat.
6. **TRANSITION PATTERNS**: Exact phrases they use to shift between sections. Not generic ones — their 
   specific verbal bridges.
7. **CLOSING PATTERNS**: How do they wrap up? CTA style? Final encouragement? Challenge to the viewer?

=== LEVEL 3: MICRO PATTERNS (the fingerprints) ===
8. **SIGNATURE PHRASES**: Not just catchphrases — include verbal tics, filler patterns, emphasis words 
   they overuse ("literally", "actually", "here’s the thing"), and phrases that signal transitions.
9. **SENTENCE RHYTHM**: Map the actual short-long-short pattern. Do they use fragments for emphasis? 
   Do they stack rhetorical questions? Do they use lists of three?
10. **PERSUASION FINGERPRINT**: What’s their specific evidence style? Client stories with exact numbers? 
    Personal vulnerability? Contrarian reframes? Authority citations? Rank their persuasion tools.
11. **UNIQUE QUIRKS**: Anything that’s distinctly THEM — humor style, metaphor preferences, topics they 
    always circle back to, emotional beats they hit repeatedly.
12. **WHAT THEY NEVER DO**: Equally important — what’s absent from their style? (e.g., never uses 
    academic citations, never swears, never gets deeply personal about family, etc.)

Then write TWO system prompts:

a) **system_prompt** (300-400 words): A comprehensive prompt that instructs an AI to write long-form 
   content (scripts, articles, emails) indistinguishable from {channel_name}. Include specific 
   structural rules, phrase examples, and anti-patterns (what NOT to do).

b) **system_prompt_short** (150 words): A condensed version for quick social media posts, comments, 
   and short replies that still sound authentically like {channel_name}.

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

    print(f"   Using {VOICE_MODEL} for deep voice analysis...")
    resp = requests.post(
        'https://openrouter.ai/api/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {OPENROUTER_API_KEY}',
            'Content-Type': 'application/json',
        },
        json={
            'model': VOICE_MODEL,
            'messages': [{"role": "user", "content": prompt}],
            'max_tokens': 4000,
            'temperature': 0.3,
        },
        timeout=180
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
        
        print(f"\n✅ Voice profile saved! (via {VOICE_MODEL})")
        print(f"\n--- PROFILE ---")
        print(f"Tone: {profile.get('tone', 'N/A')[:200]}")
        print(f"Vocabulary: {profile.get('vocabulary_level', 'N/A')[:200]}")
        print(f"Sentence style: {profile.get('sentence_style', 'N/A')[:200]}")
        phrases = profile.get('signature_phrases', [])
        if phrases:
            print(f"Signature phrases: {', '.join(str(p) for p in phrases[:5])}")
        transitions = profile.get('transition_phrases', [])
        if transitions:
            print(f"Transitions: {', '.join(str(t) for t in transitions[:5])}")
        print(f"Opening patterns: {profile.get('opening_patterns', 'N/A')[:200]}")
        print(f"Argument structure: {profile.get('argument_architecture', 'N/A')[:200]}")
        print(f"What they NEVER do: {profile.get('what_they_never_do', 'N/A')[:200]}")
        print(f"\n--- SYSTEM PROMPT (long-form) ---")
        print(profile.get('system_prompt', 'N/A'))
        print(f"\n--- SYSTEM PROMPT (short) ---")
        print(profile.get('system_prompt_short', 'N/A'))
    else:
        print("❌ Failed to build profile.")


if __name__ == '__main__':
    main()
