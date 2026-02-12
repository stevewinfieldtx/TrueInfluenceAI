"""Quick test of YouTube Data API v3."""
import sys
sys.path.insert(0, r"C:\Users\steve\Documents\TruePlatformAI")
from pathlib import Path
from ingestors import YouTubeIngestor

yt = YouTubeIngestor(Path("test_audio"))
print("Testing channel scan via YouTube Data API v3...")
urls = yt.get_channel_videos("https://www.youtube.com/@SunnyLenarduzzi", max_videos=3)
print(f"\nFound {len(urls)} videos:")
for u in urls:
    print(f"  {u}")
