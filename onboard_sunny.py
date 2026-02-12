"""
Onboard Sunny Lenarduzzi - Last 12 Months
============================================
Scans her YouTube channel, ingests videos from the past year,
runs temporal-weighted analysis, and outputs dashboard data.
"""

import requests
import json
import time
import sys
import io

# Fix Windows encoding for redirected output
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

API = "http://localhost:8100/api/v1"
COLLECTION_ID = "sunny"
CHANNEL_URL = "https://www.youtube.com/@SunnyLenarduzzi"

def api_post(path, data=None):
    r = requests.post(f"{API}{path}", json=data or {}, timeout=300)
    r.raise_for_status()
    return r.json()

def api_get(path, params=None):
    r = requests.get(f"{API}{path}", params=params, timeout=120)
    r.raise_for_status()
    return r.json()

def main():
    print("\n" + "="*60)
    print("  🚀 ONBOARDING: Sunny Lenarduzzi")
    print("  Last 12 months of YouTube content")
    print("="*60)

    # 1. Create collection
    print("\n  📁 Creating collection...")
    try:
        col = api_post("/collections", {
            "collection_id": COLLECTION_ID,
            "template_id": "creator",
            "name": "Sunny Lenarduzzi",
            "description": "YouTube creator - last 12 months analysis",
            "metadata": {"channel_url": CHANNEL_URL}
        })
        print(f"  ✅ Created: {col.get('name')}")
    except Exception as e:
        if "409" in str(e) or "already exists" in str(e).lower():
            print(f"  ⏭️ Collection exists, continuing...")
        else:
            print(f"  ❌ {e}")
            return

    # 2. Start channel ingestion (last 12 months = grab up to 100 videos, 
    #    the temporal analyzer will weight them properly)
    print(f"\n  📺 Starting channel scan: {CHANNEL_URL}")
    print(f"     Max videos: 100 (temporal weighting will handle recency)")
    
    try:
        result = api_post(f"/collections/{COLLECTION_ID}/ingest/youtube-channel", {
            "channel_url": CHANNEL_URL,
            "max_videos": 100,
            "min_duration": 60,
        })
        job_id = result.get("job_id")
        print(f"  ✅ Ingestion job started: {job_id}")
    except Exception as e:
        print(f"  ❌ Channel ingestion failed: {e}")
        return

    # 3. Poll job progress
    if job_id:
        print(f"\n  ⏳ Ingesting videos (caption-first, this may take a few minutes)...\n")
        start = time.time()
        last_completed = 0
        
        while True:
            try:
                job = api_get(f"/jobs/{job_id}")
                status = job.get("status", "unknown")
                progress = job.get("progress", 0)
                completed = job.get("completed", 0)
                total = job.get("total", 0)
                errors = job.get("errors", 0)
                elapsed = int(time.time() - start)
                
                if completed != last_completed:
                    print(f"  [{elapsed:>4}s] {status:<12} {progress:>5.1f}% | {completed}/{total} videos | {errors} errors")
                    last_completed = completed
                
                if status in ("complete", "error", "failed"):
                    break
                    
                time.sleep(8)
                
            except Exception as e:
                print(f"  ⚠️ Poll error: {e}")
                time.sleep(10)
        
        elapsed = int(time.time() - start)
        print(f"\n  ✅ Ingestion complete in {elapsed}s")
        print(f"     Videos: {completed}/{total} | Errors: {errors}")

    # 4. Check stats
    print(f"\n  📊 Collection stats...")
    stats = api_get(f"/collections/{COLLECTION_ID}/stats")
    print(f"     Sources: {stats.get('ready_sources')}")
    print(f"     Chunks:  {stats.get('chunk_count')}")
    print(f"     Hours:   {stats.get('total_duration_hours')}")

    # 5. Run analysis
    print(f"\n  🧠 Running temporal-weighted analysis...")
    try:
        api_post(f"/collections/{COLLECTION_ID}/analyze")
    except Exception as e:
        print(f"  ⚠️ Analysis start: {e}")

    # Poll for analysis results
    print(f"  ⏳ Waiting for analysis to complete...")
    for attempt in range(30):
        time.sleep(10)
        try:
            analysis = api_get(f"/collections/{COLLECTION_ID}/analysis")
            if analysis and analysis.get("topics"):
                print(f"\n  ✅ ANALYSIS COMPLETE!")
                
                # === TEMPORAL TRENDS ===
                trends = analysis.get("temporal_trends", {})
                
                print(f"\n  {'='*60}")
                print(f"  📈 CURRENT FOCUS (time-weighted)")
                print(f"  {'='*60}")
                
                current = analysis.get("current_focus", [])
                if current:
                    print(f"  Top topics RIGHT NOW: {', '.join(current[:8])}")
                
                # Show surging/rising
                surging = trends.get("surging_topics", [])
                rising = trends.get("rising_topics", [])
                if surging:
                    print(f"\n  🔥 SURGING:")
                    for t in surging[:5]:
                        print(f"    → {t['topic']} (velocity: {t['velocity']:.1f}/month)")
                if rising:
                    print(f"\n  📈 RISING:")
                    for t in rising[:5]:
                        print(f"    → {t['topic']} (score: {t['trend_score']:.0f})")
                
                new_topics = trends.get("new_topics", [])
                if new_topics:
                    print(f"\n  🆕 NEW (only appeared recently):")
                    for t in new_topics[:5]:
                        print(f"    → {t['topic']} (first: {t['first_seen']}, {t['recent_chunks']} chunks)")
                
                # Show declining/abandoned
                declining = trends.get("declining_topics", [])
                dormant = trends.get("dormant_topics", [])
                abandoned = trends.get("abandoned_topics", [])
                
                if declining:
                    print(f"\n  📉 DECLINING:")
                    for t in declining[:5]:
                        print(f"    → {t['topic']} (last: {t['last_seen']})")
                if dormant:
                    print(f"\n  💤 DORMANT (6+ months silent):")
                    for t in dormant[:5]:
                        print(f"    → {t['topic']} (was {t['historical']:.0f}% of content, last: {t['last_seen']})")
                if abandoned:
                    print(f"\n  ❌ ABANDONED (1+ year, was significant):")
                    for t in abandoned[:5]:
                        print(f"    → {t['topic']} (was {t['historical']:.0f}% of content, last: {t['last_seen']})")
                
                # Focus shifts
                shifts = analysis.get("focus_shifts", [])
                if shifts:
                    print(f"\n  🔄 FOCUS SHIFTS (pivots detected):")
                    for s in shifts[:5]:
                        print(f"    → {s.get('from_topic')} → {s.get('to_topic')}")
                        print(f"      {s.get('description', '')[:100]}")
                
                # === TOPIC TABLE ===
                topics = analysis.get("topics", [])
                if topics:
                    print(f"\n  {'='*60}")
                    print(f"  📊 ALL TOPICS (sorted by CURRENT weighted coverage)")
                    print(f"  {'='*60}")
                    print(f"  {'TOPIC':<28} {'NOW':>6} {'HIST':>6} {'TREND':<10} {'LAST SEEN':<12} {'CHUNKS':>6}")
                    print(f"  {'─'*28} {'─'*6} {'─'*6} {'─'*10} {'─'*12} {'─'*6}")
                    for t in topics[:25]:
                        name = t.get("topic", "?")[:27]
                        now = t.get("coverage_score", 0)
                        hist = t.get("historical_coverage", 0)
                        trend = t.get("trend", "?")
                        last = t.get("last_seen", "?")[:10]
                        chunks = t.get("chunk_count", 0)
                        
                        # Trend emoji
                        emoji = {"surging": "🔥", "rising": "📈", "new": "🆕",
                                 "stable": "➡️", "declining": "📉", 
                                 "dormant": "💤", "abandoned": "❌"}.get(trend, "?")
                        
                        print(f"  {name:<28} {now:>5.1f}% {hist:>5.1f}% {emoji} {trend:<8} {last:<12} {chunks:>6}")
                
                # === GAPS ===
                gaps = analysis.get("gap_map", {})
                if gaps:
                    print(f"\n  {'='*60}")
                    print(f"  ⚠️ CONTENT GAPS (time-weighted)")
                    print(f"  {'='*60}")
                    for topic, score in list(gaps.items())[:10]:
                        bar = "█" * int(score / 5) + "░" * (20 - int(score / 5))
                        print(f"  {bar} {score:>5.0f}% {topic}")
                
                # === INSIGHTS ===
                insights = analysis.get("insights", [])
                if insights:
                    print(f"\n  {'='*60}")
                    print(f"  💡 AI INSIGHTS")
                    print(f"  {'='*60}")
                    for i, ins in enumerate(insights, 1):
                        pri = ins.get("priority", "?")
                        typ = ins.get("type", "?")
                        title = ins.get("title", "")
                        desc = ins.get("description", "")
                        action = ins.get("action", "")
                        print(f"\n  {i}. [{pri.upper()}|{typ}] {title}")
                        if desc:
                            print(f"     {desc[:120]}")
                        if action:
                            print(f"     → {action[:120]}")
                
                # === TONE ===
                tone = analysis.get("tone_distribution", {})
                if tone:
                    print(f"\n  🎨 TONE DISTRIBUTION (text-based only):")
                    for t, pct in sorted(tone.items(), key=lambda x: -x[1]):
                        bar = "█" * int(pct / 3)
                        print(f"    {bar} {pct:>5.1f}% {t}")
                
                # Save full analysis to file
                out_path = r"C:\Users\steve\Documents\TrueInfluenceAI\sunny_analysis.json"
                with open(out_path, "w") as f:
                    json.dump(analysis, f, indent=2)
                print(f"\n  💾 Full analysis saved: {out_path}")
                
                print(f"\n  {'='*60}")
                print(f"  ✅ SUNNY LENARDUZZI - ONBOARDING COMPLETE")
                print(f"  {'='*60}")
                return
                
        except Exception as e:
            pass
        
        print(f"    ... waiting ({(attempt+1)*10}s)")
    
    print(f"\n  ⚠️ Analysis timed out. Check API logs.")


if __name__ == "__main__":
    main()
