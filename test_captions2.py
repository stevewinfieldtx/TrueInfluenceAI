"""Find the new API"""
from youtube_transcript_api import YouTubeTranscriptApi
print(dir(YouTubeTranscriptApi))

# Try new v1.0 syntax
try:
    ytt = YouTubeTranscriptApi()
    result = ytt.fetch('dQw4w9WgXcQ')
    print(f"\nfetch() worked! Type: {type(result)}")
    print(f"Result: {str(result)[:300]}")
except Exception as e:
    print(f"\nfetch() failed: {e}")

try:
    ytt = YouTubeTranscriptApi()
    result = ytt.list('dQw4w9WgXcQ')
    print(f"\nlist() worked! Type: {type(result)}")
    print(f"Result: {str(result)[:300]}")
except Exception as e:
    print(f"\nlist() failed: {e}")
