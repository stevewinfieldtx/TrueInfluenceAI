"""
TrueInfluenceAI - Onboarding GUI
====================================
Standalone GUI tool for ingesting influencer content.

- Point it at YouTube channels, Substack, Bluesky, Telegram, etc.
- Processes everything in background threads
- Saves results as portable "bundles" (JSON files)
- Bundles can be loaded into the vector DB later
- Run multiple instances simultaneously (one per influencer)

Usage:
    py onboard_gui.py
    py onboard_gui.py --bundle-dir C:\\path\\to\\bundles

Author: Steve Winfield / WinTech Partners
"""

import sys
import json
import uuid
import threading
import time
import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# Add parent dir for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "TruePlatformAI"))
sys.path.insert(0, str(Path(__file__).parent))

import config
from models import ContentSource, ContentChunk
from ingestors import YouTubeIngestor, convert_to_wav
from social_ingestors import (
    SubstackIngestor, BlueskyIngestor, LinkedInIngestor,
    TelegramIngestor, WhatsAppIngestor, RSSIngestor
)
from processors import Transcriber, Chunker, Embedder


# ============================================================================
# BUNDLE PROCESSOR (runs in background)
# ============================================================================

class BundleProcessor:
    """
    Processes content sources and saves results as a portable bundle.
    
    Bundle format:
        bundles/{influencer_id}_{timestamp}/
            manifest.json       # Metadata, platform counts, status
            sources.json        # All ContentSource objects
            chunks.json         # All ContentChunk objects (with embeddings)
            ready.flag          # Created when processing is complete
    """

    def __init__(self, bundle_dir: str = None):
        self.bundle_dir = Path(bundle_dir or Path(__file__).parent / "bundles")
        self.bundle_dir.mkdir(parents=True, exist_ok=True)

        # Processors
        self._chunker = Chunker()
        self._embedder = Embedder()
        self._transcriber = None  # Lazy init

        # Ingestors
        self._youtube = None  # Needs audio_dir per bundle
        self._substack = SubstackIngestor()
        self._bluesky = BlueskyIngestor()
        self._linkedin = LinkedInIngestor()
        self._telegram = TelegramIngestor()
        self._whatsapp = WhatsAppIngestor()
        self._rss = RSSIngestor()

    def create_bundle(self, influencer_id: str, name: str = "",
                      template_id: str = "creator") -> Path:
        """Create a new bundle directory."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_id = influencer_id.replace(" ", "_").lower()[:30]
        bundle_path = self.bundle_dir / f"{safe_id}_{timestamp}"
        bundle_path.mkdir(parents=True, exist_ok=True)
        (bundle_path / "audio").mkdir(exist_ok=True)

        manifest = {
            "influencer_id": influencer_id,
            "name": name or influencer_id,
            "template_id": template_id,
            "created_at": datetime.now().isoformat(),
            "status": "processing",
            "sources_count": 0,
            "chunks_count": 0,
            "platforms": {},
            "errors": [],
        }
        self._save_json(bundle_path / "manifest.json", manifest)
        self._save_json(bundle_path / "sources.json", [])
        self._save_json(bundle_path / "chunks.json", [])

        return bundle_path

    def process_youtube_videos(self, bundle_path: Path, urls: List[str],
                                callback=None) -> int:
        """Process YouTube video URLs into the bundle."""
        audio_dir = bundle_path / "audio"
        yt = YouTubeIngestor(audio_dir)
        if not self._transcriber:
            self._transcriber = Transcriber(bundle_path / "transcripts")

        count = 0
        for i, url in enumerate(urls):
            if callback:
                callback(f"[YouTube {i+1}/{len(urls)}] {url[:50]}...")
            try:
                result = self._process_single_youtube(yt, url, bundle_path)
                if result:
                    count += 1
                    if callback:
                        callback(f"  ✅ {result.get('title', '')[:40]}")
            except Exception as e:
                self._add_error(bundle_path, f"YouTube: {url} - {e}")
                if callback:
                    callback(f"  ❌ {e}")
        return count

    def _process_single_youtube(self, yt: YouTubeIngestor, url: str,
                                 bundle_path: Path) -> Optional[Dict]:
        """Process one YouTube video."""
        video_id = yt.extract_video_id(url)

        # Check if already in bundle
        sources = self._load_json(bundle_path / "sources.json") or []
        if any(s["source_id"] == video_id for s in sources):
            return None

        # Get metadata
        meta = yt.get_video_metadata(url)
        source = ContentSource(
            source_id=video_id, source_type="youtube",
            source_url=url,
            title=meta.get("title", f"Video {video_id}") if meta else f"Video {video_id}",
            author=meta.get("uploader", "") if meta else "",
            duration_seconds=meta.get("duration", 0) if meta else 0,
            published_date=meta.get("upload_date", "") if meta else "",
            metadata=meta or {},
        )

        # Try captions first
        transcript = yt.get_transcript(video_id)
        if not transcript:
            # Fall back to audio
            audio_path, dl_source = yt.download(url)
            if not audio_path:
                source.status = "error"
                self._append_source(bundle_path, source)
                return None

            wav_path = convert_to_wav(audio_path, bundle_path / "audio")
            if not wav_path:
                wav_path = audio_path

            transcript = self._transcriber.transcribe(wav_path, source.source_id)
            if not transcript:
                source.status = "error"
                self._append_source(bundle_path, source)
                return None

        # Chunk
        chunks = self._chunker.chunk_transcript(transcript, source.source_id)
        for chunk in chunks:
            chunk.published_date = source.published_date
            chunk.template_tags["platform"] = "youtube"
            chunk.template_tags["source_title"] = source.title

        # Embed
        chunks = self._embedder.embed_chunks(chunks)

        # Save
        source.status = "ready"
        source.metadata["transcript_source"] = transcript.get("source", "audio")
        self._append_source(bundle_path, source)
        self._append_chunks(bundle_path, chunks)
        self._update_manifest(bundle_path, "youtube", len(chunks))

        return source.to_dict()

    def process_youtube_channel(self, bundle_path: Path, channel_url: str,
                                 max_videos: int = 50, min_duration: int = 60,
                                 callback=None) -> int:
        """Scan a YouTube channel and process videos."""
        audio_dir = bundle_path / "audio"
        yt = YouTubeIngestor(audio_dir)

        if callback:
            callback(f"Scanning channel: {channel_url}...")

        urls = yt.get_channel_videos(channel_url, max_videos, min_duration)

        if callback:
            callback(f"Found {len(urls)} videos. Processing...")

        return self.process_youtube_videos(bundle_path, urls, callback)

    def process_substack(self, bundle_path: Path, substack_url: str,
                          max_posts: int = 50, callback=None) -> int:
        """Process Substack newsletter posts."""
        if callback:
            callback(f"Fetching Substack: {substack_url}...")

        posts = self._substack.get_posts(substack_url, max_posts)
        if callback:
            callback(f"Found {len(posts)} posts. Processing...")

        count = 0
        for i, post in enumerate(posts):
            if callback and i % 5 == 0:
                callback(f"  [{i+1}/{len(posts)}] {post.get('title', '')[:40]}")
            try:
                source = self._substack.ingest_post(post)
                n = self._process_text_source(bundle_path, source, "substack")
                if n > 0:
                    count += 1
            except Exception as e:
                self._add_error(bundle_path, f"Substack: {post.get('title', '')} - {e}")

        if callback:
            callback(f"✅ Substack: {count}/{len(posts)} posts processed")
        return count

    def process_bluesky(self, bundle_path: Path, handle: str,
                         max_posts: int = 50, callback=None) -> int:
        """Process Bluesky posts."""
        if callback:
            callback(f"Fetching Bluesky: {handle}...")

        posts = self._bluesky.get_posts(handle, max_posts)
        if callback:
            callback(f"Found {len(posts)} posts. Processing...")

        count = 0
        for post in posts:
            try:
                source = self._bluesky.ingest_post(post)
                n = self._process_text_source(bundle_path, source, "bluesky")
                if n > 0:
                    count += 1
            except Exception as e:
                self._add_error(bundle_path, f"Bluesky: {e}")

        if callback:
            callback(f"✅ Bluesky: {count}/{len(posts)} posts processed")
        return count

    def process_telegram(self, bundle_path: Path, channel_name: str,
                          max_posts: int = 50, callback=None) -> int:
        """Process Telegram public channel."""
        if callback:
            callback(f"Fetching Telegram: {channel_name}...")

        posts = self._telegram.get_channel_posts(channel_name, max_posts)
        if callback:
            callback(f"Found {len(posts)} posts. Processing...")

        count = 0
        for post in posts:
            try:
                source = self._telegram.ingest_post(post)
                n = self._process_text_source(bundle_path, source, "telegram")
                if n > 0:
                    count += 1
            except Exception as e:
                self._add_error(bundle_path, f"Telegram: {e}")

        if callback:
            callback(f"✅ Telegram: {count}/{len(posts)} posts processed")
        return count

    def process_rss(self, bundle_path: Path, feed_url: str,
                     max_posts: int = 50, callback=None) -> int:
        """Process any RSS/Atom feed."""
        if callback:
            callback(f"Fetching RSS: {feed_url}...")

        posts = self._rss.get_posts(feed_url, max_posts)
        if callback:
            callback(f"Found {len(posts)} posts. Processing...")

        count = 0
        for post in posts:
            try:
                source = self._rss.ingest_post(post)
                n = self._process_text_source(bundle_path, source, post.get("platform", "rss"))
                if n > 0:
                    count += 1
            except Exception as e:
                self._add_error(bundle_path, f"RSS: {e}")

        if callback:
            callback(f"✅ RSS: {count}/{len(posts)} posts processed")
        return count

    def process_linkedin_paste(self, bundle_path: Path, text: str,
                                author: str = "", callback=None) -> int:
        """Process pasted LinkedIn posts (separated by --- or ===)."""
        if callback:
            callback("Processing LinkedIn posts...")

        sources = self._linkedin.ingest_bulk_paste(text, author)
        count = 0
        for source in sources:
            n = self._process_text_source(bundle_path, source, "linkedin")
            if n > 0:
                count += 1

        if callback:
            callback(f"✅ LinkedIn: {count}/{len(sources)} posts processed")
        return count

    def process_whatsapp_export(self, bundle_path: Path, file_path: str,
                                 filter_sender: str = None,
                                 callback=None) -> int:
        """Process WhatsApp export file."""
        if callback:
            callback(f"Processing WhatsApp export: {file_path}...")

        sources = self._whatsapp.ingest_export(file_path, filter_sender)
        count = 0
        for source in sources:
            n = self._process_text_source(bundle_path, source, "whatsapp")
            if n > 0:
                count += 1

        if callback:
            callback(f"✅ WhatsApp: {count}/{len(sources)} messages processed")
        return count

    def process_telegram_export(self, bundle_path: Path, file_path: str,
                                 channel_name: str = "",
                                 callback=None) -> int:
        """Process Telegram JSON export file."""
        if callback:
            callback(f"Processing Telegram export: {file_path}...")

        sources = self._telegram.ingest_export(file_path, channel_name)
        count = 0
        for source in sources:
            n = self._process_text_source(bundle_path, source, "telegram")
            if n > 0:
                count += 1

        if callback:
            callback(f"✅ Telegram export: {count}/{len(sources)} messages processed")
        return count

    def finalize_bundle(self, bundle_path: Path, callback=None):
        """Mark bundle as complete."""
        manifest = self._load_json(bundle_path / "manifest.json") or {}
        manifest["status"] = "ready"
        manifest["finalized_at"] = datetime.now().isoformat()

        sources = self._load_json(bundle_path / "sources.json") or []
        chunks = self._load_json(bundle_path / "chunks.json") or []
        manifest["sources_count"] = len([s for s in sources if s.get("status") == "ready"])
        manifest["chunks_count"] = len(chunks)

        self._save_json(bundle_path / "manifest.json", manifest)

        # Write ready flag
        (bundle_path / "ready.flag").write_text(datetime.now().isoformat())

        if callback:
            callback(f"\n{'='*50}")
            callback(f"✅ BUNDLE COMPLETE: {bundle_path.name}")
            callback(f"   Sources: {manifest['sources_count']}")
            callback(f"   Chunks:  {manifest['chunks_count']}")
            callback(f"   Platforms: {manifest.get('platforms', {})}")
            callback(f"   Path: {bundle_path}")
            callback(f"{'='*50}")

    # ── Internal helpers ─────────────────────────────────────────────────

    def _process_text_source(self, bundle_path: Path,
                              source: ContentSource,
                              platform: str) -> int:
        """Process a text-based source (social post, article, etc)."""
        raw_text = source.metadata.get("raw_text", "")
        if not raw_text or len(raw_text) < 20:
            return 0

        # Check duplicate
        sources = self._load_json(bundle_path / "sources.json") or []
        if any(s["source_id"] == source.source_id for s in sources):
            return 0

        # Chunk
        chunks = self._chunker.chunk_text(raw_text, source.source_id)
        for chunk in chunks:
            chunk.published_date = source.published_date
            chunk.template_tags["platform"] = platform
            chunk.template_tags["source_title"] = source.title
            eng = source.metadata.get("engagement", {})
            if eng:
                chunk.template_tags["engagement"] = eng

        # Embed
        chunks = self._embedder.embed_chunks(chunks)

        # Save
        source.status = "ready"
        self._append_source(bundle_path, source)
        self._append_chunks(bundle_path, chunks)
        self._update_manifest(bundle_path, platform, len(chunks))

        return len(chunks)

    def _append_source(self, bundle_path: Path, source: ContentSource):
        sources = self._load_json(bundle_path / "sources.json") or []
        sources.append(source.to_dict())
        self._save_json(bundle_path / "sources.json", sources)

    def _append_chunks(self, bundle_path: Path, chunks: List[ContentChunk]):
        existing = self._load_json(bundle_path / "chunks.json") or []
        for chunk in chunks:
            existing.append(chunk.to_dict(include_embedding=True))
        self._save_json(bundle_path / "chunks.json", existing)

    def _update_manifest(self, bundle_path: Path, platform: str, chunk_count: int):
        manifest = self._load_json(bundle_path / "manifest.json") or {}
        platforms = manifest.get("platforms", {})
        platforms[platform] = platforms.get(platform, 0) + 1
        manifest["platforms"] = platforms
        manifest["chunks_count"] = manifest.get("chunks_count", 0) + chunk_count
        manifest["sources_count"] = manifest.get("sources_count", 0) + 1
        self._save_json(bundle_path / "manifest.json", manifest)

    def _add_error(self, bundle_path: Path, error: str):
        manifest = self._load_json(bundle_path / "manifest.json") or {}
        errors = manifest.get("errors", [])
        errors.append({"error": error, "at": datetime.now().isoformat()})
        manifest["errors"] = errors
        self._save_json(bundle_path / "manifest.json", manifest)

    @staticmethod
    def _save_json(path: Path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    @staticmethod
    def _load_json(path: Path):
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None


# ============================================================================
# BUNDLE LOADER (imports bundles into the platform)
# ============================================================================

class BundleLoader:
    """Load processed bundles into TruePlatformAI vector store."""

    def load_bundle(self, bundle_path: str, platform_data_dir: str = None):
        """
        Load a bundle into the platform's vector store.
        Can be called independently of the GUI.
        """
        from vector_store import VectorStore
        from models import Collection

        bundle = Path(bundle_path)
        manifest = BundleProcessor._load_json(bundle / "manifest.json")
        sources_data = BundleProcessor._load_json(bundle / "sources.json") or []
        chunks_data = BundleProcessor._load_json(bundle / "chunks.json") or []

        if not manifest:
            print(f"  ❌ No manifest found in {bundle}")
            return False

        data_dir = Path(platform_data_dir or "platform_data") / "collections"
        store = VectorStore(data_dir)

        collection_id = manifest["influencer_id"].replace(" ", "_").lower()[:30]

        # Create or get collection
        try:
            col = Collection(
                collection_id=collection_id,
                name=manifest.get("name", collection_id),
                template_id=manifest.get("template_id", "creator"),
                description=f"Loaded from bundle: {bundle.name}",
                metadata={"bundle": bundle.name, "platforms": manifest.get("platforms", {})},
            )
            store.create_collection(col)
        except Exception:
            pass  # Already exists

        # Load sources
        loaded_sources = 0
        for source_dict in sources_data:
            if source_dict.get("status") != "ready":
                continue
            source = ContentSource.from_dict(source_dict)
            store.add_source(collection_id, source)
            loaded_sources += 1

        # Load chunks grouped by source_id
        by_source = {}
        for chunk_dict in chunks_data:
            sid = chunk_dict.get("source_id", "")
            if sid not in by_source:
                by_source[sid] = []
            by_source[sid].append(chunk_dict)

        loaded_chunks = 0
        for sid, chunk_dicts in by_source.items():
            chunks = [ContentChunk.from_dict(c) for c in chunk_dicts]
            # Find matching source
            source_dict = next((s for s in sources_data if s["source_id"] == sid), {})
            store.store_chunks(collection_id, sid, chunks, source_dict)
            loaded_chunks += len(chunks)

        store.update_collection_stats(collection_id)

        print(f"  ✅ Bundle loaded: {collection_id}")
        print(f"     Sources: {loaded_sources}")
        print(f"     Chunks:  {loaded_chunks}")
        print(f"     Platforms: {manifest.get('platforms', {})}")

        return True


# ============================================================================
# GUI APPLICATION
# ============================================================================

class OnboardingGUI:
    """
    Tkinter GUI for influencer content onboarding.
    Each instance = one influencer.
    """

    def __init__(self, root: tk.Tk = None, bundle_dir: str = None):
        self.root = root or tk.Tk()
        self.root.title("TrueInfluenceAI — Onboarding")
        self.root.geometry("820x780")
        self.root.minsize(700, 600)

        self.processor = BundleProcessor(bundle_dir)
        self.bundle_path = None
        self.is_processing = False

        self._build_ui()

    def _build_ui(self):
        """Build the GUI layout."""
        style = ttk.Style()
        style.configure("Header.TLabel", font=("Segoe UI", 14, "bold"))
        style.configure("Sub.TLabel", font=("Segoe UI", 10))
        style.configure("Big.TButton", font=("Segoe UI", 11, "bold"), padding=8)

        # ── Header ───────────────────────────────────────────────────
        header = ttk.Frame(self.root, padding=10)
        header.pack(fill="x")
        ttk.Label(header, text="🚀 TrueInfluenceAI Onboarding",
                  style="Header.TLabel").pack(side="left")
        ttk.Label(header, text="Process → Bundle → Load",
                  style="Sub.TLabel").pack(side="right")

        # ── Influencer Info ──────────────────────────────────────────
        info_frame = ttk.LabelFrame(self.root, text="Influencer", padding=10)
        info_frame.pack(fill="x", padx=10, pady=5)

        row1 = ttk.Frame(info_frame)
        row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="Name:", width=12).pack(side="left")
        self.name_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.name_var, width=40).pack(side="left", padx=5)

        ttk.Label(row1, text="ID:", width=4).pack(side="left", padx=(15, 0))
        self.id_var = tk.StringVar()
        ttk.Entry(row1, textvariable=self.id_var, width=20).pack(side="left", padx=5)

        # ── Notebook (tabs for each platform) ────────────────────────
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=10, pady=5)

        # YouTube tab
        yt_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(yt_frame, text="📺 YouTube")

        ttk.Label(yt_frame, text="Channel URL (scans all videos):").pack(anchor="w")
        self.yt_channel_var = tk.StringVar()
        ch_row = ttk.Frame(yt_frame)
        ch_row.pack(fill="x", pady=2)
        ttk.Entry(ch_row, textvariable=self.yt_channel_var, width=55).pack(side="left")
        ttk.Label(ch_row, text="Max:").pack(side="left", padx=(10, 2))
        self.yt_max_var = tk.StringVar(value="30")
        ttk.Entry(ch_row, textvariable=self.yt_max_var, width=5).pack(side="left")

        ttk.Label(yt_frame, text="\nOR paste individual video URLs (one per line):").pack(anchor="w")
        self.yt_urls_text = scrolledtext.ScrolledText(yt_frame, height=6, width=70)
        self.yt_urls_text.pack(fill="x", pady=2)

        # Substack tab
        ss_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(ss_frame, text="📰 Substack")

        ttk.Label(ss_frame, text="Substack URL (e.g. username.substack.com):").pack(anchor="w")
        self.substack_var = tk.StringVar()
        ss_row = ttk.Frame(ss_frame)
        ss_row.pack(fill="x", pady=2)
        ttk.Entry(ss_row, textvariable=self.substack_var, width=55).pack(side="left")
        ttk.Label(ss_row, text="Max:").pack(side="left", padx=(10, 2))
        self.ss_max_var = tk.StringVar(value="50")
        ttk.Entry(ss_row, textvariable=self.ss_max_var, width=5).pack(side="left")

        # Bluesky tab
        bs_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(bs_frame, text="🦋 Bluesky")

        ttk.Label(bs_frame, text="Bluesky Handle (e.g. @username.bsky.social):").pack(anchor="w")
        self.bluesky_var = tk.StringVar()
        bs_row = ttk.Frame(bs_frame)
        bs_row.pack(fill="x", pady=2)
        ttk.Entry(bs_row, textvariable=self.bluesky_var, width=55).pack(side="left")
        ttk.Label(bs_row, text="Max:").pack(side="left", padx=(10, 2))
        self.bs_max_var = tk.StringVar(value="50")
        ttk.Entry(bs_row, textvariable=self.bs_max_var, width=5).pack(side="left")

        # Telegram tab
        tg_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tg_frame, text="✈️ Telegram")

        ttk.Label(tg_frame, text="Public Channel Name (e.g. @channelname):").pack(anchor="w")
        self.telegram_var = tk.StringVar()
        tg_row = ttk.Frame(tg_frame)
        tg_row.pack(fill="x", pady=2)
        ttk.Entry(tg_row, textvariable=self.telegram_var, width=55).pack(side="left")
        ttk.Label(tg_row, text="Max:").pack(side="left", padx=(10, 2))
        self.tg_max_var = tk.StringVar(value="50")
        ttk.Entry(tg_row, textvariable=self.tg_max_var, width=5).pack(side="left")

        ttk.Label(tg_frame, text="\nOR select Telegram JSON export file:").pack(anchor="w")
        tg_file_row = ttk.Frame(tg_frame)
        tg_file_row.pack(fill="x", pady=2)
        self.tg_export_var = tk.StringVar()
        ttk.Entry(tg_file_row, textvariable=self.tg_export_var, width=50).pack(side="left")
        ttk.Button(tg_file_row, text="Browse...",
                   command=self._browse_telegram_export).pack(side="left", padx=5)

        # LinkedIn tab
        li_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(li_frame, text="💼 LinkedIn")

        ttk.Label(li_frame, text="Paste LinkedIn posts (separate with --- or ===):").pack(anchor="w")
        self.linkedin_text = scrolledtext.ScrolledText(li_frame, height=10, width=70)
        self.linkedin_text.pack(fill="both", expand=True, pady=2)

        # RSS tab
        rss_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(rss_frame, text="📡 RSS/Blog")

        ttk.Label(rss_frame, text="RSS/Atom Feed URLs (one per line):").pack(anchor="w")
        self.rss_text = scrolledtext.ScrolledText(rss_frame, height=5, width=70)
        self.rss_text.pack(fill="x", pady=2)
        ttk.Label(rss_frame, text="Works with: Medium, Ghost, WordPress, newsletters, any RSS feed",
                  style="Sub.TLabel").pack(anchor="w")

        # WhatsApp tab
        wa_frame = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(wa_frame, text="💬 WhatsApp")

        ttk.Label(wa_frame, text="Select WhatsApp .txt export file:").pack(anchor="w")
        wa_row = ttk.Frame(wa_frame)
        wa_row.pack(fill="x", pady=2)
        self.wa_export_var = tk.StringVar()
        ttk.Entry(wa_row, textvariable=self.wa_export_var, width=50).pack(side="left")
        ttk.Button(wa_row, text="Browse...",
                   command=self._browse_whatsapp_export).pack(side="left", padx=5)

        ttk.Label(wa_frame, text="Filter by sender (optional):").pack(anchor="w", pady=(5, 0))
        self.wa_filter_var = tk.StringVar()
        ttk.Entry(wa_frame, textvariable=self.wa_filter_var, width=40).pack(anchor="w")

        # ── Action Buttons ───────────────────────────────────────────
        btn_frame = ttk.Frame(self.root, padding=10)
        btn_frame.pack(fill="x")

        self.process_btn = ttk.Button(
            btn_frame, text="▶  START PROCESSING",
            style="Big.TButton", command=self._start_processing
        )
        self.process_btn.pack(side="left", padx=5)

        self.load_btn = ttk.Button(
            btn_frame, text="📦 Load Bundle into Platform",
            command=self._load_bundle
        )
        self.load_btn.pack(side="left", padx=5)

        self.open_btn = ttk.Button(
            btn_frame, text="📂 Open Bundles Folder",
            command=self._open_bundles_folder
        )
        self.open_btn.pack(side="right", padx=5)

        # ── Progress / Log ───────────────────────────────────────────
        log_frame = ttk.LabelFrame(self.root, text="Progress", padding=5)
        log_frame.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            log_frame, variable=self.progress_var, maximum=100
        )
        self.progress_bar.pack(fill="x", pady=(0, 5))

        self.log_text = scrolledtext.ScrolledText(log_frame, height=8, width=70,
                                                   state="disabled")
        self.log_text.pack(fill="both", expand=True)

        # ── Status Bar ───────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready — fill in platforms and click START")
        ttk.Label(self.root, textvariable=self.status_var,
                  relief="sunken", padding=3).pack(fill="x")

    def _log(self, message: str):
        """Thread-safe log output."""
        def _update():
            self.log_text.config(state="normal")
            self.log_text.insert("end", message + "\n")
            self.log_text.see("end")
            self.log_text.config(state="disabled")
        self.root.after(0, _update)

    def _set_status(self, text: str):
        self.root.after(0, lambda: self.status_var.set(text))

    def _set_progress(self, value: float):
        self.root.after(0, lambda: self.progress_var.set(value))

    def _browse_telegram_export(self):
        path = filedialog.askopenfilename(
            title="Select Telegram Export",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        if path:
            self.tg_export_var.set(path)

    def _browse_whatsapp_export(self):
        path = filedialog.askopenfilename(
            title="Select WhatsApp Export",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if path:
            self.wa_export_var.set(path)

    def _open_bundles_folder(self):
        import subprocess
        path = self.processor.bundle_dir
        path.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(f'explorer "{path}"')

    def _start_processing(self):
        """Validate inputs and start background processing."""
        if self.is_processing:
            messagebox.showinfo("Processing", "Already processing. Please wait.")
            return

        name = self.name_var.get().strip()
        influencer_id = self.id_var.get().strip() or name.replace(" ", "_").lower()

        if not name and not influencer_id:
            messagebox.showerror("Error", "Please enter an influencer name or ID.")
            return

        # Check what platforms have data
        has_data = False
        if self.yt_channel_var.get().strip() or self.yt_urls_text.get("1.0", "end").strip():
            has_data = True
        if self.substack_var.get().strip():
            has_data = True
        if self.bluesky_var.get().strip():
            has_data = True
        if self.telegram_var.get().strip() or self.tg_export_var.get().strip():
            has_data = True
        if self.linkedin_text.get("1.0", "end").strip():
            has_data = True
        if self.rss_text.get("1.0", "end").strip():
            has_data = True
        if self.wa_export_var.get().strip():
            has_data = True

        if not has_data:
            messagebox.showerror("Error", "Please add at least one content source.")
            return

        # Start processing in background thread
        self.is_processing = True
        self.process_btn.config(state="disabled")
        self.id_var.set(influencer_id)

        thread = threading.Thread(
            target=self._run_processing,
            args=(influencer_id, name),
            daemon=True
        )
        thread.start()

    def _run_processing(self, influencer_id: str, name: str):
        """Background processing thread."""
        try:
            self._set_status(f"Creating bundle for {name or influencer_id}...")
            self.bundle_path = self.processor.create_bundle(influencer_id, name)
            self._log(f"📦 Bundle created: {self.bundle_path.name}")

            # Count total tasks for progress
            tasks = []

            yt_channel = self.yt_channel_var.get().strip()
            yt_urls_raw = self.yt_urls_text.get("1.0", "end").strip()
            yt_urls = [u.strip() for u in yt_urls_raw.split("\n") if u.strip()] if yt_urls_raw else []

            if yt_channel:
                tasks.append(("youtube_channel", yt_channel))
            if yt_urls:
                tasks.append(("youtube_videos", yt_urls))
            if self.substack_var.get().strip():
                tasks.append(("substack", self.substack_var.get().strip()))
            if self.bluesky_var.get().strip():
                tasks.append(("bluesky", self.bluesky_var.get().strip()))
            if self.telegram_var.get().strip():
                tasks.append(("telegram", self.telegram_var.get().strip()))
            if self.tg_export_var.get().strip():
                tasks.append(("telegram_export", self.tg_export_var.get().strip()))
            if self.linkedin_text.get("1.0", "end").strip():
                tasks.append(("linkedin", self.linkedin_text.get("1.0", "end").strip()))
            if self.wa_export_var.get().strip():
                tasks.append(("whatsapp", self.wa_export_var.get().strip()))

            rss_raw = self.rss_text.get("1.0", "end").strip()
            rss_urls = [u.strip() for u in rss_raw.split("\n") if u.strip()] if rss_raw else []
            for url in rss_urls:
                tasks.append(("rss", url))

            total_tasks = len(tasks)
            for i, (task_type, data) in enumerate(tasks):
                pct = (i / total_tasks) * 100
                self._set_progress(pct)
                self._set_status(f"Processing {task_type} ({i+1}/{total_tasks})...")

                try:
                    if task_type == "youtube_channel":
                        max_v = int(self.yt_max_var.get() or 30)
                        self.processor.process_youtube_channel(
                            self.bundle_path, data, max_v, 60, self._log
                        )
                    elif task_type == "youtube_videos":
                        self.processor.process_youtube_videos(
                            self.bundle_path, data, self._log
                        )
                    elif task_type == "substack":
                        max_p = int(self.ss_max_var.get() or 50)
                        self.processor.process_substack(
                            self.bundle_path, data, max_p, self._log
                        )
                    elif task_type == "bluesky":
                        max_p = int(self.bs_max_var.get() or 50)
                        self.processor.process_bluesky(
                            self.bundle_path, data, max_p, self._log
                        )
                    elif task_type == "telegram":
                        max_p = int(self.tg_max_var.get() or 50)
                        self.processor.process_telegram(
                            self.bundle_path, data, max_p, self._log
                        )
                    elif task_type == "telegram_export":
                        self.processor.process_telegram_export(
                            self.bundle_path, data,
                            self.telegram_var.get().strip(), self._log
                        )
                    elif task_type == "linkedin":
                        self.processor.process_linkedin_paste(
                            self.bundle_path, data,
                            self.name_var.get().strip(), self._log
                        )
                    elif task_type == "whatsapp":
                        self.processor.process_whatsapp_export(
                            self.bundle_path, data,
                            self.wa_filter_var.get().strip() or None, self._log
                        )
                    elif task_type == "rss":
                        self.processor.process_rss(
                            self.bundle_path, data, 50, self._log
                        )
                except Exception as e:
                    self._log(f"❌ {task_type} error: {e}")

            # Finalize
            self._set_progress(95)
            self._set_status("Finalizing bundle...")
            self.processor.finalize_bundle(self.bundle_path, self._log)

            self._set_progress(100)
            self._set_status(f"✅ Complete! Bundle: {self.bundle_path.name}")

        except Exception as e:
            self._log(f"\n❌ FATAL ERROR: {e}")
            self._set_status(f"Error: {e}")

        finally:
            self.is_processing = False
            self.root.after(0, lambda: self.process_btn.config(state="normal"))

    def _load_bundle(self):
        """Load a bundle into the platform."""
        # If we just processed one, offer that
        if self.bundle_path and (self.bundle_path / "ready.flag").exists():
            answer = messagebox.askyesno(
                "Load Bundle",
                f"Load the just-processed bundle?\n{self.bundle_path.name}\n\n"
                f"(No = browse for a different bundle)"
            )
            if answer:
                self._do_load_bundle(str(self.bundle_path))
                return

        # Browse for bundle
        path = filedialog.askdirectory(
            title="Select Bundle Folder",
            initialdir=str(self.processor.bundle_dir)
        )
        if path:
            self._do_load_bundle(path)

    def _do_load_bundle(self, bundle_path: str):
        """Actually load the bundle."""
        self._log(f"\n📦 Loading bundle: {bundle_path}")
        self._set_status("Loading bundle into platform...")
        try:
            loader = BundleLoader()
            platform_data = str(
                Path(__file__).parent.parent / "TruePlatformAI" / "platform_data" / "collections"
            )
            loader.load_bundle(bundle_path, platform_data)
            self._log("✅ Bundle loaded into platform!")
            self._set_status("✅ Bundle loaded! Run analysis from CLI or API.")
            messagebox.showinfo("Success", "Bundle loaded into TruePlatformAI!\n\nNext: run analysis from the CLI or API.")
        except Exception as e:
            self._log(f"❌ Load error: {e}")
            self._set_status(f"Load error: {e}")
            messagebox.showerror("Error", f"Failed to load bundle:\n{e}")

    def run(self):
        """Start the GUI event loop."""
        self.root.mainloop()


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Launch the onboarding GUI."""
    bundle_dir = None
    if len(sys.argv) > 2 and sys.argv[1] == "--bundle-dir":
        bundle_dir = sys.argv[2]

    # Allow running multiple instances
    root = tk.Tk()
    app = OnboardingGUI(root, bundle_dir)

    # Add menu for launching additional instances
    menubar = tk.Menu(root)
    file_menu = tk.Menu(menubar, tearoff=0)
    file_menu.add_command(
        label="New Instance",
        command=lambda: launch_new_instance(bundle_dir),
        accelerator="Ctrl+N"
    )
    file_menu.add_separator()
    file_menu.add_command(label="Exit", command=root.quit)
    menubar.add_cascade(label="File", menu=file_menu)

    tools_menu = tk.Menu(menubar, tearoff=0)
    tools_menu.add_command(
        label="Load Bundle from Folder...",
        command=app._load_bundle
    )
    tools_menu.add_command(
        label="Open Bundles Folder",
        command=app._open_bundles_folder
    )
    menubar.add_cascade(label="Tools", menu=tools_menu)

    root.config(menu=menubar)
    root.bind("<Control-n>", lambda e: launch_new_instance(bundle_dir))

    app.run()


def launch_new_instance(bundle_dir=None):
    """Launch a new GUI instance in a separate window."""
    import subprocess
    cmd = [sys.executable, __file__]
    if bundle_dir:
        cmd.extend(["--bundle-dir", bundle_dir])
    subprocess.Popen(cmd)


if __name__ == "__main__":
    main()
