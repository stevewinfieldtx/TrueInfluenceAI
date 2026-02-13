"""
TrueInfluenceAI - Cloud Analytics Pipeline
============================================
Topic extraction, timeline analysis, performance scoring.
Cloud-ready version of analytics.py with recency weighting.
"""

import os, json, re
from pathlib import Path
from datetime import datetime
from collections import defaultdict

import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL_ID = os.getenv("OPENROUTER_MODEL_ID", "anthropic/claude-sonnet-4-20250514")


def run_analytics(bundle_dir):
    """Full analytics pipeline: topic extraction + performance + recommendations."""
    bundle_dir = Path(bundle_dir)

    chunks = json.loads((bundle_dir / "chunks.json").read_text(encoding="utf-8"))
    sources = json.loads((bundle_dir / "sources.json").read_text(encoding="utf-8"))
    manifest = json.loads((bundle_dir / "manifest.json").read_text(encoding="utf-8"))
    metrics = {}
    if (bundle_dir / "channel_metrics.json").exists():
        metrics = json.loads((bundle_dir / "channel_metrics.json").read_text(encoding="utf-8"))

    channel = manifest.get("channel", "Unknown")

    # Step 1: Extract topics per video via LLM
    print("Extracting topics...")
    topic_map = _extract_topics(sources, chunks)

    # Step 1.5: Cluster topics into content pillars
    print("Clustering topics into content pillars...")
    topic_map = _cluster_topics(topic_map)

    # Step 2: Build timeline
    topic_timeline = _build_timeline(topic_map, sources)

    # Step 3: Performance analysis (recency-weighted)
    topic_performance = _analyze_performance(topic_map, sources, metrics)

    # Step 4: Generate recommendations
    print("Generating recommendations...")
    recommendations = _generate_recommendations(
        channel, topic_performance, topic_timeline, metrics
    )

    # Save
    report = {
        "channel": channel,
        "generated_at": datetime.utcnow().isoformat(),
        "topic_map": topic_map,
        "topic_timeline": topic_timeline,
        "topic_performance": topic_performance,
        "recommendations": recommendations,
        "total_topics": len(set(t for topics in topic_map.values() for t in topics)),
    }

    (bundle_dir / "analytics_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"Analytics complete: {report['total_topics']} topics tracked")


def _extract_topics(sources, chunks):
    """Use LLM to extract 3-5 topics per video."""
    video_chunks = defaultdict(list)
    for c in chunks:
        video_chunks[c["video_id"]].append(c["text"])

    topic_map = {}

    for s in sources:
        vid = s["source_id"]
        text = " ".join(video_chunks.get(vid, []))[:3000]
        if not text:
            continue

        prompt = f"""Extract 3-5 content topics from this video transcript.
Video title: "{s.get('title', '')}"

Transcript excerpt:
{text}

RULES:
- Topics should be REUSABLE across multiple videos — think "content pillars" not one-off labels
- BAD (too specific to one video): "Panama's retiree-friendly visa", "Da Nang studio apartment costs", "San Francisco's post-2008 struggle"
- BAD (too vague): "Expat life", "Travel tips", "Money"
- GOOD (reusable themes): "Visa options for retirees", "Cost of living breakdown", "Expat loneliness", "Why people leave Vietnam", "Healthcare abroad"
- Ask yourself: "Could another video on this channel also get this same topic?" If not, make it broader.
- Each topic should be 3-6 words
- Focus on the AUDIENCE NEED the video serves, not the specific details

Return ONLY a JSON array of topic strings.
Example: ["Visa options for retirees", "Cost of living abroad", "Expat relationship challenges"]"""

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
                    "temperature": 0.2,
                    "max_tokens": 200,
                },
                timeout=30,
            )
            resp.raise_for_status()
            text_resp = resp.json()["choices"][0]["message"]["content"]
            text_resp = text_resp.strip()
            if text_resp.startswith("```"):
                text_resp = text_resp.split("```json")[-1].split("```")[0] if "```json" in text_resp else text_resp.split("```")[1]
            topics = json.loads(text_resp.strip())
            if isinstance(topics, list):
                topic_map[vid] = [t.strip() for t in topics if isinstance(t, str)]
        except json.JSONDecodeError as e:
            print(f"   Topic extraction JSON parse failed for {vid}: {e} (response: {text_resp[:100] if text_resp else 'empty'})")
        except Exception as e:
            print(f"   Topic extraction failed for {vid}: {e}")

    return topic_map


def _cluster_topics(topic_map):
    """Cluster individual topics into 8-15 content pillars using LLM.
    
    Takes: {video_id: ["Da Nang affordability", "Reasons for leaving Da Nang", ...]}
    Returns: {video_id: ["Da Nang Living", "Cost of Living", ...]} with standardized pillar names.
    """
    # Collect all unique topics
    all_topics = set()
    for topics in topic_map.values():
        all_topics.update(topics)
    
    if len(all_topics) < 5:
        return topic_map  # Too few to cluster
    
    topics_list = sorted(all_topics)
    
    # Target pillar count based on number of videos
    num_videos = len(topic_map)
    target_pillars = max(6, min(12, num_videos // 2))
    
    prompt = f"""I have {len(topics_list)} content topics extracted from {num_videos} YouTube videos.
Group them into EXACTLY {target_pillars} content pillars. NO MORE than {target_pillars}.

TOPICS:
{chr(10).join(f'- {t}' for t in topics_list)}

RULES:
- EXACTLY {target_pillars} pillars. Merge aggressively. Fewer is better.
- Each pillar should be 2-4 words
- MERGE similar topics ruthlessly:
  - "Da Nang affordability" + "Da Nang vs Ho Chi Minh" + "Reasons for leaving Da Nang" = ONE pillar: "Da Nang Living"
  - "Vietnam rent tiers" + "Real rent costs" + "Cost of living breakdown" + "Escaping cost of living crisis" = ONE pillar: "Cost of Living"
  - "Retirement visa challenges" + "Visa options for retirees" + "Long-term visa pathways" = ONE pillar: "Visas & Immigration"
  - "Expat loneliness" + "Expat relationships" + "Culture shock" + "Adapting to local life" = ONE pillar: "Expat Adjustment"
- Every topic MUST be assigned to exactly one pillar
- Each pillar should ideally contain topics from MULTIPLE different videos
- If two topics sound even vaguely related, they go in the SAME pillar

Respond in this exact JSON format:
{{
  "pillars": {{
    "Pillar Name": ["topic 1", "topic 2", "topic 3"],
    "Another Pillar": ["topic 4", "topic 5"]
  }}
}}

Return ONLY valid JSON. Every topic must appear exactly once. EXACTLY {target_pillars} pillars."""

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
                "temperature": 0.1,
                "max_tokens": 3000,
            },
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        text = text.strip()
        if text.startswith("```"):
            text = text.split("```json")[-1].split("```")[0] if "```json" in text else text.split("```")[1]
        result = json.loads(text.strip())
        pillars = result.get("pillars", {})
        
        if not pillars:
            print("   WARNING: Clustering returned empty pillars, keeping original topics")
            return topic_map
        
        # Build reverse map: original_topic -> pillar_name
        topic_to_pillar = {}
        for pillar_name, member_topics in pillars.items():
            for t in member_topics:
                topic_to_pillar[t] = pillar_name
        
        # Remap topic_map: replace each video's topics with their pillar names
        clustered_map = {}
        for vid, topics in topic_map.items():
            pillar_set = set()
            for t in topics:
                pillar = topic_to_pillar.get(t, t)  # Fallback to original if not mapped
                pillar_set.add(pillar)
            clustered_map[vid] = list(pillar_set)
        
        original_count = len(all_topics)
        pillar_count = len(pillars)
        print(f"   Clustered {original_count} topics into {pillar_count} content pillars")
        
        return clustered_map
        
    except Exception as e:
        print(f"   Topic clustering failed: {e}. Keeping original topics.")
        return topic_map


def _build_timeline(topic_map, sources):
    """Build topic timeline showing when each topic appears."""
    source_map = {s["source_id"]: s for s in sources}
    timeline = defaultdict(lambda: {"videos": [], "first_seen": "", "last_seen": "", "count": 0})

    for vid, topics in topic_map.items():
        s = source_map.get(vid, {})
        pub = s.get("published_at", s.get("published_text", ""))
        for t in topics:
            entry = timeline[t]
            entry["videos"].append({"video_id": vid, "title": s.get("title", ""), "published": pub})
            entry["count"] += 1
            if not entry["first_seen"] or pub < entry["first_seen"]:
                entry["first_seen"] = pub
            if not entry["last_seen"] or pub > entry["last_seen"]:
                entry["last_seen"] = pub

    return dict(timeline)


def _analyze_performance(topic_map, sources, metrics):
    """Recency-weighted performance analysis per topic."""
    source_map = {s["source_id"]: s for s in sources}
    channel_avg = metrics.get("channel_avg_views", 1)

    sorted_sources = sorted(
        sources,
        key=lambda s: s.get("published_at", s.get("published_text", "")),
        reverse=True,
    )
    position_map = {s["source_id"]: i for i, s in enumerate(sorted_sources)}
    total = max(len(sorted_sources), 1)

    topic_stats = defaultdict(lambda: {"weighted_views": 0, "total_weight": 0, "videos": 0, "raw_views": []})

    for vid, topics in topic_map.items():
        s = source_map.get(vid, {})
        views = s.get("views", 0)
        pos = position_map.get(vid, total)
        pct = pos / total

        if pct < 0.25:
            w = 1.0
        elif pct < 0.50:
            w = 0.7
        elif pct < 0.75:
            w = 0.4
        else:
            w = 0.2

        for t in topics:
            topic_stats[t]["weighted_views"] += views * w
            topic_stats[t]["total_weight"] += w
            topic_stats[t]["videos"] += 1
            topic_stats[t]["raw_views"].append(views)

    performance = {}
    for topic, stats in topic_stats.items():
        avg = stats["weighted_views"] / stats["total_weight"] if stats["total_weight"] else 0
        raw = stats["raw_views"]
        max_v = max(raw) if raw else 0
        min_v = min(raw) if raw else 0
        # Consistency check: if max is >5x min across 2+ videos, flag as inconsistent
        is_consistent = True
        if len(raw) >= 2 and min_v > 0:
            is_consistent = (max_v / min_v) < 5
        elif len(raw) >= 2 and min_v == 0:
            is_consistent = False

        performance[topic] = {
            "weighted_avg_views": round(avg),
            "video_count": stats["videos"],
            "vs_channel_avg": round((avg / channel_avg - 1) * 100, 1) if channel_avg else 0,
            "is_consistent": is_consistent,
            "max_views": max_v,
            "min_views": min_v,
        }

    return performance


def _generate_recommendations(channel, performance, timeline, metrics):
    """LLM-generated strategic recommendations."""
    rising, declining, steady = [], [], []
    for topic, tl in timeline.items():
        count = tl["count"]
        if count >= 3:
            videos = sorted(tl["videos"], key=lambda v: v.get("published", ""))
            first_half = len([v for i, v in enumerate(videos) if i < len(videos) // 2])
            second_half = count - first_half
            if second_half > first_half:
                rising.append(topic)
            elif first_half > second_half:
                declining.append(topic)
            else:
                steady.append(topic)
        else:
            steady.append(topic)

    prompt = f"""You are a content strategist for {channel}.

TOPIC TRENDS:
- Rising (increasing frequency): {', '.join(rising[:15]) or 'None'}
- Declining (decreasing frequency): {', '.join(declining[:15]) or 'None'}
- Steady: {', '.join(steady[:15]) or 'None'}

TOP PERFORMING TOPICS (recency-weighted):
{json.dumps({t: performance[t] for t in sorted(performance, key=lambda x: -performance[x]['weighted_avg_views'])[:10]}, indent=2)}

CHANNEL AVG VIEWS: {metrics.get('channel_avg_views', 'N/A'):,}

CRITICAL CONTEXT:
- Performance data is RECENCY-WEIGHTED (recent videos count ~5x more)
- Declining topics likely represent DELIBERATE strategic shifts, not failures
- Respect the creator's evolution - recommend content aligned with their CURRENT direction

Generate 5-7 strategic recommendations. Respond in JSON:
{{
  "recommendations": [
    {{
      "title": "Short title",
      "category": "double_down|explore|evolve|optimize",
      "description": "2-3 sentence actionable recommendation",
      "expected_impact": "high|medium|low"
    }}
  ],
  "strategic_summary": "3-4 sentence overview of the creator's content trajectory and where they should focus"
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
                "max_tokens": 2000,
            },
            timeout=60,
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        if "```" in text:
            text = text.split("```json")[-1].split("```")[0] if "```json" in text else text.split("```")[1]
        return json.loads(text.strip())
    except Exception as e:
        print(f"Recommendations failed: {e}")
        return {"recommendations": [], "error": str(e)}
