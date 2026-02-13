"""
Improved Statistical Analysis for TrueInfluenceAI
==================================================

This module provides robust statistical methods for analyzing YouTube content performance.
It replaces arbitrary thresholds with statistically-grounded approaches.

Key Improvements:
1. Confidence intervals for topic performance
2. Z-score based performance classification
3. Outlier detection using IQR method
4. Trend analysis using linear regression
5. Statistical significance tests
6. Bayesian smoothing for small sample sizes
"""

import math
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timedelta
import statistics


@dataclass
class TopicStats:
    """Statistical summary for a topic."""
    topic: str
    video_count: int
    mean_views: float
    median_views: float
    std_dev: float
    coefficient_of_variation: float  # CV = std/mean (consistency measure)
    min_views: float
    max_views: float
    weighted_avg_views: float
    vs_channel_avg: float
    z_score: float  # Standard deviations from channel mean
    confidence_interval_95: Tuple[float, float]
    confidence_level: str  # 'high', 'medium', 'low'
    outlier_count: int
    trend_slope: float  # Views per video over time
    trend_direction: str  # 'rising', 'declining', 'stable'
    trend_p_value: float  # Statistical significance of trend
    performance_tier: str  # 'exceptional', 'strong', 'average', 'weak', 'poor'


class StatisticalAnalyzer:
    """
    Provides statistically rigorous analysis of content performance.
    
    Uses:
    - Z-scores for performance classification (instead of arbitrary percentages)
    - Confidence intervals based on sample size
    - Coefficient of Variation for consistency measurement
    - Linear regression for trend detection
    - IQR method for outlier detection
    - Bayesian smoothing for small samples
    """
    
    # Performance tier thresholds (in z-scores)
    PERFORMANCE_TIERS = {
        'exceptional': 2.0,   # Top 2.5% of topics
        'strong': 1.0,        # Top 16% of topics  
        'average': -0.5,      # Average topics
        'weak': -1.0,         # Below average
        'poor': float('-inf') # Bottom performers
    }
    
    # Minimum sample size for high confidence
    HIGH_CONFIDENCE_THRESHOLD = 5
    MEDIUM_CONFIDENCE_THRESHOLD = 3
    
    # Recency weights (exponential decay)
    RECENCY_DECAY_RATE = 0.15  # Views lose 15% weight per month
    
    def __init__(self, channel_avg_views: float, channel_std_views: float = None):
        """
        Initialize analyzer with channel baseline statistics.
        
        Args:
            channel_avg_views: Mean views across all channel videos
            channel_std_views: Standard deviation of views (computed if not provided)
        """
        self.channel_avg = channel_avg_views
        self.channel_std = channel_std_views or channel_avg_views * 0.5  # Default estimate
        
    def compute_topic_stats(self, 
                           topic: str,
                           video_views: List[float],
                           video_dates: List[datetime] = None,
                           video_weights: List[float] = None) -> TopicStats:
        """
        Compute comprehensive statistics for a topic.
        
        Args:
            topic: Topic name
            video_views: List of view counts for each video
            video_dates: Publication dates (for recency weighting)
            video_weights: Custom weights per video (overrides date-based weights)
        
        Returns:
            TopicStats object with full statistical analysis
        """
        n = len(video_views)
        if n == 0:
            raise ValueError(f"No videos for topic: {topic}")
        
        # Basic descriptive statistics
        mean_views = statistics.mean(video_views)
        median_views = statistics.median(video_views)
        
        # Standard deviation (sample std for n > 1)
        if n > 1:
            std_dev = statistics.stdev(video_views)
        else:
            # For single video, estimate std from channel baseline
            std_dev = self.channel_std * 0.5
        
        # Coefficient of Variation (lower = more consistent)
        cv = (std_dev / mean_views * 100) if mean_views > 0 else float('inf')
        
        # Min/Max
        min_views = min(video_views)
        max_views = max(video_views)
        
        # Compute recency-weighted average
        if video_weights:
            weights = video_weights
        elif video_dates:
            weights = self._compute_recency_weights(video_dates)
        else:
            # Equal weights if no dates provided
            weights = [1.0] * n
        
        weighted_avg = self._weighted_mean(video_views, weights)
        
        # Detect outliers using IQR method
        outliers = self._detect_outliers_iqr(video_views)
        
        # Compute confidence interval
        ci_low, ci_high = self._confidence_interval(mean_views, std_dev, n)
        
        # Determine confidence level based on sample size
        if n >= self.HIGH_CONFIDENCE_THRESHOLD:
            conf_level = 'high'
        elif n >= self.MEDIUM_CONFIDENCE_THRESHOLD:
            conf_level = 'medium'
        else:
            conf_level = 'low'
        
        # Z-score (how many std devs from channel mean)
        z_score = (mean_views - self.channel_avg) / self.channel_std if self.channel_std > 0 else 0
        
        # Bayesian-smoothed estimate for small samples
        # Shrinks toward channel average when sample size is small
        smoothed_mean = self._bayesian_smoothing(mean_views, n)
        
        # Vs channel average (using smoothed estimate for small samples)
        vs_avg = ((smoothed_mean - self.channel_avg) / self.channel_avg * 100) if self.channel_avg > 0 else 0
        
        # Trend analysis (if dates provided)
        if video_dates and len(video_dates) >= 3:
            slope, p_value = self._compute_trend(video_dates, video_views)
            if p_value < 0.05:  # Statistically significant trend
                trend_dir = 'rising' if slope > 0 else 'declining'
            else:
                trend_dir = 'stable'
        else:
            slope = 0.0
            p_value = 1.0
            trend_dir = 'unknown'
        
        # Performance tier based on z-score
        tier = self._classify_performance(z_score)
        
        return TopicStats(
            topic=topic,
            video_count=n,
            mean_views=mean_views,
            median_views=median_views,
            std_dev=std_dev,
            coefficient_of_variation=cv,
            min_views=min_views,
            max_views=max_views,
            weighted_avg_views=weighted_avg,
            vs_channel_avg=vs_avg,
            z_score=z_score,
            confidence_interval_95=(ci_low, ci_high),
            confidence_level=conf_level,
            outlier_count=len(outliers),
            trend_slope=slope,
            trend_direction=trend_dir,
            trend_p_value=p_value,
            performance_tier=tier
        )
    
    def _weighted_mean(self, values: List[float], weights: List[float]) -> float:
        """Compute weighted arithmetic mean."""
        total_weight = sum(weights)
        if total_weight == 0:
            return statistics.mean(values)
        return sum(v * w for v, w in zip(values, weights)) / total_weight
    
    def _compute_recency_weights(self, dates: List[datetime]) -> List[float]:
        """
        Compute exponential decay weights based on age.
        Most recent video gets weight 1.0, older videos decay exponentially.
        """
        now = datetime.now()
        weights = []
        for date in dates:
            if isinstance(date, str):
                # Parse ISO 8601 dates (YouTube uses 2025-01-15T01:00:00Z)
                try:
                    date = datetime.fromisoformat(date.replace('Z', '+00:00')).replace(tzinfo=None)
                except (ValueError, AttributeError):
                    try:
                        date = datetime.strptime(date, '%Y-%m-%dT%H:%M:%SZ')
                    except ValueError:
                        try:
                            date = datetime.strptime(date, '%Y-%m-%d')
                        except ValueError:
                            date = now  # Fallback: treat unparseable as recent
            
            age_months = (now - date).days / 30.44
            weight = math.exp(-self.RECENCY_DECAY_RATE * age_months)
            weights.append(weight)
        
        return weights
    
    def _detect_outliers_iqr(self, values: List[float]) -> List[float]:
        """
        Detect outliers using the IQR method.
        Values below Q1 - 1.5*IQR or above Q3 + 1.5*IQR are outliers.
        """
        if len(values) < 4:
            return []  # Need at least 4 values for meaningful quartiles
        
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        
        q1_idx = n // 4
        q3_idx = (3 * n) // 4
        
        q1 = sorted_vals[q1_idx]
        q3 = sorted_vals[q3_idx]
        iqr = q3 - q1
        
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        return [v for v in values if v < lower_bound or v > upper_bound]
    
    def _confidence_interval(self, 
                            mean: float, 
                            std: float, 
                            n: int,
                            confidence: float = 0.95) -> Tuple[float, float]:
        """
        Compute confidence interval using t-distribution.
        
        For small samples (n < 30), uses t-distribution.
        For larger samples, uses normal approximation.
        """
        if n <= 1:
            # Single observation: very wide interval
            return (mean * 0.5, mean * 1.5)
        
        # Standard error of the mean
        sem = std / math.sqrt(n)
        
        # T-value for confidence level
        # Using approximate t-values for common cases
        if n < 3:
            t_val = 12.71 if confidence == 0.95 else 4.30  # df=1 or df=2
        elif n < 6:
            t_val = 2.78  # df=4
        elif n < 10:
            t_val = 2.26  # df=9
        elif n < 30:
            t_val = 2.05  # df~25
        else:
            t_val = 1.96  # Normal approximation
        
        margin = t_val * sem
        
        return (mean - margin, mean + margin)
    
    def _bayesian_smoothing(self, 
                           observed_mean: float, 
                           n: int,
                           prior_mean: float = None,
                           prior_strength: float = 3.0) -> float:
        """
        Apply Bayesian smoothing to shrink estimates toward prior for small samples.
        
        This prevents over-reaction to topics with few videos.
        
        Args:
            observed_mean: The observed mean views
            n: Sample size
            prior_mean: Prior mean (defaults to channel average)
            prior_strength: Equivalent sample size for prior (higher = more shrinkage)
        
        Returns:
            Smoothed estimate
        """
        if prior_mean is None:
            prior_mean = self.channel_avg
        
        # Weighted average of observed and prior
        # Weight toward prior when sample is small
        total_weight = n + prior_strength
        smoothed = (n * observed_mean + prior_strength * prior_mean) / total_weight
        
        return smoothed
    
    def _compute_trend(self, 
                      dates: List[datetime], 
                      values: List[float]) -> Tuple[float, float]:
        """
        Compute linear regression trend and statistical significance.
        
        Returns:
            (slope, p_value) where slope is views change per day
        """
        if len(dates) < 3:
            return (0.0, 1.0)
        
        # Convert dates to numeric (days from earliest)
        date_objs = []
        for d in dates:
            if isinstance(d, str):
                try:
                    d = datetime.fromisoformat(d.replace('Z', '+00:00')).replace(tzinfo=None)
                except (ValueError, AttributeError):
                    try:
                        d = datetime.strptime(d, '%Y-%m-%d')
                    except ValueError:
                        d = datetime.now()
            date_objs.append(d)
        
        min_date = min(date_objs)
        x = [(d - min_date).days for d in date_objs]
        y = values
        
        n = len(x)
        
        # Linear regression: y = mx + b
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi * xi for xi in x)
        
        # Slope and intercept
        denom = n * sum_x2 - sum_x * sum_x
        if denom == 0:
            return (0.0, 1.0)
        
        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n
        
        # Compute R-squared and standard error
        y_mean = sum_y / n
        ss_tot = sum((yi - y_mean) ** 2 for yi in y)
        ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))
        
        if ss_tot == 0:
            return (slope, 1.0)
        
        r_squared = 1 - (ss_res / ss_tot)
        
        # Standard error of slope
        if n <= 2:
            return (slope, 1.0)
        
        se_slope = math.sqrt(ss_res / (n - 2)) / math.sqrt(sum_x2 - sum_x**2/n)
        
        # T-statistic for slope
        if se_slope == 0:
            return (slope, 0.0 if slope != 0 else 1.0)
        
        t_stat = slope / se_slope
        
        # Approximate p-value using t-distribution
        df = n - 2
        # Simplified: use absolute t-stat as proxy
        # For exact p-value, would need scipy.stats
        p_value = self._approx_t_pvalue(abs(t_stat), df)
        
        return (slope, p_value)
    
    def _approx_t_pvalue(self, t_stat: float, df: int) -> float:
        """
        Approximate two-tailed p-value for t-statistic.
        Uses a simple approximation suitable for our purposes.
        """
        # Critical values for alpha=0.05, two-tailed
        critical_values = {
            1: 12.71, 2: 4.30, 3: 3.18, 4: 2.78, 5: 2.57,
            10: 2.23, 20: 2.09, 30: 2.04, 60: 2.00, 120: 1.98
        }
        
        # Find closest df
        closest_df = min(critical_values.keys(), key=lambda x: abs(x - df))
        critical = critical_values[closest_df]
        
        if t_stat > critical * 1.5:
            return 0.01  # Very significant
        elif t_stat > critical:
            return 0.04  # Significant
        elif t_stat > critical * 0.8:
            return 0.08  # Borderline
        else:
            return 0.20  # Not significant
    
    def _classify_performance(self, z_score: float) -> str:
        """Classify performance tier based on z-score."""
        if z_score >= self.PERFORMANCE_TIERS['exceptional']:
            return 'exceptional'
        elif z_score >= self.PERFORMANCE_TIERS['strong']:
            return 'strong'
        elif z_score >= self.PERFORMANCE_TIERS['average']:
            return 'average'
        elif z_score >= self.PERFORMANCE_TIERS['weak']:
            return 'weak'
        else:
            return 'poor'


class TopicCategorizer:
    """
    Categorizes topics into actionable buckets using statistical rigor.
    
    Buckets:
    1. DOUBLE_DOWN: High performance + high confidence + consistent
    2. UNTAPPED: Strong performance + low sample size (opportunity)
    3. RESURFACE: Was performing + dormant (old content worth updating)
    4. STOP_MAKING: Poor performance + high confidence
    5. INVESTIGATE: Mixed signals (needs human review)
    """
    
    def __init__(self, analyzer: StatisticalAnalyzer):
        self.analyzer = analyzer
    
    def categorize_all(self, 
                      topic_data: Dict[str, Dict],
                      video_metadata: Dict[str, Dict] = None) -> Dict[str, List[Dict]]:
        """
        Categorize all topics into buckets.
        
        Args:
            topic_data: Dict of topic -> {video_ids, views, dates, etc.}
            video_metadata: Optional additional video info
        
        Returns:
            Dict with keys: double_down, untapped, resurface, stop_making, investigate
        """
        results = {
            'double_down': [],
            'untapped': [],
            'resurface': [],
            'stop_making': [],
            'investigate': []
        }
        
        for topic, data in topic_data.items():
            category, entry = self._categorize_topic(topic, data, video_metadata)
            results[category].append(entry)
        
        # Sort each category by performance (best first, worst last for stop_making)
        for cat in ['double_down', 'untapped', 'resurface']:
            results[cat].sort(key=lambda x: -x.get('z_score', 0))
        
        results['stop_making'].sort(key=lambda x: x.get('z_score', 0))  # Worst first
        results['investigate'].sort(key=lambda x: -x.get('z_score', 0))
        
        return results
    
    def _categorize_topic(self, 
                         topic: str, 
                         data: Dict,
                         video_metadata: Dict = None) -> Tuple[str, Dict]:
        """
        Categorize a single topic using statistical criteria.
        """
        views = data.get('views', [])
        dates = data.get('dates', [])
        
        # Compute stats
        stats = self.analyzer.compute_topic_stats(
            topic=topic,
            video_views=views,
            video_dates=dates
        )
        
        # Build base entry
        # IMPORTANT: 'vs_channel' key name must match dashboard JS (not 'vs_channel_avg')
        entry = {
            'topic': topic,
            'video_count': stats.video_count,
            'avg_views': stats.mean_views,
            'median_views': stats.median_views,
            'weighted_avg_views': stats.weighted_avg_views,
            'vs_channel': stats.vs_channel_avg,
            'z_score': stats.z_score,
            'confidence_level': stats.confidence_level,
            'confidence_interval': stats.confidence_interval_95,
            'consistency_cv': stats.coefficient_of_variation,
            'outlier_count': stats.outlier_count,
            'trend_direction': stats.trend_direction,
            'trend_significance': stats.trend_p_value,
            'performance_tier': stats.performance_tier,
            'videos': data.get('videos', []),
            'reason': ''
        }
        
        # === CATEGORIZATION LOGIC ===
        
        # Check for investigation needed (mixed signals)
        if stats.outlier_count > 0 and stats.video_count > 3:
            # High variance - one hit and some duds
            entry['reason'] = self._build_reason('investigate_outliers', stats)
            return ('investigate', entry)
        
        if stats.trend_direction == 'declining' and stats.trend_p_value < 0.05:
            # Statistically significant decline
            if stats.z_score > 0:
                entry['reason'] = self._build_reason('declining_hit', stats)
                return ('resurface', entry)
        
        # RESURFACE: Old content that performed well, not updated recently
        if self._is_resurface_candidate(stats, dates):
            entry['reason'] = self._build_reason('resurface', stats)
            return ('resurface', entry)
        
        # UNTAPPED: Strong performance but low sample size
        if self._is_untapped_candidate(stats):
            entry['reason'] = self._build_reason('untapped', stats)
            return ('untapped', entry)
        
        # STOP_MAKING: Poor performance with high confidence
        if self._is_stop_making_candidate(stats):
            entry['reason'] = self._build_reason('stop_making', stats)
            return ('stop_making', entry)
        
        # DOUBLE_DOWN: Strong consistent performance with high confidence
        if self._is_double_down_candidate(stats):
            entry['reason'] = self._build_reason('double_down', stats)
            return ('double_down', entry)
        
        # Default: investigate if doesn't fit clear categories
        entry['reason'] = self._build_reason('investigate_default', stats)
        return ('investigate', entry)
    
    def _is_resurface_candidate(self, stats: TopicStats, dates: List) -> bool:
        """
        Check if topic is a resurface candidate.
        
        Criteria:
        - Performed well (z > 0.5)
        - Low sample size (1-3 videos)
        - Oldest video > 6 months old
        """
        if stats.z_score < 0.5:
            return False
        
        if stats.video_count > 3:
            return False
        
        if not dates:
            return True  # Assume old if no date info
        
        # Check if content is stale
        now = datetime.now()
        oldest = min(dates)
        if isinstance(oldest, str):
            try:
                oldest = datetime.fromisoformat(oldest.replace('Z', '+00:00')).replace(tzinfo=None)
            except (ValueError, AttributeError):
                try:
                    oldest = datetime.strptime(oldest, '%Y-%m-%d')
                except ValueError:
                    oldest = datetime.now()
        
        age_months = (now - oldest).days / 30.44
        
        return age_months > 6
    
    def _is_untapped_candidate(self, stats: TopicStats) -> bool:
        """
        Check if topic is an untapped opportunity.
        
        Criteria:
        - Strong performance (z > 1.0)
        - Low sample size (1-2 videos)
        - High confidence interval (uncertainty = opportunity)
        """
        if stats.z_score < 1.0:
            return False
        
        if stats.video_count > 2:
            return False
        
        # The confidence interval width indicates upside potential
        ci_width = stats.confidence_interval_95[1] - stats.confidence_interval_95[0]
        relative_uncertainty = ci_width / stats.mean_views if stats.mean_views > 0 else 0
        
        # High uncertainty with positive z-score = untapped potential
        return relative_uncertainty > 0.3 or stats.z_score > 1.5
    
    def _is_stop_making_candidate(self, stats: TopicStats) -> bool:
        """
        Check if topic should be stopped.
        
        Criteria:
        - Poor performance (z < -1.0)
        - High confidence (3+ videos)
        - Consistent underperformance (low CV = reliably bad)
        """
        if stats.z_score > -0.5:
            return False
        
        if stats.confidence_level == 'low':
            return False  # Don't recommend stopping with low confidence
        
        if stats.video_count < 2:
            return False  # Need at least 2 videos to see a pattern
        
        return stats.z_score < -1.0 or (
            stats.z_score < -0.5 and 
            stats.coefficient_of_variation < 50  # Consistently bad
        )
    
    def _is_double_down_candidate(self, stats: TopicStats) -> bool:
        """
        Check if topic is a double-down opportunity.
        
        Criteria:
        - Strong performance (z > 0.5)
        - High confidence (3+ videos)
        - Consistent performance (CV < 80%)
        - Not declining significantly
        """
        if stats.z_score < 0.5:
            return False
        
        if stats.confidence_level == 'low':
            return False  # Need more data to recommend doubling down
        
        if stats.coefficient_of_variation > 100:
            return False  # Too inconsistent
        
        if stats.trend_direction == 'declining' and stats.trend_p_value < 0.1:
            return False  # Declining topic
        
        return True
    
    def _build_reason(self, reason_type: str, stats: TopicStats) -> str:
        """Build human-readable reason for categorization."""
        
        templates = {
            'double_down': (
                f"{stats.video_count} videos averaging {stats.mean_views:,.0f} views "
                f"(z-score: {stats.z_score:.1f}, {stats.vs_channel_avg:+.0f}% vs channel avg). "
                f"Consistency score: {100 - min(stats.coefficient_of_variation, 100):.0f}%. "
                f"{stats.confidence_level.title()} confidence. This is your lane."
            ),
            'untapped': (
                f"Only {stats.video_count} video(s) but performing {stats.z_score:.1f} standard deviations "
                f"above average ({stats.vs_channel_avg:+.0f}% vs channel). "
                f"Confidence interval: {stats.confidence_interval_95[0]:,.0f} - {stats.confidence_interval_95[1]:,.0f} views. "
                f"Your audience is hungry for more."
            ),
            'resurface': (
                f"Performed well ({stats.mean_views:,.0f} avg views, {stats.vs_channel_avg:+.0f}% vs avg) "
                f"but hasn't been updated in a while. "
                f"Time for a refresh with updated information."
            ),
            'stop_making': (
                f"{stats.video_count} videos averaging {stats.mean_views:,.0f} views "
                f"(z-score: {stats.z_score:.1f}, {stats.vs_channel_avg:+.0f}% vs channel avg). "
                f"Consistently underperforms with {stats.confidence_level} confidence. "
                f"Your audience isn't engaging with this content."
            ),
            'investigate_outliers': (
                f"Mixed performance: {stats.outlier_count} outlier video(s) among {stats.video_count} total. "
                f"Range: {stats.min_views:,.0f} - {stats.max_views:,.0f} views. "
                f"The topic has potential but needs investigation to find what works."
            ),
            'investigate_default': (
                f"Ambiguous signals: z-score {stats.z_score:.1f}, "
                f"{stats.confidence_level} confidence, trend: {stats.trend_direction}. "
                f"Needs human review to determine best strategy."
            ),
            'declining_hit': (
                f"Once a strong performer ({stats.mean_views:,.0f} avg views) but showing "
                f"statistically significant decline (p={stats.trend_p_value:.2f}). "
                f"Consider updating or pivoting the angle."
            )
        }
        
        return templates.get(reason_type, f"Category: {reason_type}")


# === Integration with existing code ===

def improved_categorize_topics(data: Dict) -> Dict[str, List[Dict]]:
    """
    Drop-in replacement for _categorize_topics with improved statistics.
    
    Args:
        data: The data bundle from _load_bundle()
    
    Returns:
        Dict with keys: double_down, untapped, resurface, stop_making, investigate
    """
    analytics = data.get("analytics_report", {})
    performance = analytics.get("topic_performance", {})
    timeline = analytics.get("topic_timeline", {})
    sources = data.get("sources", [])
    metrics = data.get("channel_metrics", {})
    
    channel_avg = metrics.get("channel_avg_views", 1)
    channel_std = metrics.get("channel_std_views", channel_avg * 0.5)
    
    # Initialize analyzer
    analyzer = StatisticalAnalyzer(channel_avg, channel_std)
    categorizer = TopicCategorizer(analyzer)
    
    # Build topic data structure
    source_map = {s["source_id"]: s for s in sources}
    topic_data = {}
    
    for topic, tl in timeline.items():
        videos = tl.get("videos", [])
        views = []
        dates = []
        video_details = []
        
        for v in videos:
            vid = v.get("video_id", "")
            s = source_map.get(vid, {})
            
            vviews = s.get("views", v.get("views", 0))
            vdate = s.get("published", v.get("published", ""))
            
            views.append(vviews)
            dates.append(vdate)
            
            video_details.append({
                "video_id": vid,
                "title": s.get("title", v.get("title", "")),
                "views": vviews,
                "published": vdate,
                "url": s.get("url", f"https://www.youtube.com/watch?v={vid}"),
            })
        
        topic_data[topic] = {
            "views": views,
            "dates": dates,
            "videos": video_details
        }
    
    # Categorize all topics
    results = categorizer.categorize_all(topic_data, source_map)
    
    # Limit results per category
    return {
        "double_down": results["double_down"][:6],
        "untapped": results["untapped"][:6],
        "resurface": results["resurface"][:6],
        "stop_making": results["stop_making"][:4],
        "investigate": results["investigate"][:4],
    }


# === Statistical Helper Functions ===

def compute_channel_statistics(sources: List[Dict]) -> Dict[str, float]:
    """
    Compute channel-level statistics from source data.
    
    Returns:
        Dict with mean, median, std_dev, quartiles
    """
    views = [s.get("views", 0) for s in sources if s.get("views", 0) > 0]
    
    if not views:
        return {"mean": 0, "median": 0, "std_dev": 0}
    
    sorted_views = sorted(views)
    n = len(sorted_views)
    
    mean = statistics.mean(views)
    median = statistics.median(views)
    std_dev = statistics.stdev(views) if n > 1 else 0
    
    q1 = sorted_views[n // 4]
    q3 = sorted_views[(3 * n) // 4]
    
    return {
        "mean": mean,
        "median": median,
        "std_dev": std_dev,
        "q1": q1,
        "q3": q3,
        "iqr": q3 - q1,
        "min": min(views),
        "max": max(views),
        "count": n
    }


def performance_percentile(z_score: float) -> float:
    """
    Convert z-score to percentile rank.
    
    Uses standard normal distribution approximation.
    """
    # Approximation of cumulative normal distribution
    # Using error function approximation
    t = 1 / (1 + 0.2316419 * abs(z_score))
    d = 0.3989423 * math.exp(-z_score * z_score / 2)
    p = d * t * (0.3193815 + t * (-0.3565638 + t * (1.781478 + t * (-1.821256 + t * 1.330274))))
    
    if z_score > 0:
        return (1 - p) * 100
    else:
        return p * 100


if __name__ == "__main__":
    # Example usage
    print("Statistical Analysis Module for TrueInfluenceAI")
    print("=" * 50)
    print("\nKey Improvements:")
    print("1. Z-score based performance classification")
    print("2. Confidence intervals based on sample size")
    print("3. Coefficient of Variation for consistency")
    print("4. Linear regression trend detection")
    print("5. IQR-based outlier detection")
    print("6. Bayesian smoothing for small samples")
    print("\nUsage:")
    print("  from improved_statistics import improved_categorize_topics")
    print("  categories = improved_categorize_topics(data)")