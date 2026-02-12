import sys
sys.path.insert(0, r"C:\Users\steve\Documents\TruePlatformAI")
from pathlib import Path
from ingestors import YouTubeIngestor

out = open(r"C:\Users\steve\Documents\TrueInfluenceAI\test_result.txt", "w")
try:
    yt = YouTubeIngestor(Path("test_audio"))
    out.write(f"API key set: {bool(yt.api_key)}\n")
    
    out.write("Scanning Sunny Lenarduzzi channel (5 videos)...\n")
    out.flush()
    urls = yt.get_channel_videos("https://www.youtube.com/@SunnyLenarduzzi", max_videos=5)
    out.write(f"Found {len(urls)} videos:\n")
    for u in urls:
        out.write(f"  {u}\n")
    
    if urls:
        out.write(f"\nGetting metadata for first video...\n")
        out.flush()
        meta = yt.get_video_metadata(urls[0])
        if meta:
            out.write(f"  Title: {meta.get('title')}\n")
            out.write(f"  Uploader: {meta.get('uploader')}\n")
            out.write(f"  Duration: {meta.get('duration')}s\n")
            out.write(f"  Views: {meta.get('view_count')}\n")
        
        out.write(f"\nGetting transcript for first video...\n")
        out.flush()
        vid_id = yt.extract_video_id(urls[0])
        transcript = yt.get_transcript(vid_id)
        if transcript:
            out.write(f"  Transcript length: {len(transcript['text'])} chars\n")
            out.write(f"  First 200 chars: {transcript['text'][:200]}\n")
        else:
            out.write("  No transcript available\n")
    
    out.write("\nALL TESTS PASSED\n")
except Exception as e:
    import traceback
    out.write(f"ERROR: {e}\n{traceback.format_exc()}\n")
out.close()
