"""
TrueInfluenceAI - Cloud Ingest Pipeline
==========================================
Cloud-ready version of fast_ingest.py.
Runs inside Railway container.

Steps:
  1. scrapetube -> list channel videos
  2. yt-dlp (primary) / youtube-transcript-api (fallback) -> pull captions
  3. Chunk transcripts
  4. Embed via OpenRouter
  5. Save bundle (sources.json, chunks.json, manifest.json)
"""

import os, json, time, re, subprocess, tempfile
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
import scrapetube

try:
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.proxies import WebshareProxyConfig
    HAS_YT_TRANSCRIPT_API = True
    print("   youtube-transcript-api: loaded OK")
except ImportError:
    HAS_YT_TRANSCRIPT_API = False
    WebshareProxyConfig = None
    print("   youtube-transcript-api: NOT INSTALLED - fallback disabled")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen/qwen3-embedding-8b")
WEBSHARE_PROXY_USERNAME = os.getenv("WEBSHARE_PROXY_USERNAME", "")
WEBSHARE_PROXY_PASSWORD = os.getenv("WEBSHARE_PROXY_PASSWORD", "")
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50


# --- Step 1: List channel videos ---

def get_channel_videos(channel_url, max_videos=100):
    """Get video metadata from a channel via scrapetube (no API key)."""
    print(f"Scanning channel: {channel_url}")

    videos = scrapetube.get_channel(channel_url=channel_url, limit=max_videos, sort_by="newest")

    results = []
    for v in videos:
        vid = v.get("videoId", "")
        if not vid:
            continue
        title = v.get("title", {})
        if isinstance(title, dict):
            title = title.get("runs", [{}])[0].get("text", "") if title.get("runs") else title.get("simpleText", "")

        dur_text = ""
        lt = v.get("lengthText", {})
        if isinstance(lt, dict):
            dur_text = lt.get("simpleText", "")

        view_text = v.get("viewCountText", {})
        if isinstance(view_text, dict):
            view_str = view_text.get("simpleText", "0")
        else:
            view_str = str(view_text) if view_text else "0"
        views = 0
        try:
            views = int(view_str.replace(",", "").replace(" views", "").replace(" view", "").strip())
        except (ValueError, AttributeError):
            pass

        pub_text = v.get("publishedTimeText", {})
        if isinstance(pub_text, dict):
            pub_text = pub_text.get("simpleText", "")
        else:
            pub_text = str(pub_text) if pub_text else ""

        results.append({
            "video_id": vid,
            "title": title,
            "duration_text": dur_text,
            "views": views,
            "published_text": pub_text,
            "url": f"https://www.youtube.com/watch?v={vid}",
        })

    print(f"   Found {len(results)} videos")
    return results


# --- Step 2: Pull transcripts via yt-dlp (primary) + youtube-transcript-api (fallback) ---

def get_transcript_ytdlp(video_id):
    """Pull captions via yt-dlp. Original working method."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    with tempfile.TemporaryDirectory() as tmpdir:
        out_tpl = os.path.join(tmpdir, "%(id)s.%(ext)s")
        cmd = [
            "yt-dlp",
            "--skip-download",
            "--write-auto-sub",
            "--write-sub",
            "--sub-lang", "en",
            "--sub-format", "json3",
            "--output", out_tpl,
            url,
        ]
        try:
            subprocess.run(cmd, capture_output=True, timeout=30, check=False)
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return None

        # Find the subtitle file
        sub_file = None
        for f in Path(tmpdir).glob("*.json3"):
            sub_file = f
            break
        if not sub_file:
            for f in Path(tmpdir).glob("*.vtt"):
                sub_file = f
                break

        if not sub_file:
            return None

        try:
            raw = json.loads(sub_file.read_text(encoding="utf-8"))
            events = raw.get("events", [])
            segments = []
            for ev in events:
                segs = ev.get("segs", [])
                text = "".join(s.get("utf8", "") for s in segs).strip()
                if text and text != "\n":
                    start_ms = ev.get("tStartMs", 0)
                    segments.append({
                        "text": text,
                        "start": start_ms / 1000.0,
                    })
            return {"video_id": video_id, "segments": segments} if segments else None
        except Exception:
            return None


def get_transcript_api(video_id):
    """Fallback: pull captions via youtube-transcript-api v1.2+. Tries ALL available languages."""
    if not HAS_YT_TRANSCRIPT_API:
        print(f"      [API fallback] skipped - youtube-transcript-api not installed")
        return None
    try:
        if WEBSHARE_PROXY_USERNAME and WebshareProxyConfig:
            ytt = YouTubeTranscriptApi(
                proxy_config=WebshareProxyConfig(
                    proxy_username=WEBSHARE_PROXY_USERNAME,
                    proxy_password=WEBSHARE_PROXY_PASSWORD,
                )
            )
            print(f"      [API fallback] using Webshare proxy")
        else:
            ytt = YouTubeTranscriptApi()
        langs = ["en", "pt", "pt-BR", "es", "fr", "de", "it", "ja", "ko", "zh-Hans", "hi"]

        # Try fetching with our preferred languages first
        fetched = None
        try:
            fetched = ytt.fetch(video_id, languages=langs)
        except Exception as e:
            print(f"      [API fallback] preferred langs failed: {e}")

        # If that failed, list what's actually available and use those
        if not fetched:
            try:
                transcript_list = ytt.list(video_id)
                available = [t.language_code for t in transcript_list]
                print(f"      [API fallback] available langs: {available}")
                if available:
                    fetched = ytt.fetch(video_id, languages=available)
            except Exception as e:
                print(f"      [API fallback] list/fetch failed: {e}")
                return None

        if not fetched:
            print(f"      [API fallback] no transcripts found")
            return None

        segments = []
        for entry in fetched:
            text = entry.text.strip() if hasattr(entry, 'text') else str(entry.get("text", "")).strip()
            start = entry.start if hasattr(entry, 'start') else entry.get("start", 0)
            if text:
                segments.append({"text": text, "start": start})

        print(f"      [API fallback] got {len(segments)} segments")
        return {"video_id": video_id, "segments": segments} if segments else None
    except Exception as e:
        print(f"      [API fallback] unexpected error: {e}")
        return None


def get_transcript(video_id):
    """Try yt-dlp first (proven), fall back to youtube-transcript-api for non-English channels."""
    result = get_transcript_ytdlp(video_id)
    if result:
        return result
    print(f"      yt-dlp returned nothing for {video_id}, trying API fallback...")
    return get_transcript_api(video_id)


def batch_get_transcripts(videos, max_workers=4):
    """Pull transcripts for multiple videos in parallel."""
    print(f"Pulling transcripts for {len(videos)} videos...")
    transcripts = {}
    failed = []

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(get_transcript, v["video_id"]): v for v in videos}
        for i, fut in enumerate(as_completed(futures)):
            v = futures[fut]
            try:
                result = fut.result()
                if result:
                    transcripts[v["video_id"]] = result
                    print(f"   [{i+1}/{len(videos)}] OK: {v['title'][:50]}")
                else:
                    failed.append(v["video_id"])
                    print(f"   [{i+1}/{len(videos)}] No captions: {v['title'][:50]}")
            except Exception as e:
                failed.append(v["video_id"])
                print(f"   [{i+1}/{len(videos)}] Error: {v['title'][:50]} - {e}")

    print(f"   Transcripts: {len(transcripts)}/{len(videos)} ({len(failed)} failed)")
    return transcripts, failed


# --- Step 3: Chunk ---

def chunk_transcript(segments, video_id):
    """Split transcript segments into overlapping chunks."""
    full_text = " ".join(s["text"] for s in segments)
    words = full_text.split()
    chunks = []
    idx = 0
    chunk_num = 0

    while idx < len(words):
        chunk_words = words[idx:idx + CHUNK_SIZE]
        text = " ".join(chunk_words)

        # Find approximate timestamp
        char_pos = len(" ".join(words[:idx]))
        timestamp = 0
        running = 0
        for seg in segments:
            running += len(seg["text"]) + 1
            if running >= char_pos:
                timestamp = seg.get("start", 0)
                break

        chunks.append({
            "chunk_id": f"{video_id}_c{chunk_num}",
            "video_id": video_id,
            "text": text,
            "timestamp": timestamp,
            "word_count": len(chunk_words),
        })
        chunk_num += 1
        idx += CHUNK_SIZE - CHUNK_OVERLAP

    return chunks


# --- Step 4: Embed ---

def embed_batch(texts, batch_id=0):
    """Embed a batch of texts via OpenRouter."""
    resp = requests.post(
        "https://openrouter.ai/api/v1/embeddings",
        headers={
            "Authorization": f"Bearer {OPENROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        json={"model": EMBEDDING_MODEL, "input": texts},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return [item["embedding"] for item in data["data"]]


def embed_chunks(chunks, batch_size=20):
    """Embed all chunks in batches."""
    print(f"Embedding {len(chunks)} chunks...")
    for i in range(0, len(chunks), batch_size):
        batch = chunks[i:i + batch_size]
        texts = [c["text"] for c in batch]
        try:
            embeddings = embed_batch(texts, i // batch_size)
            for c, emb in zip(batch, embeddings):
                c["embedding"] = emb
            print(f"   Embedded batch {i // batch_size + 1}/{(len(chunks) + batch_size - 1) // batch_size}")
        except Exception as e:
            print(f"   Batch {i // batch_size + 1} failed: {e}")
            for c in batch:
                c["embedding"] = []
    return chunks


# --- Step 5: Save Bundle ---

def save_bundle(slug, channel_name, videos, transcripts, chunks, bundle_dir):
    """Save all data to bundle directory."""
    # Sources
    sources = []
    for v in videos:
        vid = v["video_id"]
        has_transcript = vid in transcripts
        seg_count = len(transcripts[vid]["segments"]) if has_transcript else 0
        sources.append({
            "source_id": vid,
            "platform": "youtube",
            "url": v["url"],
            "title": v["title"],
            "duration_text": v.get("duration_text", ""),
            "views": v.get("views", 0),
            "published_text": v.get("published_text", ""),
            "has_transcript": has_transcript,
            "segment_count": seg_count,
        })

    (bundle_dir / "sources.json").write_text(
        json.dumps(sources, indent=2), encoding="utf-8"
    )

    # Chunks (without embeddings for readability, embeddings in separate field)
    chunks_out = []
    for c in chunks:
        chunks_out.append({
            "chunk_id": c["chunk_id"],
            "video_id": c["video_id"],
            "text": c["text"],
            "timestamp": c["timestamp"],
            "word_count": c["word_count"],
            "embedding": c.get("embedding", []),
        })

    (bundle_dir / "chunks.json").write_text(
        json.dumps(chunks_out, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Manifest
    manifest = {
        "slug": slug,
        "channel": channel_name,
        "created_at": datetime.utcnow().isoformat(),
        "total_videos": len(videos),
        "transcribed_videos": len(transcripts),
        "total_chunks": len(chunks),
        "embedding_model": EMBEDDING_MODEL,
        "pipeline_version": "2.0-cloud",
    }
    (bundle_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )

    # Ready flag
    (bundle_dir / "ready.flag").write_text(
        datetime.utcnow().isoformat(), encoding="utf-8"
    )

    print(f"Bundle saved: {bundle_dir}")
    return manifest


# --- Main Entry Point ---

def ingest_channel(channel_url, slug, creator_name, max_videos, bundle_dir):
    """
    Full ingest pipeline. Called by server.py as a background task.
    Returns dict with stats.
    """
    print(f"\n{'='*60}")
    print(f"  Ingesting: {creator_name or slug}")
    print(f"  Channel: {channel_url}")
    print(f"  Max videos: {max_videos}")
    print(f"{'='*60}")

    # Step 1: List videos
    videos = get_channel_videos(channel_url, max_videos)
    if not videos:
        raise ValueError(f"No videos found for {channel_url}")

    # Step 2: Pull transcripts
    transcripts, failed = batch_get_transcripts(videos)
    if not transcripts:
        raise ValueError(
            f"No transcripts available for {channel_url}. "
            f"Tried {len(videos)} videos across multiple languages (en, pt, es, fr, etc). "
            f"The channel may have captions disabled."
        )

    # Log detected languages
    langs_found = set(t.get("lang", "unknown") for t in transcripts.values())
    print(f"Languages detected: {', '.join(langs_found)}")

    # Step 3: Chunk
    all_chunks = []
    for vid, transcript in transcripts.items():
        chunks = chunk_transcript(transcript["segments"], vid)
        all_chunks.extend(chunks)
    print(f"Chunked: {len(all_chunks)} chunks from {len(transcripts)} videos")

    # Step 4: Embed
    all_chunks = embed_chunks(all_chunks)

    # Step 5: Save
    channel_name = creator_name or slug
    manifest = save_bundle(slug, channel_name, videos, transcripts, all_chunks, bundle_dir)

    return {
        "video_count": len(videos),
        "transcript_count": len(transcripts),
        "chunk_count": len(all_chunks),
        "failed_count": len(failed),
    }
