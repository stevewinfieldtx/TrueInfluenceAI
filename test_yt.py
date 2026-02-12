"""Quick test of yt-dlp channel scanning."""
import yt_dlp

url = "https://www.youtube.com/@SunnyLenarduzzi"
print(f"Testing URL: {url}")

# Test 1: extract_flat (what our code uses)
print("\n--- Test 1: extract_flat ---")
try:
    opts = {'quiet': True, 'no_warnings': True, 'extract_flat': True, 'playlistend': 5}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)
        print(f"  _type: {info.get('_type', 'NONE')}")
        print(f"  title: {info.get('title', 'NONE')}")
        print(f"  id: {info.get('id', 'NONE')}")
        entries = info.get('entries')
        if entries is None:
            print("  entries: None")
        else:
            entries = list(entries)
            print(f"  entries count: {len(entries)}")
            for e in entries[:3]:
                if e:
                    print(f"    -> {e.get('id','?')} | {e.get('title','?')[:40]} | dur={e.get('duration','?')}")
except Exception as ex:
    print(f"  ERROR: {ex}")

# Test 2: Try with /videos appended
print("\n--- Test 2: /videos URL ---")
try:
    url2 = url + "/videos"
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url2, download=False)
        print(f"  _type: {info.get('_type', 'NONE')}")
        entries = info.get('entries')
        if entries is None:
            print("  entries: None")
        else:
            entries = list(entries)
            print(f"  entries count: {len(entries)}")
            for e in entries[:3]:
                if e:
                    print(f"    -> {e.get('id','?')} | {e.get('title','?')[:40]} | dur={e.get('duration','?')}")
except Exception as ex:
    print(f"  ERROR: {ex}")

# Test 3: Try flat_playlist instead
print("\n--- Test 3: flat_playlist ---")
try:
    opts3 = {'quiet': True, 'no_warnings': True, 'flat_playlist': True, 'playlistend': 5}
    with yt_dlp.YoutubeDL(opts3) as ydl:
        info = ydl.extract_info(url, download=False)
        print(f"  _type: {info.get('_type', 'NONE')}")
        entries = info.get('entries')
        if entries is None:
            print("  entries: None")
        else:
            entries = list(entries)
            print(f"  entries count: {len(entries)}")
            for e in entries[:3]:
                if e:
                    print(f"    -> {e.get('id','?')} | {e.get('title','?')[:40]} | dur={e.get('duration','?')}")
except Exception as ex:
    print(f"  ERROR: {ex}")

print("\nDone.")
