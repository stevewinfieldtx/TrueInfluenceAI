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

    # Step 3.5: Categorize topics + suggest future content based on engagement
    content_categories = _categorize_content_topics(topic_map, topic_performance, topic_timeline)
    future_content_suggestions = _build_future_content_suggestions(
        topic_map, sources, topic_performance, topic_timeline, content_categories
    )

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
        "content_categories": content_categories,
        "future_content_suggestions": future_content_suggestions,
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
    
    prompt = f"""I have {len(topics_list)} content topics extracted from a YouTube channel's videos.
Many of these are variations of the same theme. Group them into 8-15 CONTENT PILLARS.

TOPICS:
{chr(10).join(f'- {t}' for t in topics_list)}

RULES:
- Each pillar should be 2-4 words (short, punchy labels)
- Every single topic MUST be assigned to exactly one pillar
- Pillars should represent what the AUDIENCE searches for
- Good pillars: "Cost of Living", "Vietnam Visas", "Da Nang Guide", "Retirement Planning", "Healthcare Abroad"
- Bad pillars: "Miscellaneous", "Other Topics", "General" (too vague to be useful)

Respond in this exact JSON format:
{{
  "pillars": {{
    "Pillar Name": ["topic 1", "topic 2", "topic 3"],
    "Another Pillar": ["topic 4", "topic 5"]
  }}
}}

Return ONLY valid JSON. Every topic from the list above must appear exactly once."""

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


def _categorize_content_topics(topic_map, performance, timeline):
    """Assign each topic to a strategy-ready category for dashboard filtering."""
    keyword_map = {
        "education": ["how to", "guide", "tutorial", "framework", "strategy", "tips", "lesson"],
        "mindset": ["mindset", "belief", "confidence", "motivation", "identity", "discipline"],
        "growth": ["growth", "audience", "subscribers", "algorithm", "reach", "seo", "viral"],
        "monetization": ["monet", "revenue", "sales", "income", "offer", "pricing", "launch"],
        "community": ["community", "comment", "q&a", "behind the scenes", "story", "personal"],
        "operations": ["systems", "workflow", "tools", "automation", "process", "team", "productivity"],
    }

    categories = {}
    for topic in set(t for ts in topic_map.values() for t in ts):
        lower = topic.lower()
        matched = "education"
        for cat, words in keyword_map.items():
            if any(w in lower for w in words):
                matched = cat
                break

        perf = performance.get(topic, {})
        timeline_entry = timeline.get(topic, {})
        recency_bias = 1 if timeline_entry.get("count", 0) >= 3 else 0

        categories[topic] = {
            "category": matched,
            "video_count": perf.get("video_count", timeline_entry.get("count", 0)),
            "weighted_avg_views": perf.get("weighted_avg_views", 0),
            "vs_channel_avg": perf.get("vs_channel_avg", 0),
            "momentum_flag": "hot" if perf.get("vs_channel_avg", 0) > 20 and recency_bias else "stable",
        }

    return categories


def _build_future_content_suggestions(topic_map, sources, performance, timeline, categories):
    """Generate deterministic, actionable future content ideas using engagement + historical performance."""
    source_map = {s["source_id"]: s for s in sources}
    topic_videos = defaultdict(list)

    for vid, topics in topic_map.items():
        src = source_map.get(vid, {})
        views = src.get("views", 0)
        likes = src.get("likes", 0)
        comments = src.get("comments", 0)
        engagement = ((likes + comments) / views * 100) if views else 0
        for topic in topics:
            topic_videos[topic].append({
                "video_id": vid,
                "title": src.get("title", ""),
                "views": views,
                "engagement": engagement,
            })

    suggestions = []
    for topic, vids in topic_videos.items():
        if not vids:
            continue

        avg_engagement = sum(v["engagement"] for v in vids) / len(vids)
        perf = performance.get(topic, {})
        avg_views = perf.get("weighted_avg_views", 0)
        vs_channel = perf.get("vs_channel_avg", 0)
        count = perf.get("video_count", len(vids))

        trend = "steady"
        tl = timeline.get(topic, {})
        if tl.get("count", 0) >= 3:
            videos = sorted(tl.get("videos", []), key=lambda v: v.get("published", ""))
            split = len(videos) // 2
            if len(videos) - split > split:
                trend = "rising"
            elif split > len(videos) - split:
                trend = "declining"

        opportunity_score = round((vs_channel * 0.6) + (avg_engagement * 8) + (8 if trend == "rising" else 0), 1)
        if count >= 2 and (vs_channel > 5 or avg_engagement > 2.0):
            top_titles = sorted(vids, key=lambda v: (v["engagement"], v["views"]), reverse=True)[:2]
            suggestions.append({
                "topic": topic,
                "category": categories.get(topic, {}).get("category", "education"),
                "trend": trend,
                "video_count": count,
                "weighted_avg_views": avg_views,
                "avg_engagement_rate": round(avg_engagement, 2),
                "opportunity_score": opportunity_score,
                "why_now": (
                    f"{topic} is {vs_channel:+.1f}% vs channel average with {avg_engagement:.2f}% engagement. "
                    f"Historical pattern is {trend}."
                ),
                "idea_angles": [
                    f"Advanced {topic} mistakes your audience still makes",
                    f"{topic}: what changed this year and what to do now",
                    f"Reacting to audience questions about {topic}",
                ],
                "proven_examples": [t["title"] for t in top_titles if t.get("title")],
            })

    suggestions.sort(key=lambda x: x["opportunity_score"], reverse=True)
    return suggestions[:12]
