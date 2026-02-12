"""
TrueInfluenceAI - Cloud Insights Builder
==========================================
Generates strategic content insights via LLM.
Cloud-ready version of build_insights.py.
"""

import os, json
from pathlib import Path
from datetime import datetime

import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL_ID = os.getenv("OPENROUTER_MODEL_ID", "anthropic/claude-sonnet-4-20250514")


def build_insights(bundle_dir):
    """Generate strategic insights from creator data."""
    bundle_dir = Path(bundle_dir)

    sources = json.loads((bundle_dir / "sources.json").read_text(encoding="utf-8"))
    chunks = json.loads((bundle_dir / "chunks.json").read_text(encoding="utf-8"))
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    metrics = {}
    if (bundle_dir / "channel_metrics.json").exists():
        metrics = json.loads((bundle_dir / "channel_metrics.json").read_text(encoding="utf-8"))
    voice = {}
    if (bundle_dir / "voice_profile.json").exists():
        voice = json.loads((bundle_dir / "voice_profile.json").read_text(encoding="utf-8"))

    channel = manifest.get("channel", "Unknown")

    # Build a content summary for the LLM
    video_summaries = []
    for s in sources[:50]:
        views = s.get("views", 0)
        title = s.get("title", "")
        pub = s.get("published_at", s.get("published_text", ""))
        video_summaries.append(f"- \"{title}\" ({views:,} views, {pub})")

    video_list = "\n".join(video_summaries)

    prompt = f"""You are a content strategist analyzing {channel}'s YouTube channel.

CHANNEL STATS:
- Total videos analyzed: {manifest.get('total_videos', 0)}
- Avg views: {metrics.get('channel_avg_views', 'N/A'):,}
- Engagement rate: {metrics.get('channel_engagement_rate', 'N/A')}%

VOICE PROFILE:
{json.dumps(voice, indent=2) if voice else 'Not available'}

RECENT VIDEOS (newest first):
{video_list}

Generate 8-12 strategic insights for this creator. Each insight should be actionable.

IMPORTANT: Performance data is RECENCY-WEIGHTED. Recent videos count ~5x more than older ones.
Topics they've moved away from represent DELIBERATE strategic shifts, not mistakes.
Respect their evolution - don't recommend going backward to abandoned topics.

Respond in JSON:
{{
  "insights": [
    {{
      "title": "Short title",
      "type": "opportunity|warning|strength|trend",
      "priority": "high|medium|low",
      "description": "2-3 sentence explanation",
      "action": "Specific action the creator should take"
    }}
  ],
  "content_gaps": [
    {{
      "topic": "Topic name",
      "opportunity_score": 85,
      "reasoning": "Why this is an opportunity"
    }}
  ],
  "strategic_direction": "2-3 sentence summary of where this creator is heading and should continue heading"
}}

Return ONLY valid JSON."""

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENROUTER_MODEL_ID,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.4,
                "max_tokens": 3000,
            },
            timeout=90,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]

        if "```" in text:
            text = text.split("```json")[-1].split("```")[0] if "```json" in text else text.split("```")[1].split("```")[0]

        insights = json.loads(text.strip())
        insights["generated_at"] = datetime.utcnow().isoformat()
        insights["model"] = OPENROUTER_MODEL_ID

        (bundle_dir / "insights.json").write_text(
            json.dumps(insights, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"Insights built: {len(insights.get('insights', []))} insights, {len(insights.get('content_gaps', []))} gaps")

    except Exception as e:
        print(f"Insights failed: {e}")
        (bundle_dir / "insights.json").write_text(
            json.dumps({"insights": [], "error": str(e)}, indent=2),
            encoding="utf-8",
        )
