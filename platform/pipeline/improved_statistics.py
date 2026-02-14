"""
Improved Statistical Analysis for TrueInfluenceAI
==================================================
Provides robust statistical methods for analyzing YouTube content performance.
"""

import math
import statistics
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime

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
    Uses Z-scores, Confidence Intervals, and Linear Regression.
    """
    
    PERFORMANCE_TIERS = {
        'exceptional': 2.0,   # Top 2.5%
        'strong': 1.0,        # Top 16%
        'average': -0.5,      # Average
        'weak': -1.0,         # Below average
        'poor': float('-inf') # Bottom performers
    }
    
    HIGH_CONFIDENCE_THRESHOLD = 5
    MEDIUM_CONFIDENCE_THRESHOLD = 3
    RECENCY_DECAY_RATE = 0.15 
    
    def __init__(self, channel_avg_views: float, channel_std_views: float = None):
        self.channel_avg = channel_avg_views
        self.channel_std = channel_std_views or (channel_avg_views * 0.5)
        
    def compute_topic_stats(self, topic: str, video_views: List[float], video_dates: List[datetime] = None) -> TopicStats:
        n = len(video_views)
        if n == 0: raise ValueError(f"No videos for topic: {topic}")
        
        mean_views = statistics.mean(video_views)
        median_views = statistics.median(video_views)
        std_dev = statistics.stdev(video_views) if n > 1 else (self.channel_std * 0.5)
        cv = (std_dev / mean_views * 100) if mean_views > 0 else 0
        
        # Weighted mean
        weights = self._compute_recency_weights(video_dates) if video_dates else [1.0] * n
        total_weight = sum(weights)
        weighted_avg = sum(v * w for v, w in zip(video_views, weights)) / total_weight if total_weight > 0 else mean_views

        # Outliers & CI
        outliers = self._detect_outliers_iqr(video_views)
        ci_low, ci_high = self._confidence_interval(mean_views, std_dev, n)
        
        conf_level = 'high' if n >= self.HIGH_CONFIDENCE_THRESHOLD else 'medium' if n >= self.MEDIUM_CONFIDENCE_THRESHOLD else 'low'
        
        # Z-score & Smoothing
        z_score = (mean_views - self.channel_avg) / self.channel_std if self.channel_std > 0 else 0
        smoothed_mean = self._bayesian_smoothing(mean_views, n)
        vs_avg = ((smoothed_mean - self.channel_avg) / self.channel_avg * 100) if self.channel_avg > 0 else 0
        
        # Trend
        slope, p_value = self._compute_trend(video_dates, video_views) if video_dates and len(video_dates) >= 3 else (0.0, 1.0)
        trend_dir = 'rising' if slope > 0 and p_value < 0.1 else 'declining' if slope < 0 and p_value < 0.1 else 'stable'

        tier = self._classify_performance(z_score)
        
        return TopicStats(
            topic=topic, video_count=n, mean_views=mean_views, median_views=median_views,
            std_dev=std_dev, coefficient_of_variation=cv, min_views=min(video_views), max_views=max(video_views),
            weighted_avg_views=weighted_avg, vs_channel_avg=vs_avg, z_score=z_score,
            confidence_interval_95=(ci_low, ci_high), confidence_level=conf_level,
            outlier_count=len(outliers), trend_slope=slope, trend_direction=trend_dir,
            trend_p_value=p_value, performance_tier=tier
        )
    
    def _compute_recency_weights(self, dates: List[datetime]) -> List[float]:
        now = datetime.now()
        weights = []
        for d in dates:
            if isinstance(d, str):
                try: d = datetime.strptime(d[:10], '%Y-%m-%d')
                except: d = now
            age_months = max(0, (now - d).days / 30.44)
            weights.append(math.exp(-self.RECENCY_DECAY_RATE * age_months))
        return weights
    
    def _detect_outliers_iqr(self, values: List[float]) -> List[float]:
        if len(values) < 4: return []
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        q1 = sorted_vals[n // 4]
        q3 = sorted_vals[(3 * n) // 4]
        iqr = q3 - q1
        return [v for v in values if v < q1 - 1.5 * iqr or v > q3 + 1.5 * iqr]
    
    def _confidence_interval(self, mean: float, std: float, n: int) -> Tuple[float, float]:
        if n <= 1: return (mean * 0.5, mean * 1.5)
        sem = std / math.sqrt(n)
        t_val = 1.96 if n >= 30 else 2.26 # Simplified t-value
        return (mean - t_val * sem, mean + t_val * sem)
    
    def _bayesian_smoothing(self, observed_mean: float, n: int, prior_strength: float = 3.0) -> float:
        total_weight = n + prior_strength
        return (n * observed_mean + prior_strength * self.channel_avg) / total_weight
    
    def _compute_trend(self, dates: List[datetime], values: List[float]) -> Tuple[float, float]:
        # Simple linear regression
        if len(dates) < 3: return (0.0, 1.0)
        date_objs = []
        for d in dates:
            if isinstance(d, str):
                try: d = datetime.strptime(d[:10], '%Y-%m-%d')
                except: continue
            date_objs.append(d)
        if len(date_objs) != len(values): return (0.0, 1.0)
        
        min_date = min(date_objs)
        x = [(d - min_date).days for d in date_objs]
        y = values
        n = len(x)
        
        sum_x, sum_y = sum(x), sum(y)
        sum_xy = sum(xi*yi for xi, yi in zip(x,y))
        sum_x2 = sum(xi*xi for xi in x)
        
        denom = n * sum_x2 - sum_x * sum_x
        if denom == 0: return (0.0, 1.0)
        
        slope = (n * sum_xy - sum_x * sum_y) / denom
        
        # Simple p-value approximation based on R2
        y_mean = sum_y/n
        ss_tot = sum((yi - y_mean)**2 for yi in y)
        intercept = (sum_y - slope * sum_x) / n
        ss_res = sum((yi - (slope * xi + intercept))**2 for xi, yi in zip(x, y))
        r2 = 1 - (ss_res/ss_tot) if ss_tot > 0 else 0
        p_value = 1.0 - r2 # Very rough approximation for sorting
        
        return (slope, p_value)

    def _classify_performance(self, z_score: float) -> str:
        for tier, threshold in self.PERFORMANCE_TIERS.items():
            if z_score >= threshold: return tier
        return 'poor'


class TopicCategorizer:
    """Categorizes topics into actionable buckets using statistical rigor."""
    
    def __init__(self, analyzer: StatisticalAnalyzer):
        self.analyzer = analyzer
    
    def categorize_all(self, topic_data: Dict[str, Dict]) -> Dict[str, List[Dict]]:
        results = {k: [] for k in ['double_down', 'untapped', 'resurface', 'stop_making', 'investigate']}
        
        for topic, data in topic_data.items():
            stats = self.analyzer.compute_topic_stats(topic, data['views'], data['dates'])
            cat, entry = self._categorize_topic(stats, data['videos'])
            results[cat].append(entry)
            
        for cat in results:
            results[cat].sort(key=lambda x: -x['z_score'])
        return results
        
    def _categorize_topic(self, stats: TopicStats, videos: List) -> Tuple[str, Dict]:
        entry = {
            'topic': stats.topic,
            'video_count': stats.video_count,
            'avg_views': stats.mean_views,
            'z_score': stats.z_score,
            'confidence_level': stats.confidence_level,
            'confidence_interval': stats.confidence_interval_95,
            'consistency_cv': stats.coefficient_of_variation,
            'trend': stats.trend_direction,
            'videos': videos,
            'reason': ''
        }
        
        # CATEGORIZATION LOGIC
        if stats.outlier_count > 0 and stats.video_count > 3:
            entry['reason'] = f"Mixed signals: {stats.outlier_count} outliers. Needs review."
            return ('investigate', entry)
            
        if stats.trend_direction == 'declining' and stats.trend_p_value < 0.1 and stats.z_score > 0:
            entry['reason'] = "Was strong, but statistically declining. Pivot or refresh."
            return ('resurface', entry)
            
        if stats.z_score > 1.0 and stats.video_count <= 2:
            entry['reason'] = f"High performance (Z={stats.z_score:.1f}) on low sample size. Untapped."
            return ('untapped', entry)
            
        if stats.z_score < -0.5 and stats.confidence_level != 'low' and stats.coefficient_of_variation < 60:
            entry['reason'] = "Consistently underperforming with high confidence."
            return ('stop_making', entry)
            
        if stats.z_score > 0.5 and stats.confidence_level != 'low' and stats.trend_direction != 'declining':
            entry['reason'] = "Strong, consistent, proven performer. Own this lane."
            return ('double_down', entry)
            
        entry['reason'] = "Ambiguous data. Requires human judgment."
        return ('investigate', entry)