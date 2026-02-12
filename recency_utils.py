"""
TrueInfluenceAI - Recency Weighting Utilities
===============================================
Shared functions for applying recency bias across the platform.

Recent content reflects the creator's CURRENT voice, strategy, and direction.
Old content may represent outdated thinking they've deliberately moved away from.

Weighting approach:
  - Most recent 25% of content → weight 1.0 (full weight)
  - Next 25%                   → weight 0.7
  - Next 25%                   → weight 0.4
  - Oldest 25%                 → weight 0.2
  
This means recent content is 5x more influential than old content,
while old content still contributes (it doesn't disappear entirely).
"""

from datetime import datetime


def compute_recency_weight(position_index, total_count):
    """
    Given a 0-based position (0 = newest) and total count,
    return a recency weight between 0.2 and 1.0.
    
    Args:
        position_index: 0 = most recent, total_count-1 = oldest
        total_count: total number of items
    Returns:
        float weight between 0.2 and 1.0
    """
    if total_count <= 1:
        return 1.0
    
    ratio = position_index / (total_count - 1)  # 0.0 = newest, 1.0 = oldest
    
    if ratio <= 0.25:
        return 1.0
    elif ratio <= 0.50:
        return 0.7
    elif ratio <= 0.75:
        return 0.4
    else:
        return 0.2


def compute_recency_weight_smooth(position_index, total_count, min_weight=0.2):
    """
    Smooth exponential decay from 1.0 (newest) to min_weight (oldest).
    Better for cosine similarity boosting where you don't want hard steps.
    
    Args:
        position_index: 0 = most recent, total_count-1 = oldest
        total_count: total number of items
        min_weight: minimum weight for oldest content (default 0.2)
    Returns:
        float weight between min_weight and 1.0
    """
    if total_count <= 1:
        return 1.0
    
    import math
    ratio = position_index / (total_count - 1)  # 0.0 = newest, 1.0 = oldest
    # Exponential decay: e^(-k*ratio) mapped to [min_weight, 1.0]
    k = -math.log(min_weight)  # ensures oldest gets exactly min_weight
    return math.exp(-k * ratio)


def rank_sources_by_date(sources):
    """
    Sort sources by published_at (newest first) and return
    a dict mapping source_id -> position (0 = newest).
    
    Args:
        sources: list of source dicts with 'source_id' and 'published_at'
    Returns:
        dict of {source_id: rank_position}
    """
    sorted_sources = sorted(
        sources,
        key=lambda s: s.get('published_at', '') or '',
        reverse=True  # newest first
    )
    return {s['source_id']: idx for idx, s in enumerate(sorted_sources)}


def weighted_sample(items, weights, n):
    """
    Sample n items with probability proportional to weights.
    Items with higher weight are more likely to be selected.
    
    Args:
        items: list of items to sample from
        weights: list of float weights (same length as items)
        n: number of items to sample
    Returns:
        list of sampled items (may have fewer than n if items < n)
    """
    import random
    if len(items) <= n:
        return list(items)
    
    # Normalize weights to probabilities
    total_w = sum(weights)
    if total_w == 0:
        return random.sample(items, min(n, len(items)))
    
    probs = [w / total_w for w in weights]
    
    # Weighted sampling without replacement
    indices = list(range(len(items)))
    selected = []
    remaining_probs = list(probs)
    
    for _ in range(n):
        if not indices:
            break
        total_p = sum(remaining_probs[i] for i in indices)
        if total_p == 0:
            break
        r = random.random() * total_p
        cumulative = 0
        chosen = indices[0]
        for idx in indices:
            cumulative += remaining_probs[idx]
            if cumulative >= r:
                chosen = idx
                break
        selected.append(items[chosen])
        indices.remove(chosen)
    
    return selected


def weighted_average(values, weights):
    """
    Compute weighted average.
    
    Args:
        values: list of numeric values
        weights: list of float weights (same length)
    Returns:
        float weighted average
    """
    if not values or not weights:
        return 0
    total_w = sum(weights)
    if total_w == 0:
        return sum(values) / len(values) if values else 0
    return sum(v * w for v, w in zip(values, weights)) / total_w
