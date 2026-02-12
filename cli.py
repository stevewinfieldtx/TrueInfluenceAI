"""
TrueInfluenceAI - Interactive CLI
====================================
Command-line interface for creator intelligence.

REQUIRES: TruePlatformAI API running on localhost:8100

Usage:
    py cli.py

Author: Steve Winfield / WinTech Partners
"""

import sys
import json
from app import TrueInfluenceAI


def print_help():
    print("""
  COMMANDS:
    onboard <id> <channel_url> [max_videos]  - Onboard a new creator
    videos  <id> <url1> [url2] [url3] ...    - Onboard with specific videos
    dash    <id>                              - Show dashboard
    ask     <id> <question>                   - Ask the content a question
    search  <id> <query>                      - Search content
    gaps    <id>                              - Show content gaps
    topics  <id>                              - Show top topics
    insights <id>                             - Show insights
    stats   <id>                              - Show stats
    list                                      - List all collections
    jobs    [id]                              - List jobs
    help                                      - This message
    quit                                      - Exit
""")


def main():
    print("\n╔" + "═"*58 + "╗")
    print("║" + " TrueInfluenceAI - Creator Intelligence CLI".center(58) + "║")
    print("╚" + "═"*58 + "╝")

    ti = TrueInfluenceAI()

    # Check API
    try:
        ti.client.health()
        print("  ✅ Connected to TruePlatformAI")
    except Exception:
        print("  ❌ Cannot reach TruePlatformAI API")
        print("  Start it first: cd TruePlatformAI && py api.py")
        return

    print_help()

    while True:
        try:
            raw = input("\n  TrueInfluence > ").strip()
            if not raw:
                continue

            parts = raw.split(maxsplit=2)
            cmd = parts[0].lower()

            if cmd in ("quit", "exit", "q"):
                print("  👋 Bye!")
                break

            elif cmd == "help":
                print_help()

            elif cmd == "list":
                cols = ti.client.list_collections()
                if cols:
                    for c in cols:
                        print(f"  • {c['collection_id']}: {c['name']} ({c['template_id']}) - {c.get('source_count',0)} sources")
                else:
                    print("  No collections found.")

            elif cmd == "jobs":
                cid = parts[1] if len(parts) > 1 else None
                jobs = ti.client.list_jobs(cid)
                if jobs:
                    for j in jobs[:10]:
                        print(f"  [{j['job_id']}] {j['type']} - {j['status']} {j['progress']}% ({j['completed']}/{j['total']})")
                else:
                    print("  No jobs found.")

            elif cmd == "onboard" and len(parts) >= 3:
                cid = parts[1]
                rest = parts[2].split()
                url = rest[0]
                max_v = int(rest[1]) if len(rest) > 1 else 20
                ti.onboard_channel(cid, url, name=cid, max_videos=max_v)

            elif cmd == "videos" and len(parts) >= 3:
                cid = parts[1]
                urls = parts[2].split()
                ti.onboard_videos(cid, urls, name=cid)

            elif cmd == "dash" and len(parts) >= 2:
                ti.print_dashboard(parts[1])

            elif cmd == "ask" and len(parts) >= 3:
                cid = parts[1]
                question = parts[2]
                print(ti.ask_formatted(cid, question))

            elif cmd == "search" and len(parts) >= 3:
                cid = parts[1]
                query = parts[2]
                results = ti.search_content(cid, query)
                for r in results:
                    print(f"\n  [{r['similarity']}%] {r['title']} @ {r['timestamp']}")
                    print(f"    {r['text'][:120]}...")

            elif cmd == "gaps" and len(parts) >= 2:
                gaps = ti.get_content_gaps(parts[1])
                if gaps:
                    for g in gaps[:10]:
                        opp = g["opportunity"].upper()
                        print(f"  [{opp}] {g['topic']}: {g['gap_score']:.0f}% gap (current: {g['current_coverage']:.0f}%)")
                else:
                    print("  No gaps found. Run analysis first.")

            elif cmd == "topics" and len(parts) >= 2:
                topics = ti.get_top_topics(parts[1])
                for t in topics[:15]:
                    cov = t.get("coverage_score", 0)
                    bar = "█" * int(cov / 5) + "░" * (20 - int(cov / 5))
                    print(f"  {bar} {cov:5.1f}% {t['topic']} ({t['chunk_count']} chunks)")

            elif cmd == "insights" and len(parts) >= 2:
                insights = ti.get_actionable_insights(parts[1])
                for i in insights[:10]:
                    pri = i.get("priority", "?")
                    typ = i.get("type", "?")
                    title = i.get("title", "N/A")
                    desc = i.get("description", "")
                    print(f"\n  [{pri}|{typ}] {title}")
                    if desc:
                        print(f"    {desc[:100]}")

            elif cmd == "stats" and len(parts) >= 2:
                stats = ti.client.get_stats(parts[1])
                print(json.dumps(stats, indent=2))

            else:
                print("  Unknown command. Type 'help' for options.")

        except KeyboardInterrupt:
            print("\n  👋 Bye!")
            break
        except Exception as e:
            print(f"  ❌ Error: {e}")


if __name__ == "__main__":
    main()
