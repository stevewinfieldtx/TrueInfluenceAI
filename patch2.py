"""Patch dashboard.py generateInsights prompt with recency bias."""
path = r"C:\Users\steve\Documents\TrueInfluenceAI\dashboard.py"
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# The file uses double-braces because it's inside a Python f-string
old = 'You are a content strategist analyzing "${{CHANNEL}}"' + "'s YouTube channel.\n\nTOPIC:"
new = ('You are a content strategist analyzing "${{CHANNEL}}"' + "'s YouTube channel.\n\n"
    "CRITICAL: Apply RECENCY BIAS. Recent content (last 6 months) reflects the creator's CURRENT direction. "
    "Older content is historical context only. If a topic is declining or dormant, respect that pivot. "
    "Do NOT recommend going back to abandoned topics unless performance data is overwhelming. "
    "Creators evolve - honor where they are NOW, not where they were.\n\nTOPIC:")

if old in content:
    content = content.replace(old, new, 1)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("[OK] Patched generateInsights prompt")
else:
    print("[!] Marker not found. Searching...")
    idx = content.find("content strategist analyzing")
    print(f"  Found at char {idx}")
    if idx > 0:
        print(f"  Context: ...{repr(content[idx:idx+120])}...")
