from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(Path(r'C:\Users\steve\Documents\TruePlatformAI\.env'))
load_dotenv(Path(r'C:\Users\steve\Documents\.env'))

key = os.getenv('OPENROUTER_API_KEY', '')
with open(r'C:\Users\steve\Documents\TrueInfluenceAI\keycheck.txt', 'w') as f:
    f.write(f'KEY LENGTH: {len(key)}\n')
    f.write(f'KEY START: {key[:20]}...\n' if len(key) > 20 else f'KEY: {key}\n')
    f.write(f'KEY SET: {bool(key)}\n')
    
    # Quick test the key
    import requests
    r = requests.post('https://openrouter.ai/api/v1/embeddings',
        headers={'Authorization': f'Bearer {key}', 'Content-Type': 'application/json'},
        json={'model': 'openai/text-embedding-3-small', 'input': 'test'},
        timeout=10)
    f.write(f'STATUS: {r.status_code}\n')
    f.write(f'RESPONSE: {r.text[:200]}\n')
