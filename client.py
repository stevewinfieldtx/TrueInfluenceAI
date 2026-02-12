"""
TrueInfluenceAI - Platform Client
====================================
Python client for the TruePlatformAI REST API.
All vertical products use this client to communicate with the engine.

Usage:
    from client import TruePlatformClient

    client = TruePlatformClient()
    client.create_collection("sunny", "creator", name="Sunny Lenarduzzi")
    client.ingest_channel("sunny", "https://youtube.com/@SunnyLenarduzzi", max_videos=20)
    client.analyze("sunny")
    answer = client.ask("sunny", "What topics get the most engagement?")
"""

import requests
from typing import List, Dict, Optional
import time


class TruePlatformClient:
    """REST client for TruePlatformAI engine."""

    def __init__(self, base_url: str = "http://localhost:8100"):
        self.base_url = base_url.rstrip("/")
        self.api = f"{self.base_url}/api/v1"

    def _get(self, path: str, params: dict = None) -> dict:
        resp = requests.get(f"{self.api}{path}", params=params, timeout=120)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, json_data: dict = None) -> dict:
        resp = requests.post(f"{self.api}{path}", json=json_data or {}, timeout=300)
        resp.raise_for_status()
        return resp.json()

    # ── Health ────────────────────────────────────────────────────────────

    def health(self) -> dict:
        resp = requests.get(f"{self.base_url}/health", timeout=10)
        resp.raise_for_status()
        return resp.json()

    # ── Templates ────────────────────────────────────────────────────────

    def list_templates(self) -> list:
        return self._get("/templates")

    def get_template(self, template_id: str) -> dict:
        return self._get(f"/templates/{template_id}")

    # ── Collections ──────────────────────────────────────────────────────

    def create_collection(self, collection_id: str, template_id: str = "creator",
                          name: str = "", description: str = "",
                          metadata: dict = None) -> dict:
        return self._post("/collections", {
            "collection_id": collection_id,
            "template_id": template_id,
            "name": name or collection_id,
            "description": description,
            "metadata": metadata or {},
        })

    def get_collection(self, collection_id: str) -> dict:
        return self._get(f"/collections/{collection_id}")

    def list_collections(self) -> list:
        return self._get("/collections")

    def get_stats(self, collection_id: str) -> dict:
        return self._get(f"/collections/{collection_id}/stats")

    def get_sources(self, collection_id: str) -> list:
        return self._get(f"/collections/{collection_id}/sources")

    # ── Ingestion ────────────────────────────────────────────────────────

    def ingest_youtube(self, collection_id: str, video_url: str,
                       metadata: dict = None) -> dict:
        return self._post(f"/collections/{collection_id}/ingest/youtube", {
            "video_url": video_url,
            "metadata": metadata or {},
        })

    def ingest_channel(self, collection_id: str, channel_url: str,
                       max_videos: int = 50, min_duration: int = 0,
                       metadata: dict = None) -> dict:
        """Start channel ingestion (background). Returns job_id."""
        return self._post(f"/collections/{collection_id}/ingest/youtube-channel", {
            "channel_url": channel_url,
            "max_videos": max_videos,
            "min_duration": min_duration,
            "metadata": metadata or {},
        })

    def ingest_blog(self, collection_id: str, url: str) -> dict:
        return self._post(f"/collections/{collection_id}/ingest/blog", {"url": url})

    def ingest_text(self, collection_id: str, text: str,
                    title: str = "", author: str = "") -> dict:
        return self._post(f"/collections/{collection_id}/ingest/text", {
            "text": text, "title": title, "author": author,
        })

    def ingest_batch(self, collection_id: str, urls: List[str]) -> dict:
        """Start batch ingestion (background). Returns job_id."""
        return self._post(f"/collections/{collection_id}/ingest/batch", {
            "urls": urls,
        })

    def ingest_podcast(self, collection_id: str, rss_url: str,
                       max_episodes: int = 50) -> dict:
        return self._post(f"/collections/{collection_id}/ingest/podcast", {
            "rss_url": rss_url, "max_episodes": max_episodes,
        })

    def upload_document(self, collection_id: str, file_path: str) -> dict:
        """Upload a file (PDF, TXT, DOCX) to ingest."""
        with open(file_path, "rb") as f:
            resp = requests.post(
                f"{self.api}/collections/{collection_id}/ingest/upload",
                files={"file": f}, timeout=120
            )
        resp.raise_for_status()
        return resp.json()

    # ── Analysis ─────────────────────────────────────────────────────────

    def analyze(self, collection_id: str) -> dict:
        """Start analysis (background)."""
        return self._post(f"/collections/{collection_id}/analyze")

    def get_analysis(self, collection_id: str) -> dict:
        return self._get(f"/collections/{collection_id}/analysis")

    def get_topics(self, collection_id: str) -> list:
        return self._get(f"/collections/{collection_id}/topics")

    def get_insights(self, collection_id: str) -> list:
        return self._get(f"/collections/{collection_id}/insights")

    def get_gaps(self, collection_id: str) -> dict:
        return self._get(f"/collections/{collection_id}/gaps")

    # ── Search ───────────────────────────────────────────────────────────

    def search(self, collection_id: str, query: str,
               top_k: int = 10, topic: str = None) -> list:
        params = {"q": query, "top_k": top_k}
        if topic:
            params["topic"] = topic
        return self._get(f"/collections/{collection_id}/search", params)

    # ── Chatbot ──────────────────────────────────────────────────────────

    def ask(self, collection_id: str, question: str,
            top_k: int = 8, include_sources: bool = True) -> dict:
        return self._post(f"/collections/{collection_id}/ask", {
            "question": question,
            "top_k": top_k,
            "include_sources": include_sources,
        })

    # ── Jobs ─────────────────────────────────────────────────────────────

    def list_jobs(self, collection_id: str = None) -> list:
        params = {"collection_id": collection_id} if collection_id else {}
        return self._get("/jobs", params)

    def get_job(self, job_id: str) -> dict:
        return self._get(f"/jobs/{job_id}")

    def wait_for_job(self, job_id: str, poll_interval: int = 5,
                     timeout: int = 600, verbose: bool = True) -> dict:
        """Poll a job until it completes."""
        start = time.time()
        while True:
            job = self.get_job(job_id)
            status = job.get("status", "unknown")
            progress = job.get("progress", 0)
            completed = job.get("completed", 0)
            total = job.get("total", 0)

            if verbose:
                print(f"  [{status}] {progress}% ({completed}/{total})")

            if status in ("complete", "error", "failed"):
                return job

            if time.time() - start > timeout:
                print(f"  ⚠️ Timeout after {timeout}s")
                return job

            time.sleep(poll_interval)
