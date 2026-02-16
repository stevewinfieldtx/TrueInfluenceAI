"""Replace _build_js_block in build_actionable_core.py with server-side API version."""
import re

SRC = r"C:\Users\steve\Documents\TrueInfluenceAI\platform\pipeline\build_actionable_core.py"
TPL = r"C:\Users\steve\Documents\TrueInfluenceAI\write_it_template.js"

with open(SRC, "r", encoding="utf-8") as f:
    content = f.read()

with open(TPL, "r", encoding="utf-8") as f:
    js_template = f.read()

# Find start of old function
idx = content.find("def _build_js_block(")
if idx < 0:
    print("ERROR: _build_js_block not found")
    exit(1)

# Escape the template for embedding in a Python string
# Replace backslashes first, then single quotes
js_escaped = js_template.replace("\\", "\\\\").replace("'", "\\'")

new_function = f'''def _build_js_block(slug, channel, big_bet_esc):
    """Build JS that calls /api/write/{{slug}} server-side.
    ZERO API keys in the browser. All LLM calls happen on the server."""
    tpl = '{js_escaped}'
    return tpl.replace("__SLUG__", slug).replace("__CH__", channel).replace("__BIGBET__", big_bet_esc)
'''

new_content = content[:idx] + new_function

with open(SRC, "w", encoding="utf-8") as f:
    f.write(new_content)

print(f"OK: Replaced _build_js_block ({len(content)} -> {len(new_content)} chars)")
# Verify no API_KEY remains
if "API_KEY" in new_content.split("def _build_js_block")[1]:
    print("WARNING: API_KEY still found in new function!")
else:
    print("VERIFIED: No API_KEY in new function")
if "openrouter.ai" in new_content.split("def _build_js_block")[1]:
    print("WARNING: openrouter.ai still found!")
else:
    print("VERIFIED: No direct openrouter.ai calls")
