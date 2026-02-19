"""
TrueInfluenceAI - Cloud Platform Server
==========================================
FastAPI server deployed on Railway.

Routes:
  GET  /                     -> Platform landing page
  GET  /onboard              -> Onboarding form (enter creator URL)
  POST /api/onboard          -> Start processing pipeline
  GET  /api/status/{job_id}  -> Check pipeline progress
  GET  /c/{slug}             -> Creator landing page
  GET  /c/{slug}/dashboard   -> Creator dashboard
  GET  /c/{slug}/analytics   -> Creator analytics
  GET  /c/{slug}/discuss     -> Creator discussion/chat

Later: subdomain routing (sunny.trueinfluenceai.com -> /c/sunny)

Author: Steve Winfield / WinTech Partners
"""

import os, json, uuid, asyncio, time
from pathlib import Path
from datetime import datetime

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load .env from project root (one level up), fall back to current dir
load_dotenv(Path(__file__).resolve().parent.parent / ".env")
load_dotenv()  # also check current dir as fallback (e.g. Railway)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
BUNDLE_PATH = Path(os.getenv("BUNDLE_STORAGE_PATH", "./bundles"))
BUNDLE_PATH.mkdir(parents=True, exist_ok=True)
PLATFORM_DOMAIN = os.getenv("PLATFORM_DOMAIN", "trueinfluenceai.com")
PORT = int(os.getenv("PORT", 8080))

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="TrueInfluenceAI", version="1.0.0")

# CORS — allow creator websites to call the chat API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: restrict to registered creator domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

# In-memory job tracker (swap for Redis/DB in production)
jobs = {}
# Creator registry: slug -> bundle_path
creators = {}

def load_creator_registry():
    """Scan bundles dir and build slug -> path mapping."""
    creators.clear()
    if not BUNDLE_PATH.exists():
        return
    for d in BUNDLE_PATH.iterdir():
        if d.is_dir() and (d / "manifest.json").exists():
            try:
                manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
                slug = manifest.get("slug") or d.name.split("_")[0].lower()
                creators[slug] = {
                    "path": d,
                    "name": manifest.get("channel", slug),
                    "slug": slug,
                    "created": manifest.get("created_at", ""),
                    "total_videos": manifest.get("total_videos", 0),
                }
            except Exception:
                pass

load_creator_registry()


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health")
async def health():
    return {"status": "ok", "creators": len(creators), "ts": datetime.utcnow().isoformat()}


# ---------------------------------------------------------------------------
# Landing Page
# ---------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def landing(request: Request):
    return templates.TemplateResponse("landing.html", {
        "request": request,
        "creator_count": len(creators),
        "creators": list(creators.values())[:6],
    })


# ---------------------------------------------------------------------------
# Onboarding Form
# ---------------------------------------------------------------------------
@app.get("/onboard", response_class=HTMLResponse)
async def onboard_form(request: Request):
    return templates.TemplateResponse("onboard.html", {"request": request})


# ---------------------------------------------------------------------------
# API: Start Onboarding
# ---------------------------------------------------------------------------
@app.post("/api/onboard")
async def start_onboard(request: Request, background_tasks: BackgroundTasks):
    body = await request.json()
    channel_url = body.get("channel_url", "").strip()
    creator_name = body.get("creator_name", "").strip()
    max_videos = min(int(body.get("max_videos", 50)), 100)
    tradition = body.get("tradition", "none").strip()

    if not channel_url:
        raise HTTPException(400, "channel_url is required")

    # Extract slug from URL
    slug = ""
    if "/@" in channel_url:
        slug = channel_url.split("/@")[-1].split("/")[0].strip().lower()
    elif creator_name:
        slug = creator_name.lower().replace(" ", "").replace("_", "")
    else:
        slug = f"creator_{uuid.uuid4().hex[:8]}"

    # Check if already processed (allow force re-process)
    force = body.get("force", False)
    if slug in creators and not force:
        return JSONResponse({
            "status": "exists",
            "slug": slug,
            "url": f"/c/{slug}",
            "message": f"{creators[slug]['name']} is already on the platform. Use force=true to re-process."
        })

    # If forcing, remove old entry from registry (old bundle stays as backup)
    if slug in creators:
        creators.pop(slug, None)

    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {
        "id": job_id,
        "slug": slug,
        "channel_url": channel_url,
        "creator_name": creator_name or slug,
        "status": "queued",
        "progress": 0,
        "step": "Starting...",
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "error": None,
    }

    # Run pipeline in background
    background_tasks.add_task(run_pipeline, job_id, channel_url, slug, creator_name, max_videos, tradition)

    return JSONResponse({
        "status": "started",
        "job_id": job_id,
        "slug": slug,
        "message": f"Processing {creator_name or slug}. This takes 3-8 minutes."
    })


# ---------------------------------------------------------------------------
# API: Check Status
# ---------------------------------------------------------------------------
@app.get("/api/status/{job_id}")
async def check_status(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return JSONResponse(job)


# ---------------------------------------------------------------------------
# API: List Creators
# ---------------------------------------------------------------------------
@app.get("/api/creators")
async def list_creators():
    return JSONResponse({"creators": list(creators.values())})


# ---------------------------------------------------------------------------
# API: Refresh Creator (Incremental Update)
# ---------------------------------------------------------------------------
@app.post("/api/refresh/{slug}")
async def refresh_creator(slug: str, background_tasks: BackgroundTasks):
    creator = creators.get(slug)
    if not creator:
        raise HTTPException(404, f"Creator '{slug}' not found")

    # Check if already refreshing
    for j in jobs.values():
        if j.get("slug") == slug and j.get("status") in ("queued", "processing"):
            return JSONResponse({
                "status": "already_running",
                "job_id": j["id"],
                "message": f"Refresh already in progress for {slug}"
            })

    # Get channel URL from manifest
    bundle_dir = creator["path"]
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    channel_url = manifest.get("channel_url", "")
    creator_name = manifest.get("channel", slug)

    # If no channel_url in manifest, try to reconstruct it
    if not channel_url:
        channel_url = f"https://www.youtube.com/@{slug}"

    job_id = uuid.uuid4().hex[:12]
    jobs[job_id] = {
        "id": job_id,
        "slug": slug,
        "channel_url": channel_url,
        "creator_name": creator_name,
        "status": "queued",
        "progress": 0,
        "step": "Starting refresh...",
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": None,
        "error": None,
        "type": "refresh",
    }

    background_tasks.add_task(
        run_refresh_pipeline, job_id, channel_url, slug, creator_name, bundle_dir
    )

    return JSONResponse({
        "status": "started",
        "job_id": job_id,
        "slug": slug,
        "message": f"Refreshing {creator_name}. New videos only — should be fast."
    })


async def run_refresh_pipeline(job_id: str, channel_url: str, slug: str,
                               creator_name: str, bundle_dir: Path):
    """Incremental refresh: only new videos, then re-run analytics + pages."""
    job = jobs[job_id]
    try:
        from pipeline.ingest import incremental_update
        from pipeline.enrich import enrich_bundle
        from pipeline.voice import build_voice_profile
        from pipeline.insights import build_insights
        from pipeline.analytics import run_analytics
        from pipeline.pages import build_all_pages

        job["status"] = "processing"
        job["step"] = "Scanning for new videos..."
        job["progress"] = 10

        result = await asyncio.to_thread(
            incremental_update, channel_url, slug, creator_name, 100, bundle_dir
        )
        new_count = result.get("new_videos", 0)
        job["progress"] = 40
        job["step"] = f"Found {new_count} new videos" if new_count else "No new videos — updating analytics"

        # Re-run enrich (updates channel metrics with fresh view counts)
        job["step"] = "Updating channel metrics..."
        job["progress"] = 50
        await asyncio.to_thread(enrich_bundle, bundle_dir)

        # Only rebuild voice if we have new content
        if new_count > 0:
            job["step"] = "Updating voice profile..."
            job["progress"] = 60
            await asyncio.to_thread(build_voice_profile, bundle_dir)

        # Re-run analytics THEN insights (insights reads analytics_report.json)
        job["step"] = "Updating topic analytics..."
        job["progress"] = 70
        await asyncio.to_thread(run_analytics, bundle_dir)

        job["step"] = "Regenerating insights..."
        job["progress"] = 80
        await asyncio.to_thread(build_insights, bundle_dir)

        # Re-run scripture detection if tradition is set and we have new content
        if new_count > 0:
            _manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8")) if (bundle_dir / "manifest.json").exists() else {}
            tradition = _manifest.get("tradition", "")
            if tradition and tradition != "none":
                try:
                    from pipeline.scripture import process_bundle_scriptures
                    job["step"] = f"Updating scripture index ({tradition})..."
                    job["progress"] = 85
                    await asyncio.to_thread(process_bundle_scriptures, bundle_dir, tradition)
                except Exception as e:
                    print(f"Scripture refresh error (non-fatal): {e}")

        # Rebuild pages
        job["step"] = "Rebuilding pages..."
        job["progress"] = 90
        await asyncio.to_thread(build_all_pages, bundle_dir, slug)

        # Update registry
        manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
        creators[slug]["total_videos"] = manifest.get("total_videos", 0)
        creators[slug]["created"] = manifest.get("created_at", "")

        # Sync to database
        try:
            from pipeline.db import sync_bundle_to_db
            await asyncio.to_thread(sync_bundle_to_db, slug, bundle_dir)
        except Exception as e:
            print(f"DB sync error on refresh (non-fatal): {e}")

        job["status"] = "complete"
        job["progress"] = 100
        job["step"] = f"Refresh done! {new_count} new video{'s' if new_count != 1 else ''} added." if new_count else "Refresh done! Analytics updated with latest view counts."
        job["completed_at"] = datetime.utcnow().isoformat()
        job["url"] = f"/c/{slug}"
        job["new_videos"] = new_count

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        job["step"] = f"Error: {str(e)[:200]}"
        import traceback
        traceback.print_exc()


# ---------------------------------------------------------------------------
# Creator Pages (path-based routing, subdomain mapping later)
# ---------------------------------------------------------------------------
@app.get("/c/{slug}", response_class=HTMLResponse)
async def creator_landing(slug: str):
    creator = creators.get(slug)
    if not creator:
        raise HTTPException(404, f"Creator '{slug}' not found")
    page = creator["path"] / "index.html"
    if not page.exists():
        raise HTTPException(404, "Landing page not built yet")
    return HTMLResponse(page.read_text(encoding="utf-8"))


@app.get("/c/{slug}/dashboard", response_class=HTMLResponse)
async def creator_dashboard(slug: str):
    creator = creators.get(slug)
    if not creator:
        raise HTTPException(404, f"Creator '{slug}' not found")
    page = creator["path"] / "dashboard.html"
    if not page.exists():
        raise HTTPException(404, "Dashboard not built yet")
    return HTMLResponse(page.read_text(encoding="utf-8"))


@app.get("/c/{slug}/analytics")
async def creator_analytics(slug: str):
    """Analytics merged into dashboard. Redirect for backwards compatibility."""
    from fastapi.responses import RedirectResponse
    return RedirectResponse(f"/c/{slug}/dashboard")


@app.get("/c/{slug}/discuss", response_class=HTMLResponse)
async def creator_discuss(slug: str):
    creator = creators.get(slug)
    if not creator:
        raise HTTPException(404, f"Creator '{slug}' not found")
    page = creator["path"] / "discuss.html"
    if not page.exists():
        raise HTTPException(404, "Discussion page not built yet")
    return HTMLResponse(page.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# API: Chat — server-side RAG (no API keys in browser)
# ---------------------------------------------------------------------------
@app.post("/api/chat/{slug}")
async def api_chat(slug: str, request: Request):
    creator = creators.get(slug)
    if not creator:
        raise HTTPException(404, f"Creator '{slug}' not found")
    body = await request.json()
    question = body.get("question", "").strip()
    if not question:
        raise HTTPException(400, "question is required")
    from pipeline.chat_api import handle_chat
    result = await asyncio.to_thread(handle_chat, slug, question, creator["path"])
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# API: Write — server-side content generation (no API keys in browser)
# ---------------------------------------------------------------------------
@app.post("/api/write/{slug}")
async def api_write(slug: str, request: Request):
    creator = creators.get(slug)
    if not creator:
        raise HTTPException(404, f"Creator '{slug}' not found")
    body = await request.json()
    topic = body.get("topic", "").strip()
    write_type = body.get("type", "start")  # start | write | explain
    extra_context = body.get("context", "")
    card_type = body.get("card_type", "")
    views = body.get("views", "")
    big_bet = body.get("big_bet", "")
    label = body.get("label", "")
    if not topic:
        raise HTTPException(400, "topic is required")
    from pipeline.chat_api import handle_write
    result = await asyncio.to_thread(
        handle_write, slug, topic, write_type, creator["path"],
        extra_context, card_type, views, big_bet, label
    )
    return JSONResponse(result)


# ---------------------------------------------------------------------------
# API: Force sync a creator's bundle to database
# ---------------------------------------------------------------------------
@app.post("/api/sync/{slug}")
async def sync_to_db(slug: str):
    creator = creators.get(slug)
    if not creator:
        raise HTTPException(404, f"Creator '{slug}' not found")
    try:
        from pipeline.db import sync_from_bundle
        await asyncio.to_thread(sync_from_bundle, slug, creator["path"])
        return JSONResponse({"status": "synced", "slug": slug})
    except Exception as e:
        raise HTTPException(500, f"Sync failed: {e}")


# ---------------------------------------------------------------------------
# Pipeline Runner (background task)
# ---------------------------------------------------------------------------
async def run_pipeline(job_id: str, channel_url: str, slug: str,
                       creator_name: str, max_videos: int, tradition: str = "none"):
    """
    Full processing pipeline:
      1. Scan channel (scrapetube)
      2. Pull transcripts (yt-dlp captions)
      3. Chunk transcripts
      4. Embed chunks (OpenRouter)
      5. Enrich with YouTube Data API
      6. Build voice profile (LLM)
      7. Build insights (LLM)
      8. Run analytics
      9. Build HTML pages
    """
    job = jobs[job_id]

    try:
        from pipeline.ingest import ingest_channel
        from pipeline.enrich import enrich_bundle
        from pipeline.voice import build_voice_profile
        from pipeline.insights import build_insights
        from pipeline.analytics import run_analytics
        from pipeline.pages import build_all_pages

        # Step 1-4: Ingest (0-45% — scanning, transcripts, chunking, embedding)
        job["status"] = "processing"
        job["step"] = "Scanning channel videos..."
        job["progress"] = 2

        bundle_dir = BUNDLE_PATH / f"{slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        bundle_dir.mkdir(parents=True, exist_ok=True)

        def _update_progress(pct, step):
            job["progress"] = pct
            job["step"] = step

        result = await asyncio.to_thread(
            ingest_channel, channel_url, slug, creator_name, max_videos, bundle_dir,
            progress_cb=_update_progress
        )
        job["progress"] = 48
        job["step"] = f"Ingested {result.get('video_count', 0)} videos, {result.get('chunk_count', 0)} chunks"

        # Step 5: Enrich
        job["step"] = "Enriching with YouTube analytics..."
        job["progress"] = 50
        await asyncio.to_thread(enrich_bundle, bundle_dir)

        # Step 6: Voice profile
        job["step"] = "Building voice profile..."
        job["progress"] = 60
        await asyncio.to_thread(build_voice_profile, bundle_dir)

        # Step 7: Analytics (MUST run before insights — insights reads analytics_report.json)
        job["step"] = "Running topic analytics..."
        job["progress"] = 70
        await asyncio.to_thread(run_analytics, bundle_dir)

        # Step 8: Insights (reads analytics_report.json for revival, cannibalization, AI deep analysis)
        job["step"] = "Generating strategic insights..."
        job["progress"] = 80
        await asyncio.to_thread(build_insights, bundle_dir)

        # Step 8.5: Scripture detection (if religious tradition selected)
        if tradition and tradition != "none":
            try:
                from pipeline.scripture import process_bundle_scriptures
                job["step"] = f"Detecting scripture references ({tradition})..."
                job["progress"] = 85
                await asyncio.to_thread(process_bundle_scriptures, bundle_dir, tradition)
            except ImportError:
                print("Scripture module not found, skipping")
            except Exception as e:
                print(f"Scripture detection error (non-fatal): {e}")

        # Step 9: Build pages
        job["step"] = "Building creator pages..."
        job["progress"] = 90
        await asyncio.to_thread(build_all_pages, bundle_dir, slug)

        # Update manifest with slug and tradition
        manifest_path = bundle_dir / "manifest.json"
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["slug"] = slug
            if tradition and tradition != "none":
                manifest["tradition"] = tradition
            manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

        # Register creator (in-memory)
        creators[slug] = {
            "path": bundle_dir,
            "name": creator_name or slug,
            "slug": slug,
            "created": datetime.utcnow().isoformat(),
            "total_videos": result.get("video_count", 0),
        }

        # Sync bundle data to PostgreSQL (chunks, sources, voice profile)
        job["step"] = "Syncing to database..."
        job["progress"] = 95
        try:
            from pipeline.db import sync_bundle_to_db
            await asyncio.to_thread(sync_bundle_to_db, slug, bundle_dir)
        except Exception as e:
            print(f"DB sync error (non-fatal): {e}")

        job["status"] = "complete"
        job["progress"] = 100
        job["step"] = "Done! Creator pages are live."
        job["completed_at"] = datetime.utcnow().isoformat()
        job["url"] = f"/c/{slug}"

    except Exception as e:
        job["status"] = "error"
        job["error"] = str(e)
        job["step"] = f"Error: {str(e)[:200]}"
        import traceback
        traceback.print_exc()


# ---------------------------------------------------------------------------
# Startup
# ---------------------------------------------------------------------------
@app.on_event("startup")
async def startup():
    load_creator_registry()

    # Initialize database (PostgreSQL + pgvector)
    db_ok = False
    try:
        from pipeline.db import init_db, get_creator, sync_bundle_to_db
        init_db()
        db_ok = True
        print(f"   Database: connected (pgvector enabled)")
    except Exception as e:
        print(f"   Database: NOT available ({e}) — chat/write will use JSON fallback")

    # Auto-migrate existing bundles to DB on first deploy
    if db_ok and creators:
        migrated = 0
        for slug, info in creators.items():
            try:
                existing = get_creator(slug)
                if not existing:
                    sync_bundle_to_db(slug, info["path"])
                    migrated += 1
            except Exception as e:
                print(f"   Migration skip {slug}: {e}")
        if migrated:
            print(f"   Migrated {migrated} creator(s) to database")

    print(f"TrueInfluenceAI Platform")
    print(f"   Creators loaded: {len(creators)}")
    print(f"   Bundle path: {BUNDLE_PATH}")
    print(f"   Domain: {PLATFORM_DOMAIN}")
