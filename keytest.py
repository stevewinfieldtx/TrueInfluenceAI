import requests
key = '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'
r = requests.post('https://openrouter.ai/api/v1/embeddings',
    headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
    json={'model': 'openai/text-embedding-3-small', 'input': 'hello world'},
    timeout=10)
with open(r'C:\Users\steve\Documents\TrueInfluenceAI\keytest.txt', 'w') as f:
    f.write(f'STATUS: {r.status_code}\n')
    f.write(f'RESPONSE: {r.text[:300]}\n')
