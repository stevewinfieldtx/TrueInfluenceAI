"""Patch dashboard.py to add recency bias to AI prompts."""
import re

path = r"C:\Users\steve\Documents\TrueInfluenceAI\dashboard.py"
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Patch 1: Add recency instruction to the main generateInsights prompt
old_marker = 'You are a content strategist analyzing "${CHANNEL}"' + "'s YouTube channel.\n\nTOPIC:"
new_marker = ('You are a content strategist analyzing "${CHANNEL}"' + "'s YouTube channel.\n\n"
    "CRITICAL: Apply RECENCY BIAS. Recent content (last 6 months) reflects the creator's CURRENT direction. "
    "Older content is historical context only. If a topic is declining or dormant, respect that pivot. "
    "Do NOT recommend going back to abandoned topics unless performance data is overwhelming. "
    "Creators evolve - honor where they are NOW, not where they were.\n\nTOPIC:")

if old_marker in content:
    content = content.replace(old_marker, new_marker, 1)
    print("[OK] Patched generateInsights prompt with recency bias")
else:
    print("[!] Could not find generateInsights prompt marker")

# Patch 2: Add recency to the Strategic Brief prompt  
old_brief = 'You are a data-driven content strategy advisor'
new_brief = ('You are a data-driven content strategy advisor (APPLY RECENCY BIAS: '
    "recent content reflects current direction, older content is historical context only)")
if old_brief in content:
    content = content.replace(old_brief, new_brief, 1)
    print("[OK] Patched Strategic Brief prompt")

# Patch 3: Add recency note to the Platform Strategy prompt
old_plat = 'You are a platform distribution strategist advising'
new_plat = ('You are a platform distribution strategist advising (RECENCY MATTERS: '
    "base strategy on creator's recent focus, not historical topics they've moved away from)")
if old_plat in content:
    content = content.replace(old_plat, new_plat, 1)
    print("[OK] Patched Platform Strategy prompt")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("\nDone. Dashboard prompts now include recency bias instructions.")
