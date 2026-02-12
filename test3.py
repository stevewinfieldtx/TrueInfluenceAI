outpath = r'C:\Users\steve\Documents\TrueInfluenceAI\api_result.txt'
try:
    import requests, json
    r = requests.get('https://www.googleapis.com/youtube/v3/channels', params={
        'key': 'AIzaSyC4l9F-Fx519FTp-ipe4_0GUXQIVDZ_Do',
        'part': 'id,contentDetails',
        'forHandle': 'SunnyLenarduzzi'
    }, timeout=10)
    data = r.json()
    with open(outpath, 'w') as f:
        if 'items' in data:
            ch = data['items'][0]
            cid = ch['id']
            uploads = ch['contentDetails']['relatedPlaylists']['uploads']
            f.write(f'CHANNEL ID: {cid}\n')
            f.write(f'UPLOADS: {uploads}\n')
            r2 = requests.get('https://www.googleapis.com/youtube/v3/playlistItems', params={
                'key': 'AIzaSyC4l9F-Fx519FTp-ipe4_0GUXQIVDZ_Do',
                'part': 'contentDetails,snippet',
                'playlistId': uploads,
                'maxResults': 5
            }, timeout=10)
            vids = r2.json()
            f.write(f'VIDEOS: {len(vids.get("items",[]))}\n')
            for v in vids.get('items',[]):
                vid = v['contentDetails']['videoId']
                title = v['snippet']['title']
                f.write(f'  {vid} | {title}\n')
        else:
            f.write(f'ERROR: {json.dumps(data)}\n')
except Exception as e:
    with open(outpath, 'w') as f:
        f.write(f'CRASH: {type(e).__name__}: {e}\n')
    import traceback
    with open(outpath, 'a') as f:
        f.write(traceback.format_exc())
