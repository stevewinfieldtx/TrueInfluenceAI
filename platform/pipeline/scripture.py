"""
TrueInfluenceAI - Scripture Detection Engine
==============================================
Detects and indexes scripture references in creator transcripts.

Supports multiple religious traditions via pluggable profiles:
  - Christian (Bible: 66 books, OT + NT)
  - Latter-day Saints (Bible + Book of Mormon + D&C + Pearl of Great Price)
  - (Future: Islam, Judaism, Hinduism, Buddhism)

Pipeline integration:
  Called after chunking, before embedding.
  Adds `scriptures` field to each chunk.
  Outputs scripture_index.json to the bundle.

Usage:
  from pipeline.scripture import detect_scriptures, build_scripture_index

  # During ingest, after chunking:
  chunks = detect_scriptures(chunks, tradition="christian")
  scripture_index = build_scripture_index(chunks)
"""

import os
import re
import json
from pathlib import Path
from abc import ABC, abstractmethod
from typing import Dict, List, Tuple, Optional
from collections import defaultdict

import requests

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL_ID = os.getenv("OPENROUTER_MODEL_ID", "anthropic/claude-sonnet-4-20250514")


# ═══════════════════════════════════════════════════════════════
# Base Tradition Profile
# ═══════════════════════════════════════════════════════════════

class TraditionProfile(ABC):
    """
    Base class for religious tradition scripture detection.

    To add a new tradition:
      1. Subclass TraditionProfile
      2. Define BOOKS dict mapping canonical name -> abbreviations
      3. Define citation_patterns() returning regex patterns
      4. Register in TRADITION_REGISTRY at bottom of file
    """

    name: str = "base"
    display_name: str = "Base"

    # Subclasses define: { "Canonical Name": ["abbrev1", "abbrev2", ...] }
    BOOKS: Dict[str, List[str]] = {}

    def citation_patterns(self) -> List[re.Pattern]:
        """Return compiled regex patterns that match scripture citations."""
        patterns = []
        all_names = []
        for canonical, abbrevs in self.BOOKS.items():
            escaped = [re.escape(a) for a in [canonical] + abbrevs]
            all_names.extend(escaped)

        if not all_names:
            return []

        # Sort longest first so "1 Corinthians" matches before "1 Cor"
        all_names.sort(key=len, reverse=True)
        book_pattern = "|".join(all_names)

        # Match: Book Chapter:Verse (with optional verse ranges)
        # Examples: John 3:16, 1 Cor 13:4-7, Genesis 1:1-3, Psalm 23
        patterns.append(re.compile(
            rf'\b({book_pattern})\s+'           # Book name
            rf'(\d{{1,3}})'                     # Chapter
            rf'(?:\s*:\s*(\d{{1,3}})'           # :Verse (optional)
            rf'(?:\s*[-–—]\s*(\d{{1,3}}))?)?'   # -EndVerse (optional)
            , re.IGNORECASE
        ))

        # Match chapter-only references: "Psalm 23", "Proverbs 31"
        patterns.append(re.compile(
            rf'\b({book_pattern})\s+(\d{{1,3}})\b'
            rf'(?!\s*:\s*\d)',  # Negative lookahead: no :verse following
            re.IGNORECASE
        ))

        return patterns

    def normalize_reference(self, book: str, chapter: str,
                            verse_start: str = None,
                            verse_end: str = None) -> str:
        """Normalize a detected reference to canonical format."""
        canonical = self._to_canonical(book.strip())
        ref = f"{canonical} {chapter}"
        if verse_start:
            ref += f":{verse_start}"
            if verse_end:
                ref += f"-{verse_end}"
        return ref

    def _to_canonical(self, name: str) -> str:
        """Map any abbreviation or variant to canonical book name."""
        name_lower = name.lower().strip().rstrip(".")
        for canonical, abbrevs in self.BOOKS.items():
            if name_lower == canonical.lower():
                return canonical
            for a in abbrevs:
                if name_lower == a.lower().rstrip("."):
                    return canonical
        return name  # Return as-is if no match

    @abstractmethod
    def llm_detection_prompt(self) -> str:
        """Return the LLM prompt suffix for detecting paraphrased references."""
        pass

    def tradition_context(self) -> str:
        """Return context string for LLM about this tradition's texts."""
        book_list = ", ".join(list(self.BOOKS.keys())[:20])
        return f"Tradition: {self.display_name}. Canonical texts include: {book_list}..."


# ═══════════════════════════════════════════════════════════════
# Christian Profile (Bible: 66 books)
# ═══════════════════════════════════════════════════════════════

class ChristianProfile(TraditionProfile):
    name = "christian"
    display_name = "Christian (Bible)"

    BOOKS = {
        # Old Testament
        "Genesis": ["Gen", "Ge", "Gn"],
        "Exodus": ["Exod", "Ex", "Exo"],
        "Leviticus": ["Lev", "Le", "Lv"],
        "Numbers": ["Num", "Nu", "Nm", "Nb"],
        "Deuteronomy": ["Deut", "Dt", "De"],
        "Joshua": ["Josh", "Jos", "Jsh"],
        "Judges": ["Judg", "Jdg", "Jg", "Jdgs"],
        "Ruth": ["Rth", "Ru"],
        "1 Samuel": ["1 Sam", "1 Sa", "1Sam", "1Sa"],
        "2 Samuel": ["2 Sam", "2 Sa", "2Sam", "2Sa"],
        "1 Kings": ["1 Kgs", "1 Ki", "1Kings", "1Ki"],
        "2 Kings": ["2 Kgs", "2 Ki", "2Kings", "2Ki"],
        "1 Chronicles": ["1 Chr", "1 Ch", "1Chron", "1Chr"],
        "2 Chronicles": ["2 Chr", "2 Ch", "2Chron", "2Chr"],
        "Ezra": ["Ezr", "Ez"],
        "Nehemiah": ["Neh", "Ne"],
        "Esther": ["Esth", "Es", "Est"],
        "Job": ["Jb"],
        "Psalms": ["Ps", "Psa", "Psm", "Psalm"],
        "Proverbs": ["Prov", "Pr", "Prv"],
        "Ecclesiastes": ["Eccl", "Ec", "Ecc"],
        "Song of Solomon": ["Song", "SOS", "Song of Songs", "Sg", "Sol"],
        "Isaiah": ["Isa", "Is"],
        "Jeremiah": ["Jer", "Je", "Jr"],
        "Lamentations": ["Lam", "La"],
        "Ezekiel": ["Ezek", "Eze", "Ezk"],
        "Daniel": ["Dan", "Da", "Dn"],
        "Hosea": ["Hos", "Ho"],
        "Joel": ["Joe", "Jl"],
        "Amos": ["Am"],
        "Obadiah": ["Obad", "Ob"],
        "Jonah": ["Jon", "Jnh"],
        "Micah": ["Mic", "Mc"],
        "Nahum": ["Nah", "Na"],
        "Habakkuk": ["Hab", "Hb"],
        "Zephaniah": ["Zeph", "Zep", "Zp"],
        "Haggai": ["Hag", "Hg"],
        "Zechariah": ["Zech", "Zec", "Zc"],
        "Malachi": ["Mal", "Ml"],
        # New Testament
        "Matthew": ["Matt", "Mt"],
        "Mark": ["Mrk", "Mk", "Mr"],
        "Luke": ["Luk", "Lk"],
        "John": ["Jn", "Jhn"],
        "Acts": ["Act", "Ac"],
        "Romans": ["Rom", "Ro", "Rm"],
        "1 Corinthians": ["1 Cor", "1 Co", "1Cor", "1Co"],
        "2 Corinthians": ["2 Cor", "2 Co", "2Cor", "2Co"],
        "Galatians": ["Gal", "Ga"],
        "Ephesians": ["Eph", "Ep"],
        "Philippians": ["Phil", "Php", "Pp"],
        "Colossians": ["Col", "Co"],
        "1 Thessalonians": ["1 Thess", "1 Th", "1Thess", "1Th"],
        "2 Thessalonians": ["2 Thess", "2 Th", "2Thess", "2Th"],
        "1 Timothy": ["1 Tim", "1 Ti", "1Tim", "1Ti"],
        "2 Timothy": ["2 Tim", "2 Ti", "2Tim", "2Ti"],
        "Titus": ["Tit", "Ti"],
        "Philemon": ["Phlm", "Phm"],
        "Hebrews": ["Heb"],
        "James": ["Jas", "Jm"],
        "1 Peter": ["1 Pet", "1 Pe", "1Pet", "1Pe"],
        "2 Peter": ["2 Pet", "2 Pe", "2Pet", "2Pe"],
        "1 John": ["1 Jn", "1 Jhn", "1Jn", "1John"],
        "2 John": ["2 Jn", "2 Jhn", "2Jn", "2John"],
        "3 John": ["3 Jn", "3 Jhn", "3Jn", "3John"],
        "Jude": ["Jud", "Jd"],
        "Revelation": ["Rev", "Re", "Rv"],
    }

    def llm_detection_prompt(self) -> str:
        return """You are a Bible scripture detection expert.

Given a transcript chunk from a Christian content creator, identify ALL scripture references including:
1. EXPLICIT references: "John 3:16 says...", "In Romans 8:28..."
2. PARAPHRASED quotes: "For God so loved the world..." (= John 3:16)
3. ALLUSIONS: "We know all things work together for good..." (= Romans 8:28)
4. THEMATIC references: "As Paul wrote to the Corinthians about love..." (= 1 Corinthians 13)

For each reference found, return:
- reference: The canonical citation (e.g., "John 3:16")
- type: "explicit", "paraphrase", "allusion", or "thematic"
- quote_snippet: The exact words from the transcript that triggered detection (max 20 words)"""


# ═══════════════════════════════════════════════════════════════
# Latter-day Saints Profile (Bible + BoM + D&C + PoGP)
# ═══════════════════════════════════════════════════════════════

class LDSProfile(ChristianProfile):
    """
    Extends Christian profile with LDS-specific scriptures.
    Inherits all 66 Bible books and adds:
      - Book of Mormon (15 books)
      - Doctrine and Covenants (D&C)
      - Pearl of Great Price (Moses, Abraham, JS-History, JS-Matthew, AoF)
    """
    name = "lds"
    display_name = "Latter-day Saints"

    # Start with all Bible books from parent
    BOOKS = {**ChristianProfile.BOOKS}

    # Book of Mormon
    BOOKS.update({
        "1 Nephi": ["1 Ne", "1Ne", "1 Nep"],
        "2 Nephi": ["2 Ne", "2Ne", "2 Nep"],
        "Jacob": ["Jac"],
        "Enos": [],
        "Jarom": [],
        "Omni": [],
        "Words of Mormon": ["W of M", "WofM"],
        "Mosiah": ["Mos"],
        "Alma": [],
        "Helaman": ["Hel"],
        "3 Nephi": ["3 Ne", "3Ne", "3 Nep"],
        "4 Nephi": ["4 Ne", "4Ne", "4 Nep"],
        "Mormon": ["Morm", "Morm."],
        "Ether": ["Eth"],
        "Moroni": ["Moro", "Mni"],
    })

    # Doctrine and Covenants
    BOOKS.update({
        "Doctrine and Covenants": ["D&C", "DC", "D and C", "D & C", "Doctrine & Covenants"],
    })

    # Pearl of Great Price
    BOOKS.update({
        "Moses": ["Mos."],
        "Abraham": ["Abr"],
        "Joseph Smith—History": ["JS-H", "JSH", "JS—H", "JS History", "Joseph Smith History"],
        "Joseph Smith—Matthew": ["JS-M", "JSM", "JS—M", "JS Matthew"],
        "Articles of Faith": ["AoF", "A of F"],
    })

    def llm_detection_prompt(self) -> str:
        return """You are a Latter-day Saint scripture detection expert.

Given a transcript chunk from an LDS content creator, identify ALL scripture references from:
- The Bible (Old and New Testament)
- The Book of Mormon (1 Nephi through Moroni)
- Doctrine and Covenants (D&C sections)
- Pearl of Great Price (Moses, Abraham, JS-History, JS-Matthew, Articles of Faith)

Include:
1. EXPLICIT references: "In 1 Nephi 3:7 it says...", "D&C 89 tells us..."
2. PARAPHRASED quotes: "I will go and do the things which the Lord hath commanded..." (= 1 Nephi 3:7)
3. ALLUSIONS: "The Word of Wisdom teaches us..." (= D&C 89)
4. THEMATIC references: "As Moroni promised at the end of the Book of Mormon..." (= Moroni 10:4-5)
5. GENERAL CONFERENCE quotes that reference specific scriptures

For each reference found, return:
- reference: The canonical citation (e.g., "1 Nephi 3:7", "D&C 89:1")
- type: "explicit", "paraphrase", "allusion", or "thematic"
- quote_snippet: The exact words from the transcript that triggered detection (max 20 words)"""


# ═══════════════════════════════════════════════════════════════
# Tradition Registry — add new traditions here
# ═══════════════════════════════════════════════════════════════

TRADITION_REGISTRY: Dict[str, type] = {
    "christian": ChristianProfile,
    "lds": LDSProfile,
    # Future:
    # "islam": IslamProfile,
    # "judaism": JudaismProfile,
    # "hinduism": HinduismProfile,
    # "buddhism": BuddhismProfile,
}


def get_tradition(name: str) -> TraditionProfile:
    """Get a tradition profile by name."""
    cls = TRADITION_REGISTRY.get(name.lower())
    if not cls:
        available = ", ".join(TRADITION_REGISTRY.keys())
        raise ValueError(f"Unknown tradition '{name}'. Available: {available}")
    return cls()


def list_traditions() -> List[Dict[str, str]]:
    """List all available traditions."""
    return [
        {"id": k, "name": v.display_name}
        for k, v in TRADITION_REGISTRY.items()
    ]


# ═══════════════════════════════════════════════════════════════
# Scripture Detection Pipeline
# ═══════════════════════════════════════════════════════════════

def _regex_detect(text: str, profile: TraditionProfile) -> List[Dict]:
    """Fast regex pass to find explicit scripture references."""
    found = []
    seen = set()

    for pattern in profile.citation_patterns():
        for match in pattern.finditer(text):
            groups = match.groups()
            book = groups[0] if groups[0] else ""
            chapter = groups[1] if len(groups) > 1 and groups[1] else ""
            verse_start = groups[2] if len(groups) > 2 and groups[2] else None
            verse_end = groups[3] if len(groups) > 3 and groups[3] else None

            if not book or not chapter:
                continue

            ref = profile.normalize_reference(book, chapter, verse_start, verse_end)

            if ref not in seen:
                seen.add(ref)
                # Get surrounding context (±30 chars)
                start = max(0, match.start() - 30)
                end = min(len(text), match.end() + 30)
                snippet = text[start:end].strip()

                found.append({
                    "reference": ref,
                    "type": "explicit",
                    "snippet": snippet,
                    "match": match.group(0),
                })

    return found


def _llm_detect(text: str, profile: TraditionProfile,
                already_found: List[str] = None) -> List[Dict]:
    """
    LLM pass to find paraphrased quotes and allusions.
    Only called on chunks where context suggests scripture content.
    """
    if not OPENROUTER_API_KEY:
        return []

    already_str = ", ".join(already_found or [])
    prompt = f"""{profile.llm_detection_prompt()}

ALREADY DETECTED (by regex, skip these): {already_str or "None"}

TRANSCRIPT CHUNK:
\"\"\"{text[:2000]}\"\"\"

Return ONLY a JSON array. If no additional references found, return [].
Example:
[
  {{"reference": "Romans 8:28", "type": "paraphrase", "quote_snippet": "all things work together for good"}},
  {{"reference": "Jeremiah 29:11", "type": "allusion", "quote_snippet": "plans to prosper you and not to harm you"}}
]

Return ONLY valid JSON array. No markdown, no explanation."""

    try:
        resp = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENROUTER_MODEL_ID,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.1,
                "max_tokens": 500,
            },
            timeout=30,
        )
        resp.raise_for_status()
        text_resp = resp.json()["choices"][0]["message"]["content"].strip()

        # Clean markdown fences
        if text_resp.startswith("```"):
            text_resp = text_resp.split("```json")[-1].split("```")[0] if "```json" in text_resp else text_resp.split("```")[1].split("```")[0]

        results = json.loads(text_resp.strip())
        if isinstance(results, list):
            # Normalize references through the profile
            for r in results:
                ref = r.get("reference", "")
                # Try to parse and re-normalize
                parts = ref.rsplit(" ", 1)
                if len(parts) == 2:
                    book_part, chv = parts
                    chv_parts = chv.split(":")
                    ch = chv_parts[0]
                    vs = chv_parts[1] if len(chv_parts) > 1 else None
                    ve = None
                    if vs and "-" in vs:
                        vs, ve = vs.split("-", 1)
                    r["reference"] = profile.normalize_reference(book_part, ch, vs, ve)
            return results
        return []
    except Exception as e:
        print(f"      Scripture LLM detection error: {e}")
        return []


def _should_llm_scan(text: str, profile: TraditionProfile) -> bool:
    """Quick heuristic: does this chunk likely contain scripture content?"""
    indicators = [
        "verse", "scripture", "bible", "chapter", "says in",
        "word of god", "gospel", "lord says", "god says",
        "it is written", "as it says", "the book of",
        "paul wrote", "jesus said", "moses said", "prophet",
        "commandment", "psalm", "proverb", "parable",
    ]
    # LDS-specific indicators
    if profile.name == "lds":
        indicators.extend([
            "book of mormon", "doctrine and covenants", "d&c",
            "pearl of great price", "nephi", "moroni", "alma",
            "general conference", "elder", "president nelson",
            "restoration", "latter-day", "celestial",
        ])

    text_lower = text.lower()
    return any(ind in text_lower for ind in indicators)


def detect_scriptures(chunks: List[Dict], tradition: str = "christian",
                      use_llm: bool = True) -> List[Dict]:
    """
    Main entry point: detect scripture references in all chunks.

    Args:
        chunks: List of chunk dicts (must have 'text' and 'chunk_id')
        tradition: Tradition profile name
        use_llm: Whether to use LLM for paraphrase detection (costs API calls)

    Returns:
        Same chunks list with 'scriptures' field added to each chunk
    """
    profile = get_tradition(tradition)
    total_refs = 0
    llm_scanned = 0

    print(f"Scripture detection: {profile.display_name} ({len(chunks)} chunks)")

    for i, chunk in enumerate(chunks):
        text = chunk.get("text", "")
        if not text:
            chunk["scriptures"] = []
            continue

        # Pass 1: Regex (fast, free)
        refs = _regex_detect(text, profile)

        # Pass 2: LLM (slower, costs tokens — only if chunk looks scriptural)
        if use_llm and _should_llm_scan(text, profile):
            already = [r["reference"] for r in refs]
            llm_refs = _llm_detect(text, profile, already)
            # Deduplicate
            existing = {r["reference"] for r in refs}
            for lr in llm_refs:
                if lr.get("reference") not in existing:
                    refs.append({
                        "reference": lr["reference"],
                        "type": lr.get("type", "paraphrase"),
                        "snippet": lr.get("quote_snippet", ""),
                    })
            llm_scanned += 1

        chunk["scriptures"] = refs
        total_refs += len(refs)

        if (i + 1) % 50 == 0:
            print(f"   [{i+1}/{len(chunks)}] {total_refs} references found ({llm_scanned} LLM scans)")

    print(f"   Scripture detection complete: {total_refs} references across {len(chunks)} chunks ({llm_scanned} LLM scans)")
    return chunks


# ═══════════════════════════════════════════════════════════════
# Scripture Index Builder
# ═══════════════════════════════════════════════════════════════

def build_scripture_index(chunks: List[Dict],
                          sources: List[Dict] = None) -> Dict:
    """
    Build a searchable scripture index from tagged chunks.

    Returns:
        {
            "index": {
                "John 3:16": {
                    "count": 5,
                    "chunks": [
                        {"chunk_id": "...", "video_id": "...", "type": "explicit",
                         "snippet": "...", "video_title": "..."}
                    ]
                }
            },
            "stats": {
                "total_references": 142,
                "unique_verses": 87,
                "most_referenced": [("Romans 8:28", 8), ("John 3:16", 6), ...],
                "books_referenced": {"John": 23, "Romans": 18, ...},
                "testament_split": {"old": 45, "new": 97},
            }
        }
    """
    source_map = {}
    if sources:
        source_map = {s["source_id"]: s for s in sources}

    index = defaultdict(lambda: {"count": 0, "chunks": []})
    book_counts = defaultdict(int)
    total_refs = 0

    for chunk in chunks:
        scriptures = chunk.get("scriptures", [])
        for ref_data in scriptures:
            ref = ref_data.get("reference", "")
            if not ref:
                continue

            vid = chunk.get("video_id", "")
            s = source_map.get(vid, {})

            index[ref]["count"] += 1
            index[ref]["chunks"].append({
                "chunk_id": chunk.get("chunk_id", ""),
                "video_id": vid,
                "video_title": s.get("title", ""),
                "video_url": s.get("url", ""),
                "type": ref_data.get("type", "explicit"),
                "snippet": ref_data.get("snippet", ""),
                "timestamp": chunk.get("timestamp", 0),
            })

            # Track book-level counts
            book = ref.rsplit(" ", 1)[0] if " " in ref else ref
            book_counts[book] += 1
            total_refs += 1

    # Sort by most referenced
    most_referenced = sorted(
        [(ref, data["count"]) for ref, data in index.items()],
        key=lambda x: -x[1]
    )

    # Testament split (rough: OT books before Matthew)
    OT_BOOKS = {
        "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
        "Joshua", "Judges", "Ruth", "1 Samuel", "2 Samuel",
        "1 Kings", "2 Kings", "1 Chronicles", "2 Chronicles",
        "Ezra", "Nehemiah", "Esther", "Job", "Psalms", "Proverbs",
        "Ecclesiastes", "Song of Solomon", "Isaiah", "Jeremiah",
        "Lamentations", "Ezekiel", "Daniel", "Hosea", "Joel",
        "Amos", "Obadiah", "Jonah", "Micah", "Nahum", "Habakkuk",
        "Zephaniah", "Haggai", "Zechariah", "Malachi",
    }
    ot_count = sum(c for b, c in book_counts.items() if b in OT_BOOKS)
    nt_count = total_refs - ot_count  # Everything else (NT + BoM + D&C etc)

    return {
        "index": dict(index),
        "stats": {
            "total_references": total_refs,
            "unique_verses": len(index),
            "most_referenced": most_referenced[:20],
            "books_referenced": dict(book_counts),
            "testament_split": {"old_testament": ot_count, "new_testament_and_other": nt_count},
        },
    }


# ═══════════════════════════════════════════════════════════════
# Bundle Integration
# ═══════════════════════════════════════════════════════════════

def process_bundle_scriptures(bundle_dir, tradition: str = "christian",
                               use_llm: bool = True):
    """
    Full scripture processing for an existing bundle.
    Reads chunks.json, detects scriptures, saves scripture_index.json.
    Updates chunks.json with scripture tags.

    Args:
        bundle_dir: Path to bundle directory
        tradition: Religious tradition profile name
        use_llm: Use LLM for paraphrase detection
    """
    bundle_dir = Path(bundle_dir)
    chunks_path = bundle_dir / "chunks.json"
    sources_path = bundle_dir / "sources.json"

    if not chunks_path.exists():
        print(f"No chunks.json found in {bundle_dir}")
        return

    chunks = json.loads(chunks_path.read_text(encoding="utf-8"))
    sources = json.loads(sources_path.read_text(encoding="utf-8")) if sources_path.exists() else []

    # Detect scriptures
    chunks = detect_scriptures(chunks, tradition=tradition, use_llm=use_llm)

    # Build index
    scripture_index = build_scripture_index(chunks, sources)

    # Save updated chunks (with scripture tags)
    chunks_path.write_text(
        json.dumps(chunks, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Save scripture index
    (bundle_dir / "scripture_index.json").write_text(
        json.dumps(scripture_index, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    # Update manifest
    manifest_path = bundle_dir / "manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["scripture_tradition"] = tradition
        manifest["scripture_stats"] = scripture_index["stats"]
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    stats = scripture_index["stats"]
    print(f"   Scripture index saved: {stats['total_references']} references, "
          f"{stats['unique_verses']} unique verses")
    if stats["most_referenced"]:
        top3 = ", ".join(f"{r[0]} ({r[1]}x)" for r in stats["most_referenced"][:3])
        print(f"   Top referenced: {top3}")


# ═══════════════════════════════════════════════════════════════
# Template: Adding a New Tradition
# ═══════════════════════════════════════════════════════════════
#
# class IslamProfile(TraditionProfile):
#     name = "islam"
#     display_name = "Islam (Quran & Hadith)"
#
#     BOOKS = {
#         "Al-Fatiha": ["Fatiha", "Al-Fatihah"],
#         "Al-Baqarah": ["Baqarah"],
#         # ... all 114 surahs ...
#         # Hadith collections:
#         "Sahih Bukhari": ["Bukhari"],
#         "Sahih Muslim": ["Muslim"],
#         "Sunan Abu Dawud": ["Abu Dawud"],
#         # etc.
#     }
#
#     def citation_patterns(self) -> List[re.Pattern]:
#         patterns = super().citation_patterns()
#         # Add Quran-specific: "Quran 2:255", "Surah 2, Ayah 255"
#         patterns.append(re.compile(
#             r'\b(?:Quran|Qur\'?an)\s+(\d{1,3})\s*:\s*(\d{1,3})',
#             re.IGNORECASE
#         ))
#         patterns.append(re.compile(
#             r'\bSurah\s+(\d{1,3})(?:\s*,?\s*(?:Ayah|Ayat|verse)\s+(\d{1,3}))?',
#             re.IGNORECASE
#         ))
#         return patterns
#
#     def llm_detection_prompt(self) -> str:
#         return """You are a Quranic and Hadith reference detection expert..."""
#
#
# # Register it:
# TRADITION_REGISTRY["islam"] = IslamProfile


if __name__ == "__main__":
    print("Scripture Detection Engine for TrueInfluenceAI")
    print("=" * 50)
    print(f"\nAvailable traditions:")
    for t in list_traditions():
        print(f"  - {t['id']}: {t['name']}")

    # Quick test
    profile = get_tradition("christian")
    test = "Jesus said in John 3:16 that God so loved the world. Paul reminds us in Romans 8:28 that all things work together."
    refs = _regex_detect(test, profile)
    print(f"\nTest detection ({len(refs)} refs found):")
    for r in refs:
        print(f"  {r['reference']} ({r['type']})")