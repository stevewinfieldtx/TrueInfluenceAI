"""Quick caption diagnostic"""
import traceback

print("=== youtube_transcript_api version ===")
try:
    import youtube_transcript_api
    print(f"Version: {youtube_transcript_api.__version__}")
except Exception as e:
    print(f"Import failed: {e}")

print("\n=== Test: get_transcript (Rick Astley) ===")
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    t = YouTubeTranscriptApi.get_transcript('dQw4w9WgXcQ')
    print(f"SUCCESS: {len(t)} entries")
    print(f"First: {t[0]}")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")
    traceback.print_exc()

print("\n=== Test: Sunny video ===")
try:
    t = YouTubeTranscriptApi.get_transcript('Cc3ETBNDGOM')
    print(f"SUCCESS: {len(t)} entries")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")
    traceback.print_exc()
