import requests
key = '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'
models = [
    'openai/text-embedding-3-small',
    'openai/text-embedding-3-large', 
    'openai/text-embedding-ada-002',
]
results = []
for m in models:
    r = requests.post('https://openrouter.ai/api/v1/embeddings',
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        json={'model': m, 'input': 'hello world'},
        timeout=10)
    ok = r.status_code == 200 and 'data' in r.text
    results.append(f'{m}: {r.status_code} {"OK" if ok else r.text[:100]}')

with open(r'C:\Users\steve\Documents\TrueInfluenceAI\embed_test.txt', 'w') as f:
    f.write('\n'.join(results))
