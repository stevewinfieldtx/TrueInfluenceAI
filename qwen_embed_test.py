import requests
key = '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'
r = requests.post('https://openrouter.ai/api/v1/embeddings',
    headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
    json={'model': 'qwen/qwen3-embedding-8b', 'input': 'hello world'},
    timeout=15)
with open(r'C:\Users\steve\Documents\TrueInfluenceAI\qwen_test.txt', 'w') as f:
    f.write(f'STATUS: {r.status_code}\n')
    data = r.json()
    if 'data' in data:
        emb = data['data'][0]['embedding']
        f.write(f'DIMENSION: {len(emb)}\n')
        f.write(f'FIRST 5: {emb[:5]}\n')
        f.write('WORKING!\n')
    else:
        f.write(f'RESPONSE: {r.text[:300]}\n')
