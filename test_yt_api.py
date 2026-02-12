import requests, json
out = []
try:
    r = requests.get('https://www.googleapis.com/youtube/v3/channels', params={
        'key': 'AIzaSyC4l9F-Fx519FTp-ipe4_0GUXQIVDZ_Do',
        'part': 'id,contentDetails',
        'forHandle': 'SunnyLenarduzzi'
    }, timeout=10)
    data = r.json()
    if 'items' in data:
        ch = data['items'][0]
        cid = ch['id']
        uploads = ch['contentDetails']['relatedPlaylists']['uploads']
        out.append(f'CHANNEL ID: {cid}')
        out.append(f'UPLOADS PLAYLIST: {uploads}')
        r2 = requests.get('https://www.googleapis.com/youtube/v3/playlistItems', params={
            'key': 'AIzaSyC4l9F-Fx519FTp-ipe4_0GUXQIVDZ_Do',
            'part': 'contentDetails,snippet',
            'playlistId': uploads,
            'maxResults': 5
        }, timeout=10)
        vids = r2.json()
        out.append(f'VIDEOS FOUND: {len(vids.get("items",[]))}')
        for v in vids.get('items',[]):
            vid = v['contentDetails']['videoId']
            title = v['snippet']['title']
            out.append(f'  {vid} | {title}')
    else:
        out.append(f'ERROR: {json.dumps(data, indent=2)}')
except Exception as e:
    out.append(f'EXCEPTION: {e}')

with open(r'C:\Users\steve\Documents\TrueInfluenceAI\api_result.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
