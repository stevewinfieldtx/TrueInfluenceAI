"""
TrueInfluenceAI - Fast Channel Ingestion (POC)
================================================
Ingests an entire YouTube channel in MINUTES, not days.

NO audio download. NO Whisper. Just:
  1. scrapetube -> list all videos (no API key needed)
  2. yt-dlp -> pull subtitle files only (no audio, handles rate limits)
  3. OpenRouter -> embed chunks
  4. Save bundle -> ready for platform

Usage:
  py fast_ingest.py https://www.youtube.com/@SunnyLenarduzzi
  py fast_ingest.py https://www.youtube.com/@SunnyLenarduzzi --max 20
"""

import sys, os, json, time, re, subprocess, shutil, tempfile
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, r"C:\Users\steve\Documents\TruePlatformAI")

from dotenv import load_dotenv
load_dotenv(Path(r"C:\Users\steve\Documents\.env"))
load_dotenv(Path(r"C:\Users\steve\Documents\TruePlatformAI\.env"))

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen/qwen3-embedding-8b")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
BUNDLE_DIR = Path(r"C:\Users\steve\Documents\TrueInfluenceAI\bundles")

import requests


# ─── Step 1: List channel videos via scrapetube ──────────────────────

def get_channel_videos(channel_url, max_videos=100):
    """Get video IDs from a channel. Fast, no API key needed."""
    import scrapetube
    print(f"\n📡 Scanning channel: {channel_url}")
    
    videos = scrapetube.get_channel(channel_url=channel_url, limit=max_videos, sort_by="newest")
    
    results = []
    for v in videos:
        vid = v.get('videoId', '')
        if not vid:
            continue
        title = v.get('title', {})
        if isinstance(title, dict):
            title = title.get('runs', [{}])[0].get('text', '') if title.get('runs') else title.get('simpleText', '')
        
        dur_text = ''
        lt = v.get('lengthText', {})
        if isinstance(lt, dict):
            dur_text = lt.get('simpleText', '')
        
        # View count
        view_text = v.get('viewCountText', {})
        if isinstance(view_text, dict):
            view_str = view_text.get('simpleText', '0')
        else:
            view_str = str(view_text) if view_text else '0'
        views = 0
        try:
            views = int(view_str.replace(',', '').replace(' views', '').replace(' view', '').strip())
        except (ValueError, AttributeError):
            pass
        
        # Publish date
        pub_text = v.get('publishedTimeText', {})
        if isinstance(pub_text, dict):
            pub_text = pub_text.get('simpleText', '')
        else:
            pub_text = str(pub_text) if pub_text else ''
        
        results.append({
            'video_id': vid,
            'title': title or f'Video {vid}',
            'duration_text': dur_text,
            'url': f'https://www.youtube.com/watch?v={vid}',
            'views': views,
            'published_text': pub_text,
            'position': len(results),  # 0 = newest
        })
        
        if len(results) % 10 == 0:
            print(f"  Found {len(results)} videos...")
    
    print(f"  ✅ Found {len(results)} videos total")
    return results


# ─── Step 2: Pull subtitles via yt-dlp (no audio, handles blocks) ───

def get_transcript(video_id):
    """Get captions via yt-dlp subtitle extraction. No audio download."""
    tmp_dir = tempfile.mkdtemp()
    out_template = os.path.join(tmp_dir, '%(id)s')
    
    try:
        cmd = [
            'yt-dlp',
            '--skip-download',
            '--write-auto-sub',
            '--write-sub',
            '--sub-lang', 'en',
            '--sub-format', 'json3',
            '--no-warnings',
            '--quiet',
            '-o', out_template,
            f'https://www.youtube.com/watch?v={video_id}'
        ]
        subprocess.run(cmd, capture_output=True, timeout=30)
        
        # Find subtitle file
        sub_file = None
        for f in os.listdir(tmp_dir):
            if f.endswith('.json3'):
                sub_file = os.path.join(tmp_dir, f)
                break
        
        if not sub_file:
            # Retry with vtt format
            cmd2 = cmd.copy()
            cmd2[9] = 'vtt'
            subprocess.run(cmd2, capture_output=True, timeout=30)
            for f in os.listdir(tmp_dir):
                if f.endswith('.vtt'):
                    sub_file = os.path.join(tmp_dir, f)
                    break
        
        if not sub_file:
            return None
        
        with open(sub_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        segments = []
        
        if sub_file.endswith('.json3'):
            data = json.loads(content)
            events = data.get('events', [])
            for ev in events:
                segs = ev.get('segs', [])
                text = ''.join(s.get('utf8', '') for s in segs).strip()
                if not text or text == '\n':
                    continue
                start_ms = ev.get('tStartMs', 0)
                dur_ms = ev.get('dDurationMs', 0)
                segments.append({
                    'start': start_ms / 1000.0,
                    'end': (start_ms + dur_ms) / 1000.0,
                    'text': text.replace('\n', ' '),
                })
        else:
            # Parse VTT
            blocks = content.split('\n\n')
            for block in blocks:
                lines = block.strip().split('\n')
                if len(lines) >= 2 and '-->' in lines[0]:
                    time_line = lines[0]
                    text = ' '.join(lines[1:]).strip()
                    text = re.sub(r'<[^>]+>', '', text)
                    if not text:
                        continue
                    parts = time_line.split(' --> ')
                    start = _parse_vtt_time(parts[0].strip())
                    end = _parse_vtt_time(parts[1].strip().split(' ')[0])
                    segments.append({'start': start, 'end': end, 'text': text})
        
        if not segments:
            return None
        
        full_text = ' '.join(s['text'] for s in segments)
        return {'text': full_text, 'segments': segments, 'word_count': len(full_text.split())}
    
    except Exception as e:
        get_transcript._fail_count = getattr(get_transcript, '_fail_count', 0) + 1
        if get_transcript._fail_count <= 5:
            print(f"  ⚠️ {video_id}: {type(e).__name__}: {str(e)[:80]}")
        return None
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _parse_vtt_time(t):
    """Parse VTT timestamp like 00:01:23.456 to seconds."""
    parts = t.replace(',', '.').split(':')
    if len(parts) == 3:
        return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    elif len(parts) == 2:
        return float(parts[0]) * 60 + float(parts[1])
    return 0.0


def batch_get_transcripts(videos, max_workers=5):
    """Pull subtitles in parallel batches."""
    print(f"\n📝 Pulling subtitles for {len(videos)} videos ({max_workers} parallel)...")
    
    results = {}
    failed = []
    
    batch_size = 50
    for batch_start in range(0, len(videos), batch_size):
        batch = videos[batch_start:batch_start + batch_size]
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(get_transcript, v['video_id']): v for v in batch}
            for future in as_completed(futures):
                video = futures[future]
                transcript = future.result()
                if transcript:
                    results[video['video_id']] = transcript
                else:
                    failed.append(video['video_id'])
        
        done = min(batch_start + batch_size, len(videos))
        print(f"  {done}/{len(videos)} - {len(results)} with captions")
    
    print(f"  ✅ Got captions: {len(results)}/{len(videos)} ({len(failed)} no captions)")
    return results, failed


# ─── Step 3: Chunk with timestamps ───────────────────────────────────

def chunk_transcript(segments, source_id, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split transcript into overlapping chunks with timestamps."""
    words_with_time = []
    for seg in segments:
        seg_words = seg['text'].split()
        if not seg_words:
            continue
        seg_duration = seg['end'] - seg['start']
        word_dur = seg_duration / len(seg_words) if seg_words else 0
        for i, word in enumerate(seg_words):
            words_with_time.append({
                'word': word,
                'time': seg['start'] + (i * word_dur)
            })
    
    if not words_with_time:
        return []
    
    chunks = []
    i = 0
    idx = 0
    while i < len(words_with_time):
        end = min(i + chunk_size, len(words_with_time))
        chunk_words = words_with_time[i:end]
        text = ' '.join(w['word'] for w in chunk_words)
        chunks.append({
            'chunk_id': f"{source_id}_c{idx:04d}",
            'source_id': source_id,
            'text': text,
            'chunk_index': idx,
            'word_count': end - i,
            'start_time': chunk_words[0]['time'],
            'end_time': chunk_words[-1]['time'],
        })
        idx += 1
        i += chunk_size - overlap
    
    return chunks


# ─── Step 4: Embed via OpenRouter ────────────────────────────────────

def embed_chunks_parallel(all_chunks, max_workers=5):
    """Embed all chunks with parallel workers."""
    print(f"\n🔢 Embedding {len(all_chunks)} chunks...")
    start = time.time()
    
    def _embed_one(chunk):
        try:
            resp = requests.post(
                'https://openrouter.ai/api/v1/embeddings',
                headers={
                    'Authorization': f'Bearer {OPENROUTER_API_KEY}',
                    'Content-Type': 'application/json',
                },
                json={'model': EMBEDDING_MODEL, 'input': chunk['text'][:8000]},
                timeout=30
            )
            if resp.status_code == 200:
                data = resp.json()
                if 'data' in data:
                    chunk['embedding'] = data['data'][0]['embedding']
                    return chunk
            chunk['embedding'] = []
            return chunk
        except Exception:
            chunk['embedding'] = []
            return chunk
    
    done = 0
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_embed_one, c): c for c in all_chunks}
        for future in as_completed(futures):
            result = future.result()
            done += 1
            if done % 25 == 0 or done == len(all_chunks):
                elapsed = time.time() - start
                rate = done / elapsed if elapsed > 0 else 0
                print(f"  {done}/{len(all_chunks)} embedded ({rate:.1f}/sec)")
    
    embedded = sum(1 for c in all_chunks if c.get('embedding'))
    print(f"  ✅ {embedded}/{len(all_chunks)} embedded in {time.time()-start:.1f}s")
    return all_chunks


# ─── Step 5: Save bundle ─────────────────────────────────────────────

def save_bundle(channel_name, videos, transcripts, chunks):
    """Save everything as a portable bundle."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r'[^\w\-]', '_', channel_name)
    bundle_dir = BUNDLE_DIR / f"{safe_name}_{timestamp}"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    
    manifest = {
        'channel': channel_name,
        'created': datetime.now().isoformat(),
        'total_videos': len(videos),
        'videos_with_captions': len(transcripts),
        'total_chunks': len(chunks),
        'embedded_chunks': sum(1 for c in chunks if c.get('embedding')),
        'embedding_model': EMBEDDING_MODEL,
    }
    
    with open(bundle_dir / 'manifest.json', 'w') as f:
        json.dump(manifest, f, indent=2)
    
    sources = []
    for v in videos:
        t = transcripts.get(v['video_id'], {})
        sources.append({
            'source_id': v['video_id'],
            'source_type': 'youtube',
            'url': v['url'],
            'title': v['title'],
            'duration_text': v.get('duration_text', ''),
            'has_transcript': v['video_id'] in transcripts,
            'word_count': t.get('word_count', 0),
            'views': v.get('views', 0),
            'published_text': v.get('published_text', ''),
            'position': v.get('position', 0),
        })
    
    with open(bundle_dir / 'sources.json', 'w') as f:
        json.dump(sources, f, indent=2)
    
    with open(bundle_dir / 'chunks.json', 'w') as f:
        json.dump(chunks, f)
    
    (bundle_dir / 'ready.flag').write_text('ready')
    
    print(f"\n📦 Bundle saved: {bundle_dir}")
    print(f"   {manifest['total_videos']} videos, {manifest['videos_with_captions']} transcribed, {manifest['total_chunks']} chunks")
    return bundle_dir


# ─── Main ─────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: py fast_ingest.py <channel_url> [--max N]")
        sys.exit(1)
    
    channel_url = sys.argv[1]
    max_videos = 100
    if '--max' in sys.argv:
        idx = sys.argv.index('--max')
        max_videos = int(sys.argv[idx + 1])
    
    total_start = time.time()
    channel_name = channel_url.split('/@')[-1].split('/')[0] if '/@' in channel_url else 'channel'
    
    print(f"🚀 TrueInfluenceAI Fast Ingest")
    print(f"   Channel: {channel_name}")
    print(f"   Max videos: {max_videos}")
    print(f"   Embedding: {EMBEDDING_MODEL}")
    print(f"   API Key: {'✅ Set' if OPENROUTER_API_KEY else '❌ Missing'}")
    
    # Step 1: List videos
    t1 = time.time()
    videos = get_channel_videos(channel_url, max_videos)
    if not videos:
        print("❌ No videos found.")
        sys.exit(1)
    
    # Step 2: Pull subtitles
    transcripts, failed = batch_get_transcripts(videos)
    if not transcripts:
        print("❌ No transcripts found.")
        sys.exit(1)
    
    # Step 3: Chunk
    t3 = time.time()
    all_chunks = []
    for vid, transcript in transcripts.items():
        chunks = chunk_transcript(transcript['segments'], vid)
        all_chunks.extend(chunks)
    print(f"\n✂️ Chunked: {len(all_chunks)} chunks from {len(transcripts)} videos ({time.time()-t3:.1f}s)")
    
    # Step 4: Embed
    all_chunks = embed_chunks_parallel(all_chunks, max_workers=5)
    
    # Step 5: Save
    bundle_dir = save_bundle(channel_name, videos, transcripts, all_chunks)
    
    total_time = time.time() - total_start
    print(f"\n🏁 DONE in {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"   {len(videos)} videos scanned")
    print(f"   {len(transcripts)} transcripts pulled")
    print(f"   {len(all_chunks)} chunks embedded")
    
    if failed:
        print(f"   ⚠️ {len(failed)} videos had no captions")


if __name__ == '__main__':
    main()
