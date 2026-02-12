import scrapetube

print("Scanning Sunny Lenarduzzi channel...")
videos = scrapetube.get_channel(
    channel_url="https://www.youtube.com/@SunnyLenarduzzi",
    limit=5, sort_by="newest"
)

count = 0
for v in videos:
    count += 1
    vid = v.get('videoId', '?')
    title_obj = v.get('title', {})
    if isinstance(title_obj, dict):
        runs = title_obj.get('runs', [{}])
        title = runs[0].get('text', '?') if runs else '?'
    else:
        title = str(title_obj)
    
    lt = v.get('lengthText', {})
    dur = lt.get('simpleText', '?') if isinstance(lt, dict) else '?'
    
    print(f"  {count}. [{vid}] {dur} - {title[:60]}")

print(f"\nTotal: {count} videos found")
