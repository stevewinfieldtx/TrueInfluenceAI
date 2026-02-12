import sys
print("Starting...", flush=True)
try:
    import scrapetube
    print("scrapetube imported OK", flush=True)
    videos = scrapetube.get_channel(channel_url="https://www.youtube.com/@SunnyLenarduzzi", limit=3)
    print(f"Got generator: {type(videos)}", flush=True)
    count = 0
    for v in videos:
        count += 1
        print(f"Video {count}: {v.get('videoId','?')}", flush=True)
    print(f"Done. Total: {count}", flush=True)
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}", flush=True)
