"""
TrueInfluenceAI - Web Platform Server
=======================================
FastAPI server that powers the entire platform:

  - Main domain  → Platform landing page (creator onboarding)
  - Subdomains   → Per-creator intelligence pages
  - /api/*       → Onboarding pipeline, job status, chat endpoints

Architecture:
  trueinfluence.ai          → Landing page + "Get Started"
  sunny.trueinfluence.ai    → Sunny's creator intelligence suite
  alex.trueinfluence.ai     → Alex's suite
  ...etc

Local dev:
  py web/server.py
  → http://localhost:8200         (landing page)
  → http://localhost:8200/c/sunny (creator pages in dev mode)

Production (Railway):
  Subdomain routing via Host header

Author: Steve Winfield / WinTech Partners
"""

import os
import sys
import json
import asyncio
import uuid
import time
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from dotenv import load_dotenv
load_dotenv(Path(r"C:\Users\steve\Documents\.env"))
load_dotenv(Path(r"C:\Users\steve\Documents\TruePlatformAI\.env"))

# ── Paths ──
BASE_DIR = Path(__file__).parent.parent
BUNDLE_DIR = BASE_DIR / "bundles"
WEB_DIR = Path(__file__).parent
STATIC_DIR = WEB_DIR / "static"
TEMPLATE_DIR = WEB_DIR / "templates"

# ── Config ──
MAIN_DOMAIN = os.getenv("MAIN_DOMAIN", "trueinfluence.ai")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "qwen/qwen3-embedding-8b")

# ── Job tracking (in-memory for now, Redis/DB later) ──
jobs: Dict[str, dict] = {}


# =====================================================================
# BUNDLE REGISTRY - maps creator handles to their latest bundle
# =====================================================================

def build_registry() -> Dict[str, Path]:
    """Scan bundles/ and build a handle → bundle_path map."""
    registry = {}
    if not BUNDLE_DIR.exists():
        return registry
    
    # Group bundles by channel name, pick latest
    bundles_by_name = {}
    for d in BUNDLE_DIR.iterdir():
        if not d.is_dir():
            continue
        manifest_path = d / "manifest.json"
        if not manifest_path.exists():
            continue
        try:
            with open(manifest_path, 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            channel = manifest.get("channel", "")
            if not channel:
                continue
            handle = slugify(channel)
            # Keep latest by modified time
            if handle not in bundles_by_name or d.stat().st_mtime > bundles_by_name[handle].stat().st_mtime:
                bundles_by_name[handle] = d
        except Exception:
            continue
    
    registry = bundles_by_name
    return registry


def slugify(name: str) -> str:
    """Convert channel name to URL-safe handle."""
    s = name.lower().strip()
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = s.strip('-')
    return s or "unknown"


def get_bundle_for_handle(handle: str) -> Optional[Path]:
    """Look up the bundle path for a creator handle."""
    registry = build_registry()
    return registry.get(handle)


def list_creators() -> list:
    """List all available creators with metadata."""
    registry = build_registry()
    creators = []
    for handle, bundle_path in registry.items():
        try:
            with open(bundle_path / "manifest.json", 'r', encoding='utf-8') as f:
                manifest = json.load(f)
            creators.append({
                "handle": handle,
                "name": manifest.get("channel", handle),
                "videos": manifest.get("total_videos", 0),
                "chunks": manifest.get("total_chunks", 0),
                "created": manifest.get("created", ""),
                "bundle": bundle_path.name,
            })
        except Exception:
            continue
    return sorted(creators, key=lambda c: c["name"])


# =====================================================================
# PIPELINE RUNNER (background tasks)
# =====================================================================

async def run_pipeline(job_id: str, channel_url: str, max_videos: int = 50):
    """
    Run the full pipeline in background:
      1. fast_ingest (scan + subtitle + chunk + embed)
      2. enrich (YouTube API data)
      3. build_voice (voice profile)
      4. build_insights (strategic insights)
      5. analytics (topic performance)
      6. build_pages (HTML generation)
    """
    jobs[job_id]["status"] = "ingesting"
    jobs[job_id]["step"] = "Scanning channel & pulling transcripts..."
    
    try:
        # Run each pipeline step as subprocess
        # Step 1: Fast ingest
        result = await _run_script(
            "fast_ingest.py", channel_url, "--max", str(max_videos),
            job_id=job_id, step_name="Ingesting content"
        )
        if result != 0:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = "Ingestion failed"
            return
        
        # Find the bundle that was just created
        bundle_path = _find_newest_bundle()
        if not bundle_path:
            jobs[job_id]["status"] = "failed"
            jobs[job_id]["error"] = "No bundle created"
            return
        
        bundle_name = bundle_path.name
        jobs[job_id]["bundle"] = bundle_name
        
        # Step 2: Enrich with YouTube API data
        jobs[job_id]["step"] = "Enriching with performance data..."
        result = await _run_script("enrich.py", bundle_name, job_id=job_id, step_name="Enriching")
        
        # Step 3: Build voice profile
        jobs[job_id]["step"] = "Analyzing voice & style..."
        result = await _run_script("build_voice.py", str(bundle_path), job_id=job_id, step_name="Voice analysis")
        
        # Step 4: Build insights
        jobs[job_id]["step"] = "Generating strategic insights..."
        result = await _run_script("build_insights.py", bundle_name, job_id=job_id, step_name="Insights")
        
        # Step 5: Analytics
        jobs[job_id]["step"] = "Building analytics report..."
        result = await _run_script("analytics.py", bundle_name, job_id=job_id, step_name="Analytics")
        
        # Step 6: Build pages
        jobs[job_id]["step"] = "Generating creator pages..."
        result = await _run_script("build_pages.py", bundle_name, job_id=job_id, step_name="Pages")
        
        # Done!
        jobs[job_id]["status"] = "complete"
        jobs[job_id]["step"] = "Ready!"
        
        # Get the handle for the new creator
        with open(bundle_path / "manifest.json", 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        handle = slugify(manifest.get("channel", "unknown"))
        jobs[job_id]["handle"] = handle
        jobs[job_id]["completed_at"] = datetime.now().isoformat()
        
    except Exception as e:
        jobs[job_id]["status"] = "failed"
        jobs[job_id]["error"] = str(e)


async def _run_script(script_name: str, *args, job_id: str = "", step_name: str = "") -> int:
    """Run a Python script as async subprocess."""
    script_path = BASE_DIR / script_name
    cmd = [sys.executable, str(script_path)] + list(args)
    
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(BASE_DIR)
    )
    
    stdout, stderr = await proc.communicate()
    
    if job_id and job_id in jobs:
        jobs[job_id]["log"] = jobs[job_id].get("log", "") + f"\n--- {step_name} ---\n"
        if stdout:
            jobs[job_id]["log"] += stdout.decode(errors='replace')[-2000:]
        if stderr and proc.returncode != 0:
            jobs[job_id]["log"] += "\nERROR:\n" + stderr.decode(errors='replace')[-1000:]
    
    return proc.returncode


def _find_newest_bundle() -> Optional[Path]:
    """Find the most recently created bundle."""
    if not BUNDLE_DIR.exists():
        return None
    bundles = sorted(BUNDLE_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    for b in bundles:
        if (b / "manifest.json").exists():
            return b
    return None


# =====================================================================
# CHAT API (for creator discuss pages)
# =====================================================================

async def handle_chat(handle: str, question: str) -> dict:
    """RAG chat using creator's embedded content."""
    bundle_path = get_bundle_for_handle(handle)
    if not bundle_path:
        return {"answer": "Creator not found.", "sources": []}
    
    # Load chunks
    chunks_path = bundle_path / "chunks.json"
    if not chunks_path.exists():
        return {"answer": "No content available.", "sources": []}
    
    with open(chunks_path, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    
    # Load voice profile
    voice_path = bundle_path / "voice_profile.json"
    voice = {}
    if voice_path.exists():
        with open(voice_path, 'r', encoding='utf-8') as f:
            voice = json.load(f)
    
    # Load sources for metadata
    sources_path = bundle_path / "sources.json"
    sources = []
    if sources_path.exists():
        with open(sources_path, 'r', encoding='utf-8') as f:
            sources = json.load(f)
    source_map = {s.get("source_id", ""): s for s in sources}
    
    # Embed the question
    import requests as req
    try:
        resp = req.post(
            'https://openrouter.ai/api/v1/embeddings',
            headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}', 'Content-Type': 'application/json'},
            json={'model': EMBEDDING_MODEL, 'input': question},
            timeout=30
        )
        q_embedding = resp.json()['data'][0]['embedding']
    except Exception:
        return {"answer": "Search temporarily unavailable.", "sources": []}
    
    # Cosine similarity search with recency boost
    import math
    
    def cosine_sim(a, b):
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(x * x for x in b))
        return dot / (na * nb) if na and nb else 0
    
    scored = []
    for chunk in chunks:
        emb = chunk.get("embedding", [])
        if not emb:
            continue
        sim = cosine_sim(q_embedding, emb)
        
        # Recency boost
        src = source_map.get(chunk.get("source_id", ""), {})
        pub = src.get("published_at", "")
        recency_weight = 1.0
        if pub:
            try:
                pub_dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
                days_old = (datetime.now(pub_dt.tzinfo) - pub_dt).days
                recency_weight = max(0.2, 1.0 - (days_old / 500))
            except Exception:
                pass
        
        final_score = sim * recency_weight
        scored.append((final_score, chunk, src))
    
    scored.sort(key=lambda x: -x[0])
    top = scored[:5]
    
    if not top:
        return {"answer": "I don't have enough content to answer that.", "sources": []}
    
    # Build context
    context = "\n\n".join(
        f"[Source: {s.get('title', 'Unknown')}]\n{c['text']}"
        for _, c, s in top
    )
    
    # Build voice instruction
    voice_instruction = ""
    if voice:
        tone = voice.get("tone", "")
        style = voice.get("style_notes", "")
        voice_instruction = f"\nRespond in this creator's voice. Their tone is: {tone}\nStyle: {style}\n"
    
    # Get manifest for creator name
    manifest_path = bundle_path / "manifest.json"
    creator_name = handle
    if manifest_path.exists():
        with open(manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)
        creator_name = manifest.get("channel", handle)
    
    prompt = f"""You are answering questions AS {creator_name}, based on their actual content.
{voice_instruction}
Use ONLY the following content excerpts to answer. If the answer isn't in the content, say so.

CONTENT:
{context}

QUESTION: {question}

Answer naturally in {creator_name}'s voice, referencing specific advice from their content."""
    
    try:
        resp = req.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers={'Authorization': f'Bearer {OPENROUTER_API_KEY}', 'Content-Type': 'application/json'},
            json={
                'model': os.getenv("OPENROUTER_MODEL_ID", "google/gemini-2.5-flash-lite:online"),
                'messages': [{'role': 'user', 'content': prompt}],
                'max_tokens': 800
            },
            timeout=60
        )
        answer = resp.json()['choices'][0]['message']['content']
    except Exception as e:
        answer = f"Sorry, I couldn't generate a response right now. ({str(e)[:50]})"
    
    cited_sources = [
        {
            "title": s.get("title", "Unknown"),
            "url": s.get("url", ""),
            "score": round(score, 3),
        }
        for score, _, s in top[:3]
    ]
    
    return {"answer": answer, "sources": cited_sources}


# =====================================================================
# FASTAPI APP
# =====================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"\n🚀 TrueInfluenceAI Platform Server")
    print(f"   Bundles: {BUNDLE_DIR}")
    registry = build_registry()
    print(f"   Creators: {len(registry)} ({', '.join(registry.keys()) if registry else 'none yet'})")
    print(f"   Main domain: {MAIN_DOMAIN}")
    print(f"   Dev mode: http://localhost:8200")
    print(f"   Creator pages: http://localhost:8200/c/{{handle}}")
    yield
    print("\n👋 Shutting down")


app = FastAPI(title="TrueInfluenceAI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ── Middleware: detect subdomain ──
@app.middleware("http")
async def subdomain_router(request: Request, call_next):
    """Detect subdomain and route to creator pages."""
    host = request.headers.get("host", "").split(":")[0].lower()
    
    # Check if this is a subdomain request
    creator_handle = None
    if host != MAIN_DOMAIN and host != "localhost" and host != "127.0.0.1":
        # Could be "sunny.trueinfluence.ai" or similar
        if host.endswith(f".{MAIN_DOMAIN}"):
            creator_handle = host.replace(f".{MAIN_DOMAIN}", "")
    
    # Store on request state for route handlers
    request.state.creator_handle = creator_handle
    response = await call_next(request)
    return response


# ── Main landing page ──
@app.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    """Platform landing page or creator subdomain page."""
    # If subdomain, serve creator landing
    handle = getattr(request.state, 'creator_handle', None)
    if handle:
        return await serve_creator_page(handle, "index.html")
    
    # Serve platform landing
    landing_path = TEMPLATE_DIR / "landing.html"
    if landing_path.exists():
        return HTMLResponse(landing_path.read_text(encoding='utf-8'))
    return HTMLResponse("<h1>TrueInfluenceAI - Coming Soon</h1>")


# ── Dev mode: /c/{handle} routes ──
@app.get("/c/{handle}", response_class=HTMLResponse)
@app.get("/c/{handle}/", response_class=HTMLResponse)
async def creator_landing(handle: str):
    return await serve_creator_page(handle, "index.html")

@app.get("/c/{handle}/dashboard", response_class=HTMLResponse)
@app.get("/c/{handle}/dashboard.html", response_class=HTMLResponse)
async def creator_dashboard(handle: str):
    return await serve_creator_page(handle, "dashboard.html")

@app.get("/c/{handle}/analytics", response_class=HTMLResponse)
@app.get("/c/{handle}/analytics.html", response_class=HTMLResponse)
async def creator_analytics(handle: str):
    return await serve_creator_page(handle, "analytics.html")

@app.get("/c/{handle}/discuss", response_class=HTMLResponse)
@app.get("/c/{handle}/discuss.html", response_class=HTMLResponse)
async def creator_discuss(handle: str):
    return await serve_creator_page(handle, "discuss.html")


async def serve_creator_page(handle: str, page: str) -> HTMLResponse:
    """Serve an HTML page from a creator's bundle."""
    bundle_path = get_bundle_for_handle(handle)
    if not bundle_path:
        return HTMLResponse(
            f"<h1>Creator not found: {handle}</h1>"
            f"<p>This creator hasn't been onboarded yet.</p>"
            f"<p><a href='/'>← Go to TrueInfluenceAI</a></p>",
            status_code=404
        )
    
    page_path = bundle_path / page
    if not page_path.exists():
        return HTMLResponse(f"<h1>Page not found: {page}</h1>", status_code=404)
    
    html = page_path.read_text(encoding='utf-8')
    
    # Fix relative links in dev mode (e.g., href="dashboard.html" → "/c/handle/dashboard.html")
    # Only needed when serving via /c/ prefix, not subdomains
    html = html.replace('href="dashboard.html"', f'href="/c/{handle}/dashboard.html"')
    html = html.replace('href="analytics.html"', f'href="/c/{handle}/analytics.html"')
    html = html.replace('href="discuss.html"', f'href="/c/{handle}/discuss.html"')
    html = html.replace('href="index.html"', f'href="/c/{handle}/"')
    
    return HTMLResponse(html)


# ── API: Onboarding ──
@app.post("/api/onboard")
async def start_onboarding(request: Request, background_tasks: BackgroundTasks):
    """Start the onboarding pipeline for a new creator."""
    body = await request.json()
    channel_url = body.get("channel_url", "").strip()
    max_videos = min(body.get("max_videos", 50), 100)
    
    if not channel_url:
        raise HTTPException(400, "channel_url is required")
    
    # Validate URL format
    if "youtube.com" not in channel_url and "youtu.be" not in channel_url:
        # Try to construct from handle
        if channel_url.startswith("@"):
            channel_url = f"https://www.youtube.com/{channel_url}"
        elif not channel_url.startswith("http"):
            channel_url = f"https://www.youtube.com/@{channel_url}"
    
    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "id": job_id,
        "channel_url": channel_url,
        "status": "queued",
        "step": "Waiting to start...",
        "started_at": datetime.now().isoformat(),
        "log": "",
    }
    
    background_tasks.add_task(run_pipeline, job_id, channel_url, max_videos)
    
    return {"job_id": job_id, "status": "queued"}


@app.get("/api/job/{job_id}")
async def get_job_status(job_id: str):
    """Check the status of an onboarding job."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    
    # Don't send full log in status check
    return {k: v for k, v in job.items() if k != "log"}


@app.get("/api/job/{job_id}/log")
async def get_job_log(job_id: str):
    """Get the full log for an onboarding job."""
    job = jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {"log": job.get("log", "")}


# ── API: Chat ──
@app.post("/api/chat/{handle}")
async def chat_endpoint(handle: str, request: Request):
    """Chat with a creator's AI."""
    body = await request.json()
    question = body.get("question", "").strip()
    if not question:
        raise HTTPException(400, "question is required")
    
    result = await handle_chat(handle, question)
    return result


# ── API: Creator list ──
@app.get("/api/creators")
async def api_creators():
    """List all available creators."""
    return {"creators": list_creators()}


# =====================================================================
# RUN
# =====================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8200)
