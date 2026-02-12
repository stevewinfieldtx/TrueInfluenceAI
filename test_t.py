import sys
out = open(r"C:\Users\steve\Documents\TrueInfluenceAI\test_transcript.txt", "w")
try:
    from youtube_transcript_api import YouTubeTranscriptApi
    out.write("Imported OK\n")
    out.flush()
    t = YouTubeTranscriptApi.get_transcript('fN_2c_LPfX0')
    out.write(f"OK: {len(t)} segments\n")
    out.write(f"First: {t[0]}\n")
except Exception as e:
    out.write(f"Error: {type(e).__name__}: {e}\n")
out.close()
