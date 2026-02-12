"""
TrueInfluenceAI - End-to-End Test
====================================
Tests the full pipeline through the TruePlatformAI API:
  1. Health check
  2. Create a creator collection
  3. Ingest YouTube videos (caption-first)
  4. Check stats
  5. Semantic search
  6. RAG chatbot Q&A
  7. Run analysis
  8. Get topics, insights, gaps

REQUIRES: TruePlatformAI API running on localhost:8100
  cd C:\\Users\\steve\\Documents\\TruePlatformAI
  py api.py

Usage:
  py test_platform.py
  py test_platform.py https://youtube.com/watch?v=VIDEO_ID
  py test_platform.py https://youtube.com/@CHANNEL_HANDLE 10

Author: Steve Winfield / WinTech Partners
"""

import sys
import json
import time
from client import TruePlatformClient

# ── Test Config ──────────────────────────────────────────────────────────

# Default test videos (short, caption-friendly)
DEFAULT_VIDEOS = [
    "https://www.youtube.com/watch?v=ZXsQAXx_ao0",  # Shia LaBeouf motivation (short)
    "https://www.youtube.com/watch?v=9bZkp7q19f0",  # PSY Gangnam Style (captions)
]

COLLECTION_ID = "test_creator"
COLLECTION_NAME = "Test Creator Channel"


def banner(text: str):
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}")


def test_health(client: TruePlatformClient) -> bool:
    banner("🏥 HEALTH CHECK")
    try:
        h = client.health()
        print(f"  Status:      {h.get('status')}")
        print(f"  OpenRouter:  {'✓' if h.get('openrouter') else '❌'}")
        print(f"  Deepgram:    {'⚡' if h.get('deepgram') else '🐢 Whisper'}")
        print(f"  Collections: {h.get('collections')}")
        print(f"  Templates:   {h.get('templates')}")
        return h.get("status") == "healthy"
    except Exception as e:
        print(f"  ❌ Cannot reach API: {e}")
        print(f"\n  START THE API FIRST:")
        print(f"    cd C:\\Users\\steve\\Documents\\TruePlatformAI")
        print(f"    py api.py")
        return False


def test_templates(client: TruePlatformClient) -> bool:
    banner("📋 TEMPLATES")
    templates = client.list_templates()
    for t in templates:
        print(f"  • {t['id']}: {t['name']}")
    return len(templates) > 0


def test_collection(client: TruePlatformClient) -> bool:
    banner("📁 CREATE COLLECTION")
    try:
        col = client.create_collection(
            COLLECTION_ID, "creator",
            name=COLLECTION_NAME,
            description="TrueInfluenceAI integration test"
        )
        print(f"  ✅ Created: {col.get('name')} (template: {col.get('template_id')})")
        return True
    except Exception as e:
        if "409" in str(e):
            print(f"  ⏭️ Collection already exists, continuing...")
            return True
        print(f"  ❌ Failed: {e}")
        return False


def test_ingest_videos(client: TruePlatformClient, urls: list) -> bool:
    banner(f"📥 INGEST {len(urls)} VIDEO(S)")
    success = 0
    for i, url in enumerate(urls, 1):
        print(f"\n  [{i}/{len(urls)}] {url[:60]}...")
        try:
            result = client.ingest_youtube(COLLECTION_ID, url)
            status = result.get("status", "unknown")
            if status == "ingesting":
                print(f"    → Background ingestion started")
                # Give it a moment for single video
                time.sleep(3)
            else:
                title = result.get("title", "N/A")
                method = result.get("metadata", {}).get("transcript_source", "?")
                print(f"    ✅ {title} (via {method})")
            success += 1
        except Exception as e:
            print(f"    ❌ {e}")

    print(f"\n  Result: {success}/{len(urls)} submitted")
    return success > 0


def test_ingest_channel(client: TruePlatformClient, channel_url: str,
                        max_videos: int) -> bool:
    banner(f"📺 INGEST CHANNEL ({max_videos} videos)")
    print(f"  Channel: {channel_url}")
    try:
        result = client.ingest_channel(COLLECTION_ID, channel_url, max_videos)
        job_id = result.get("job_id")
        print(f"  ✅ Job started: {job_id}")

        if job_id:
            print(f"\n  Waiting for completion...")
            final = client.wait_for_job(job_id, poll_interval=10, timeout=600)
            print(f"\n  Final status: {final.get('status')}")
            print(f"  Completed: {final.get('completed')}/{final.get('total')}")
            print(f"  Errors: {final.get('errors')}")
            return final.get("status") == "complete"
        return True
    except Exception as e:
        print(f"  ❌ {e}")
        return False


def test_stats(client: TruePlatformClient) -> bool:
    banner("📊 COLLECTION STATS")
    try:
        stats = client.get_stats(COLLECTION_ID)
        print(f"  Sources: {stats.get('ready_sources')}/{stats.get('source_count')}")
        print(f"  Chunks:  {stats.get('chunk_count')}")
        print(f"  Hours:   {stats.get('total_duration_hours')}")

        top = stats.get("top_topics", [])
        if top:
            print(f"\n  Top Topics (pre-analysis):")
            for topic, count in top[:8]:
                print(f"    • {topic}: {count} chunks")
        return stats.get("chunk_count", 0) > 0
    except Exception as e:
        print(f"  ❌ {e}")
        return False


def test_search(client: TruePlatformClient) -> bool:
    banner("🔍 SEMANTIC SEARCH")
    queries = [
        "main topic",
        "advice tips",
        "audience growth",
    ]
    total_found = 0
    for q in queries:
        print(f"\n  Query: \"{q}\"")
        try:
            results = client.search(COLLECTION_ID, q, top_k=3)
            total_found += len(results)
            for r in results[:2]:
                sim = r.get("similarity", 0)
                text = r.get("text", "")[:80]
                print(f"    [{sim}%] {text}...")
        except Exception as e:
            print(f"    ❌ {e}")

    return total_found > 0


def test_chatbot(client: TruePlatformClient) -> bool:
    banner("💬 RAG CHATBOT")
    questions = [
        "What is the main topic of this content?",
        "What advice is given?",
        "Summarize the key points.",
    ]
    success = 0
    for q in questions:
        print(f"\n  Q: {q}")
        try:
            result = client.ask(COLLECTION_ID, q, top_k=5)
            answer = result.get("answer", "No answer")
            confidence = result.get("confidence", 0)
            sources = len(result.get("sources", []))
            print(f"  A: {answer[:200]}...")
            print(f"     Confidence: {confidence}% | Sources: {sources}")
            success += 1
        except Exception as e:
            print(f"  ❌ {e}")

    return success > 0


def test_analyze(client: TruePlatformClient) -> bool:
    banner("🧠 ANALYSIS PIPELINE")
    try:
        result = client.analyze(COLLECTION_ID)
        print(f"  ✅ Analysis started: {result.get('status')}")

        # Wait for it
        print(f"  Waiting for analysis to complete...")
        time.sleep(5)

        # Poll for results
        for attempt in range(12):
            try:
                analysis = client.get_analysis(COLLECTION_ID)
                if analysis:
                    print(f"\n  ✅ Analysis complete!")
                    print(f"     Topics:   {len(analysis.get('topics', []))}")
                    print(f"     Insights: {len(analysis.get('insights', []))}")
                    print(f"     Gaps:     {len(analysis.get('gap_map', {}))}")

                    topics = analysis.get("topics", [])
                    if topics:
                        print(f"\n  Top Topics:")
                        for t in topics[:8]:
                            cov = t.get("coverage_score", 0)
                            cnt = t.get("chunk_count", 0)
                            name = t.get("topic", "?")
                            bar = "█" * int(cov / 5) + "░" * (20 - int(cov / 5))
                            print(f"    {bar} {cov:5.1f}% {name} ({cnt} chunks)")

                    insights = analysis.get("insights", [])
                    if insights:
                        print(f"\n  Insights:")
                        for ins in insights[:5]:
                            pri = ins.get("priority", "?")
                            typ = ins.get("type", "?")
                            title = ins.get("title", "N/A")
                            print(f"    [{pri}/{typ}] {title}")

                    gaps = analysis.get("gap_map", {})
                    if gaps:
                        print(f"\n  Content Gaps:")
                        for topic, score in list(gaps.items())[:5]:
                            print(f"    ⚠️ {topic}: {score:.0f}% gap")

                    return True
            except Exception:
                pass
            print(f"    ... waiting ({(attempt+1)*5}s)")
            time.sleep(5)

        print(f"  ⚠️ Analysis not ready after 60s. Check API logs.")
        return False
    except Exception as e:
        print(f"  ❌ {e}")
        return False


def main():
    print("\n" + "╔" + "═"*58 + "╗")
    print("║" + " TrueInfluenceAI - Platform Integration Test".center(58) + "║")
    print("║" + " Testing against TruePlatformAI API".center(58) + "║")
    print("╚" + "═"*58 + "╝")

    client = TruePlatformClient("http://localhost:8100")

    # Parse args
    urls = DEFAULT_VIDEOS
    channel_url = None
    max_channel_videos = 10

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if "/@" in arg or "/c/" in arg or "/channel/" in arg:
            channel_url = arg
            if len(sys.argv) > 2:
                max_channel_videos = int(sys.argv[2])
        else:
            urls = [arg]

    # Run tests
    results = {}

    results["Health"] = test_health(client)
    if not results["Health"]:
        print("\n  ❌ API not reachable. Exiting.")
        return

    results["Templates"] = test_templates(client)
    results["Collection"] = test_collection(client)

    if not results["Collection"]:
        return

    if channel_url:
        results["Channel Ingest"] = test_ingest_channel(
            client, channel_url, max_channel_videos
        )
    else:
        results["Video Ingest"] = test_ingest_videos(client, urls)
        # Wait for background ingestion
        print("\n  ⏳ Waiting for ingestion to complete...")
        time.sleep(15)

    results["Stats"] = test_stats(client)
    results["Search"] = test_search(client)
    results["Chatbot"] = test_chatbot(client)
    results["Analysis"] = test_analyze(client)

    # Summary
    banner("📋 TEST RESULTS")
    all_pass = True
    for name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status}  {name}")
        if not passed:
            all_pass = False

    print("\n" + ("  🎉 All tests passed!" if all_pass else "  ⚠️ Some tests failed."))
    print()


if __name__ == "__main__":
    main()
