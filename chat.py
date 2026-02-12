"""
TrueInfluenceAI - Chat with a Creator's Content
=================================================
Loads a bundle, searches by semantic similarity, asks OpenRouter for answers.

Usage:
  py chat.py                          (auto-picks latest bundle)
  py chat.py bundles/SunnyLenarduzzi_20260211_164612
"""

import sys, os, json, time
import numpy as np
import requests
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(r"C:\Users\steve\Documents\.env"))
load_dotenv(Path(r"C:\Users\steve\Documents\TruePlatformAI\.env"))

from recency import recency_weight

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen/qwen3-embedding-8b")
CHAT_MODEL = os.getenv("OPENROUTER_MODEL_ID", "google/gemini-2.5-flash-lite:online")
BUNDLE_DIR = Path(r"C:\Users\steve\Documents\TrueInfluenceAI\bundles")


def load_bundle(bundle_path):
    """Load a bundle into memory."""
    bundle_path = Path(bundle_path)
    
    with open(bundle_path / 'manifest.json') as f:
        manifest = json.load(f)
    
    with open(bundle_path / 'sources.json') as f:
        sources = json.load(f)
    
    with open(bundle_path / 'chunks.json') as f:
        chunks = json.load(f)
    
    # Load voice profile if exists
    voice_profile = None
    voice_path = bundle_path / 'voice_profile.json'
    if voice_path.exists():
        with open(voice_path) as f:
            voice_profile = json.load(f)
    
    # Build source lookup
    source_map = {s['source_id']: s for s in sources}
    
    # Build embedding matrix for fast search
    valid_chunks = [c for c in chunks if c.get('embedding')]
    embeddings = np.array([c['embedding'] for c in valid_chunks], dtype=np.float32)
    
    # Normalize for cosine similarity
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    embeddings = embeddings / norms
    
    return {
        'manifest': manifest,
        'sources': source_map,
        'chunks': valid_chunks,
        'embeddings': embeddings,
        'channel': manifest.get('channel', 'Unknown'),
        'voice_profile': voice_profile,
    }


def embed_query(text):
    """Get embedding for a search query."""
    resp = requests.post(
        'https://openrouter.ai/api/v1/embeddings',
        headers={
            'Authorization': f'Bearer {OPENROUTER_API_KEY}',
            'Content-Type': 'application/json',
        },
        json={'model': EMBEDDING_MODEL, 'input': text[:8000]},
        timeout=30
    )
    if resp.status_code == 200:
        data = resp.json()
        if 'data' in data:
            return np.array(data['data'][0]['embedding'], dtype=np.float32)
    return None


def search(bundle, query, top_k=5):
    """Semantic search across the bundle with recency boosting."""
    q_emb = embed_query(query)
    if q_emb is None:
        return []
    
    # Normalize query
    q_norm = np.linalg.norm(q_emb)
    if q_norm > 0:
        q_emb = q_emb / q_norm
    
    # Cosine similarity
    raw_scores = bundle['embeddings'] @ q_emb
    
    # Apply recency weighting: recent content gets boosted
    boosted_scores = np.copy(raw_scores)
    for i, chunk in enumerate(bundle['chunks']):
        source = bundle['sources'].get(chunk['source_id'], {})
        pub = source.get('published_at', '')
        weight = recency_weight(pub)
        boosted_scores[i] = raw_scores[i] * weight
    
    top_indices = np.argsort(boosted_scores)[-top_k:][::-1]
    
    results = []
    for idx in top_indices:
        chunk = bundle['chunks'][idx]
        source = bundle['sources'].get(chunk['source_id'], {})
        # Build URL with timestamp if available
        url = source.get('url', '')
        start = chunk.get('start_time')
        if not start:
            seg_start = chunk.get('segments', [{}])[0].get('start') if chunk.get('segments') else None
            start = seg_start
        if start and url:
            url = f"{url}&t={int(start)}s"
        results.append({
            'text': chunk['text'],
            'score': float(boosted_scores[idx]),
            'raw_score': float(raw_scores[idx]),
            'recency_weight': recency_weight(source.get('published_at', '')),
            'title': source.get('title', 'Unknown'),
            'url': url,
            'source_id': chunk['source_id'],
            'published_at': source.get('published_at', ''),
        })
    
    return results


def ask(bundle, question, history=None):
    """Ask a question about the creator's content."""
    results = search(bundle, question, top_k=5)
    
    if not results:
        return "No relevant content found.", []
    
    # Build context - summarize key points, don't dump raw transcript
    context_parts = []
    for i, r in enumerate(results):
        context_parts.append(f"VIDEO {i+1}: \"{r['title']}\"\nKEY POINTS FROM THIS SECTION: {r['text'][:400]}")
    
    context = "\n\n".join(context_parts)
    
    # Use voice profile for tone, but never impersonate or parrot
    voice = bundle.get('voice_profile')
    voice_guidance = ""
    if voice:
        tone = voice.get('tone', '')
        vocab = voice.get('vocabulary_level', '')
        style = voice.get('sentence_style', '')
        audience = voice.get('audience_relationship', '')
        if any([tone, vocab, style, audience]):
            voice_guidance = f"""\n\nSTYLE GUIDANCE (inspired by {bundle['channel']}'s communication style):
- Tone: {tone}
- Vocabulary: {vocab}
- Sentence style: {style}
- Audience approach: {audience}
Use this style guidance to inform your TONE and WARMTH, not to impersonate."""
    
    system_msg = f"""You ARE {bundle['channel']}. Respond in first person as if you are the creator speaking directly to a fan or follower.

RULES:
1. Restate your ideas in fresh words — never repeat your transcript word-for-word.
2. Never fabricate calls-to-action, links, comment prompts, or offers you didn't actually make. If you mentioned a resource in a video, just say "I talk more about that in my video [title]."
3. End each response with 1-3 concrete next steps the user can take right now.
4. Keep it warm, direct, and actionable — the way you talk to your audience.{voice_guidance}"""
    
    messages = [{"role": "system", "content": system_msg}]
    
    # Add conversation history
    if history:
        for h in history[-6:]:  # Last 3 exchanges
            messages.append(h)
    
    messages.append({
        "role": "user",
        "content": f"""Below are REFERENCE NOTES from {bundle['channel']}'s videos. 
Do NOT copy this text. Synthesize the ideas into your OWN words.
Do NOT generate any calls-to-action, offers, or "comment below" type language.

REFERENCE NOTES:
{context}

USER QUESTION: {question}

Remember: Answer in your own words. Give 1-3 actionable next steps. Never copy the source text."""
    })
    
    resp = requests.post(
        'https://openrouter.ai/api/v1/chat/completions',
        headers={
            'Authorization': f'Bearer {OPENROUTER_API_KEY}',
            'Content-Type': 'application/json',
        },
        json={
            'model': CHAT_MODEL,
            'messages': messages,
            'max_tokens': 1000,
            'temperature': 0.3,
        },
        timeout=60
    )
    
    if resp.status_code == 200:
        answer = resp.json()['choices'][0]['message']['content']
        return answer, results
    else:
        return f"API error: {resp.status_code} - {resp.text[:200]}", results


def find_latest_bundle():
    """Find the most recent bundle."""
    bundles = sorted(BUNDLE_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for b in bundles:
        if (b / 'ready.flag').exists():
            return b
    return None


def main():
    # Find bundle
    if len(sys.argv) > 1:
        bundle_path = Path(sys.argv[1])
        if not bundle_path.is_absolute():
            bundle_path = BUNDLE_DIR / bundle_path
    else:
        bundle_path = find_latest_bundle()
    
    if not bundle_path or not bundle_path.exists():
        print("❌ No bundle found. Run fast_ingest.py first.")
        sys.exit(1)
    
    # Load
    print(f"📦 Loading bundle: {bundle_path.name}")
    bundle = load_bundle(bundle_path)
    print(f"   {bundle['manifest']['total_videos']} videos, {len(bundle['chunks'])} chunks")
    print(f"   Channel: {bundle['channel']}")
    if bundle.get('voice_profile'):
        print(f"   Voice: ✅ {bundle['channel']}'s style loaded")
    else:
        print(f"   Voice: ❌ Generic (run build_voice.py to clone their style)")
    print(f"\n💬 Chat with {bundle['channel']}'s content (type 'quit' to exit)\n")
    
    history = []
    
    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        
        if not question:
            continue
        if question.lower() in ('quit', 'exit', 'q'):
            break
        
        answer, sources = ask(bundle, question, history)
        
        print(f"\n{answer}")
        
        # Show source videos as the creator would reference them
        seen = set()
        source_list = []
        for s in sources:
            if s['title'] not in seen:
                seen.add(s['title'])
                source_list.append(s)
        
        if source_list:
            print(f"\n   Here are some places where I talked about this:")
            for s in source_list[:3]:
                # Extract timestamp from URL for display
                ts = ''
                if '&t=' in s['url']:
                    secs = int(s['url'].split('&t=')[1].replace('s',''))
                    mins, sec = divmod(secs, 60)
                    ts = f" @ {mins}:{sec:02d}"
                print(f"      • {s['title']}{ts}")
                print(f"        {s['url']}")
        
        print()
        
        # Track history
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})


if __name__ == '__main__':
    main()
