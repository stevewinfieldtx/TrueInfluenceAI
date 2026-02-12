"""
TrueInfluenceAI - Recency Weighting Module
============================================
Shared utility for recency bias across all systems.

The core idea: recent content reflects the creator's CURRENT direction,
voice, and strategy. Older content is historical context, not current intent.

Weighting:
  - Last 30 days:  1.0  (full weight — this is who they are NOW)
  - 1-3 months:    0.85 (still very relevant)
  - 3-6 months:    0.65 (relevant but fading)
  - 6-12 months:   0.40 (background context)
  - 12+ months:    0.20 (historical only — they may have moved on)

Usage:
  from recency import recency_weight, boost_scores, sort_by_recency_weighted_relevance
"""

from datetime import datetime, timezone


# ─── Core Weight Function ─────────────────────────────────────────

def recency_weight(published_at, reference_date=None):
    """
    Returns a weight between 0.2 and 1.0 based on how recent the content is.
    
    Args:
        published_at: ISO format date string or datetime object
        reference_date: datetime to measure from (default: now)
    
    Returns:
        float between 0.2 and 1.0
    """
    if not published_at:
        return 0.3  # Unknown date gets low-ish weight
    
    if reference_date is None:
        reference_date = datetime.now(timezone.utc)
    
    if isinstance(published_at, str):
        try:
            # Handle various ISO formats
            pub = published_at.replace('Z', '+00:00')
            pub_dt = datetime.fromisoformat(pub)
        except (ValueError, TypeError):
            return 0.3
    elif isinstance(published_at, datetime):
        pub_dt = published_at
    else:
        return 0.3
    
    # Make timezone-aware if needed
    if pub_dt.tzinfo is None:
        pub_dt = pub_dt.replace(tzinfo=timezone.utc)
    if reference_date.tzinfo is None:
        reference_date = reference_date.replace(tzinfo=timezone.utc)
    
    days_ago = (reference_date - pub_dt).days
    
    if days_ago < 0:
        return 1.0  # Future date (shouldn't happen, but handle gracefully)
    elif days_ago <= 30:
        return 1.0
    elif days_ago <= 90:
        # Linear decay from 1.0 to 0.85 over 60 days
        return 1.0 - (days_ago - 30) / 60 * 0.15
    elif days_ago <= 180:
        # Linear decay from 0.85 to 0.65 over 90 days
        return 0.85 - (days_ago - 90) / 90 * 0.20
    elif days_ago <= 365:
        # Linear decay from 0.65 to 0.40 over 185 days
        return 0.65 - (days_ago - 180) / 185 * 0.25
    else:
        # Linear decay from 0.40 to 0.20 over next year, then floor at 0.20
        beyond = days_ago - 365
        return max(0.20, 0.40 - beyond / 365 * 0.20)


# ─── RAG Search Boosting ─────────────────────────────────────────

def boost_scores(results, source_map):
    """
    Apply recency weighting to RAG search results.
    
    Args:
        results: list of dicts with 'source_id' and 'score'
        source_map: dict mapping source_id to source info (must have 'published_at')
    
    Returns:
        list of results with 'boosted_score' added, sorted by boosted_score desc
    """
    for r in results:
        src = source_map.get(r.get('source_id'), {})
        pub = src.get('published_at', '')
        weight = recency_weight(pub)
        r['recency_weight'] = weight
        r['boosted_score'] = r.get('score', 0) * weight
    
    results.sort(key=lambda x: x['boosted_score'], reverse=True)
    return results


# ─── Source Sorting ───────────────────────────────────────────────

def sort_sources_by_recency(sources):
    """Sort sources newest first using published_at."""
    def sort_key(s):
        pub = s.get('published_at', '')
        if not pub:
            return ''
        return pub
    return sorted(sources, key=sort_key, reverse=True)


# ─── Voice Profile Filtering ─────────────────────────────────────

def filter_recent_sources(sources, months=6):
    """
    Return only sources from the last N months.
    Used for voice profile building — we want her CURRENT voice, not historical.
    """
    cutoff = datetime.now(timezone.utc)
    filtered = []
    for s in sources:
        pub = s.get('published_at', '')
        w = recency_weight(pub, cutoff)
        if w >= 0.5:  # Roughly within ~9 months depending on exact date
            filtered.append(s)
    
    # If we filtered too aggressively (fewer than 10), relax
    if len(filtered) < 10:
        # Sort by date and take newest half
        dated = [(s, s.get('published_at', '')) for s in sources]
        dated.sort(key=lambda x: x[1], reverse=True)
        filtered = [s for s, _ in dated[:max(len(sources) // 2, 10)]]
    
    return filtered


# ─── Analytics Weighting ─────────────────────────────────────────

def weighted_topic_performance(video_topics, source_map):
    """
    Calculate topic performance with recency weighting.
    Recent videos' view counts matter more than old ones.
    
    Returns:
        dict: topic -> weighted average views
    """
    from collections import defaultdict
    
    topic_weighted_views = defaultdict(list)
    
    for vid, topics in video_topics.items():
        src = source_map.get(vid, {})
        views = src.get('views', 0)
        pub = src.get('published_at', '')
        weight = recency_weight(pub)
        
        for t in topics:
            t_clean = t.strip().title()
            topic_weighted_views[t_clean].append((views, weight))
    
    result = {}
    for topic, vw_list in topic_weighted_views.items():
        if not vw_list:
            result[topic] = 0
            continue
        # Weighted average: sum(views * weight) / sum(weights)
        total_weighted = sum(v * w for v, w in vw_list)
        total_weight = sum(w for _, w in vw_list)
        result[topic] = int(total_weighted / total_weight) if total_weight > 0 else 0
    
    return result


# ─── Content Idea Prioritization ─────────────────────────────────

def get_recent_sample_content(chunks, source_map, topic_name=None, max_samples=5):
    """
    Get sample content chunks prioritized by recency.
    For content idea generation, we want the AI to see her RECENT voice.
    """
    scored = []
    for c in chunks:
        src = source_map.get(c.get('source_id'), {})
        pub = src.get('published_at', '')
        weight = recency_weight(pub)
        scored.append((c, weight))
    
    scored.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in scored[:max_samples]]
