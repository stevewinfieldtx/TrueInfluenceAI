"""
TrueInfluenceAI - Creator Intelligence Platform
===================================================
The creator-facing product built on TruePlatformAI.

Adds creator-specific logic on top of the platform engine:
  - Channel onboarding (scan + ingest + analyze in one call)
  - Content gap analysis with audience demand signals
  - Content calendar generation
  - Subscriber chatbot configuration
  - Creator dashboard data formatting

Usage:
    from app import TrueInfluenceAI

    ti = TrueInfluenceAI()
    ti.onboard_channel("sunny", "https://youtube.com/@SunnyLenarduzzi",
                       name="Sunny Lenarduzzi", max_videos=30)
    dashboard = ti.get_dashboard("sunny")
    calendar = ti.generate_content_calendar("sunny", weeks=4)

Author: Steve Winfield / WinTech Partners
"""

import json
import time
from typing import List, Dict, Optional
from client import TruePlatformClient


class TrueInfluenceAI:
    """
    Creator intelligence platform.
    Wraps TruePlatformClient with creator-specific workflows.
    """

    def __init__(self, api_url: str = "http://localhost:8100"):
        self.client = TruePlatformClient(api_url)

    # =========================================================================
    # ONBOARDING
    # =========================================================================

    def onboard_channel(self, creator_id: str, channel_url: str,
                        name: str = "", max_videos: int = 30,
                        min_duration: int = 60, wait: bool = True) -> Dict:
        """
        Full creator onboarding:
          1. Create collection (creator template)
          2. Scan + ingest channel videos
          3. Wait for completion
          4. Run analysis
          5. Return dashboard-ready data
        """
        print(f"\n{'='*60}")
        print(f"  🚀 Onboarding: {name or creator_id}")
        print(f"  Channel: {channel_url}")
        print(f"  Max videos: {max_videos}")
        print(f"{'='*60}")

        # 1. Create collection
        try:
            col = self.client.create_collection(
                creator_id, "creator",
                name=name or creator_id,
                description=f"Creator channel: {channel_url}",
                metadata={"channel_url": channel_url}
            )
            print(f"\n  ✅ Collection created: {col.get('name')}")
        except Exception as e:
            if "409" in str(e):
                print(f"\n  ⏭️ Collection exists, continuing...")
            else:
                print(f"\n  ❌ Collection failed: {e}")
                return {"error": str(e)}

        # 2. Start channel ingestion
        result = self.client.ingest_channel(
            creator_id, channel_url, max_videos, min_duration
        )
        job_id = result.get("job_id")
        print(f"  ✅ Ingestion started (job: {job_id})")

        # 3. Wait for completion
        if wait and job_id:
            print(f"\n  ⏳ Ingesting videos...")
            final = self.client.wait_for_job(job_id, poll_interval=10, timeout=900)
            print(f"\n  ✅ Ingestion complete: {final.get('completed')}/{final.get('total')} videos")
        elif not wait:
            return {"status": "ingesting", "job_id": job_id}

        # 4. Run analysis
        print(f"\n  🧠 Running analysis...")
        self.client.analyze(creator_id)
        time.sleep(3)

        # Poll for results
        for attempt in range(20):
            try:
                analysis = self.client.get_analysis(creator_id)
                if analysis and analysis.get("topics"):
                    print(f"  ✅ Analysis complete!")
                    return {
                        "status": "ready",
                        "creator_id": creator_id,
                        "name": name,
                        "stats": self.client.get_stats(creator_id),
                        "topic_count": len(analysis.get("topics", [])),
                        "insight_count": len(analysis.get("insights", [])),
                        "gap_count": len(analysis.get("gap_map", {})),
                    }
            except Exception:
                pass
            time.sleep(5)

        return {"status": "analysis_pending", "creator_id": creator_id}

    def onboard_videos(self, creator_id: str, video_urls: List[str],
                       name: str = "", wait: bool = True) -> Dict:
        """Onboard a creator with specific video URLs instead of full channel."""
        print(f"\n  🚀 Onboarding {name or creator_id} with {len(video_urls)} videos")

        # Create collection
        try:
            self.client.create_collection(
                creator_id, "creator", name=name or creator_id
            )
        except Exception:
            pass

        # Batch ingest
        result = self.client.ingest_batch(creator_id, video_urls)
        job_id = result.get("job_id")

        if wait and job_id:
            final = self.client.wait_for_job(job_id, poll_interval=8, timeout=600)
            print(f"  ✅ {final.get('completed')}/{final.get('total')} ingested")

            # Analyze
            self.client.analyze(creator_id)
            time.sleep(15)

        return {"status": "ready" if wait else "ingesting", "job_id": job_id}

    # =========================================================================
    # DASHBOARD DATA
    # =========================================================================

    def get_dashboard(self, creator_id: str) -> Dict:
        """Get all dashboard data for a creator in one call."""
        stats = self.client.get_stats(creator_id)
        analysis = self.client.get_analysis(creator_id)

        if not analysis:
            return {
                "creator_id": creator_id,
                "status": "no_analysis",
                "stats": stats,
            }

        topics = analysis.get("topics", [])
        insights = analysis.get("insights", [])
        gaps = analysis.get("gap_map", {})
        tone = analysis.get("tone_distribution", {})

        # Format topics for bubble chart
        bubbles = []
        for t in topics:
            coverage = t.get("coverage_score", 0)
            bubbles.append({
                "topic": t.get("topic", ""),
                "coverage": coverage,
                "chunks": t.get("chunk_count", 0),
                "sources": t.get("source_count", 0),
                "depth": t.get("avg_depth", 0),
                "gap": gaps.get(t.get("topic", ""), 0),
                "trend": t.get("trend", "stable"),
            })

        # Separate gap-only topics (not in coverage)
        covered_topics = {t.get("topic") for t in topics}
        pure_gaps = [
            {"topic": t, "coverage": 0, "gap": score}
            for t, score in gaps.items()
            if t not in covered_topics
        ]

        return {
            "creator_id": creator_id,
            "status": "ready",
            "stats": stats,
            "bubbles": bubbles,
            "pure_gaps": pure_gaps,
            "insights": insights,
            "tone_distribution": tone,
            "analyzed_at": analysis.get("analyzed_at"),
        }

    # =========================================================================
    # CHATBOT
    # =========================================================================

    def ask(self, creator_id: str, question: str) -> Dict:
        """Ask the creator's content a question."""
        return self.client.ask(creator_id, question)

    def ask_formatted(self, creator_id: str, question: str) -> str:
        """Ask and return a nicely formatted string."""
        result = self.client.ask(creator_id, question)
        answer = result.get("answer", "No answer available.")
        confidence = result.get("confidence", 0)
        sources = result.get("sources", [])

        output = f"\n{answer}\n"
        if sources:
            output += f"\n📎 Sources ({confidence}% confidence):\n"
            for s in sources[:3]:
                output += f"  → {s['title']} at {s['timestamp']}\n"
        return output

    # =========================================================================
    # CONTENT INTELLIGENCE
    # =========================================================================

    def get_content_gaps(self, creator_id: str) -> List[Dict]:
        """Get content gaps sorted by opportunity score."""
        analysis = self.client.get_analysis(creator_id)
        if not analysis:
            return []

        gaps = analysis.get("gap_map", {})
        topics = {t["topic"]: t for t in analysis.get("topics", [])}

        gap_list = []
        for topic, gap_score in gaps.items():
            existing = topics.get(topic, {})
            gap_list.append({
                "topic": topic,
                "gap_score": gap_score,
                "current_coverage": existing.get("coverage_score", 0),
                "current_chunks": existing.get("chunk_count", 0),
                "opportunity": "high" if gap_score > 70 else "medium" if gap_score > 40 else "low",
            })

        return sorted(gap_list, key=lambda g: -g["gap_score"])

    def get_top_topics(self, creator_id: str, limit: int = 10) -> List[Dict]:
        """Get top covered topics."""
        topics = self.client.get_topics(creator_id)
        return topics[:limit]

    def get_actionable_insights(self, creator_id: str,
                                 priority: str = None) -> List[Dict]:
        """Get insights, optionally filtered by priority."""
        insights = self.client.get_insights(creator_id)
        if priority:
            insights = [i for i in insights if i.get("priority") == priority]
        return insights

    # =========================================================================
    # SEARCH
    # =========================================================================

    def search_content(self, creator_id: str, query: str,
                       top_k: int = 5) -> List[Dict]:
        """Search creator's content."""
        return self.client.search(creator_id, query, top_k)

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def print_dashboard(self, creator_id: str):
        """Print a text dashboard for a creator."""
        dash = self.get_dashboard(creator_id)
        stats = dash.get("stats", {})
        bubbles = dash.get("bubbles", [])
        insights = dash.get("insights", [])

        print(f"\n{'='*60}")
        print(f"  📊 CREATOR DASHBOARD: {creator_id}")
        print(f"{'='*60}")
        print(f"  Videos: {stats.get('ready_sources', 0)} | Chunks: {stats.get('chunk_count', 0)} | Hours: {stats.get('total_duration_hours', 0)}")

        if bubbles:
            print(f"\n  {'TOPIC':<25} {'COVERAGE':>8} {'CHUNKS':>7} {'GAP':>6}")
            print(f"  {'─'*25} {'─'*8} {'─'*7} {'─'*6}")
            for b in sorted(bubbles, key=lambda x: -x["coverage"])[:15]:
                bar = "█" * int(b["coverage"] / 5)
                gap_str = f"{b['gap']:.0f}%" if b["gap"] > 0 else "—"
                print(f"  {b['topic']:<25} {b['coverage']:>7.1f}% {b['chunks']:>7} {gap_str:>6}")

        if insights:
            print(f"\n  💡 INSIGHTS:")
            for i in insights[:8]:
                pri = i.get("priority", "?")[:4]
                typ = i.get("type", "?")
                title = i.get("title", "N/A")
                print(f"    [{pri}|{typ}] {title}")

        tone = dash.get("tone_distribution", {})
        if tone:
            print(f"\n  🎨 TONE: ", end="")
            parts = [f"{k} {v:.0f}%" for k, v in
                     sorted(tone.items(), key=lambda x: -x[1])[:4]]
            print(" | ".join(parts))

        print()
