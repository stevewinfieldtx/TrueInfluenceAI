"""
TrueInfluenceAI - PostgreSQL + pgvector Database
==================================================
Persistent storage for embeddings, chunks, sources, and creator metadata.
Deployed on Railway with a Postgres add-on.

Config: DATABASE_URL env var (provided automatically by Railway Postgres)

Tables:
  creators  - slug, channel name, voice profile, manifest
  sources   - video metadata per creator
  chunks    - transcript chunks with pgvector embeddings
"""

import os, json
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
from pgvector.psycopg2 import register_vector

DATABASE_URL = os.getenv("DATABASE_URL", "")

# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_conn():
    """Get a database connection. Caller must close it."""
    conn = psycopg2.connect(DATABASE_URL)
    register_vector(conn)
    return conn


@contextmanager
def db_cursor(commit=True):
    """Context manager for DB operations."""
    conn = get_conn()
    try:
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        yield cur
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

def init_db():
    """Create tables + pgvector extension. Safe to call on every startup."""
    # Step 1: Create extension using RAW connection (no register_vector yet)
    raw_conn = psycopg2.connect(DATABASE_URL)
    try:
        raw_cur = raw_conn.cursor()
        raw_cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        raw_conn.commit()
        raw_cur.close()
        print("   [DB] pgvector extension ready")
    finally:
        raw_conn.close()

    # Step 2: Create tables (MUST commit before ivfflat attempt)
    with db_cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS creators (
                slug            TEXT PRIMARY KEY,
                channel_name    TEXT NOT NULL DEFAULT '',
                channel_url     TEXT NOT NULL DEFAULT '',
                voice_profile   JSONB NOT NULL DEFAULT '{}',
                manifest        JSONB NOT NULL DEFAULT '{}',
                channel_metrics JSONB NOT NULL DEFAULT '{}',
                tradition       TEXT NOT NULL DEFAULT 'none',
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sources (
                id              SERIAL PRIMARY KEY,
                slug            TEXT NOT NULL REFERENCES creators(slug) ON DELETE CASCADE,
                video_id        TEXT NOT NULL,
                title           TEXT NOT NULL DEFAULT '',
                url             TEXT NOT NULL DEFAULT '',
                views           INTEGER NOT NULL DEFAULT 0,
                duration_text   TEXT NOT NULL DEFAULT '',
                published_text  TEXT NOT NULL DEFAULT '',
                has_transcript  BOOLEAN NOT NULL DEFAULT FALSE,
                segment_count   INTEGER NOT NULL DEFAULT 0,
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(slug, video_id)
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_sources_slug ON sources(slug);")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS chunks (
                id              SERIAL PRIMARY KEY,
                slug            TEXT NOT NULL REFERENCES creators(slug) ON DELETE CASCADE,
                chunk_id        TEXT NOT NULL,
                video_id        TEXT NOT NULL,
                text            TEXT NOT NULL DEFAULT '',
                timestamp       REAL NOT NULL DEFAULT 0,
                word_count      INTEGER NOT NULL DEFAULT 0,
                embedding       vector(4096),
                created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(slug, chunk_id)
            );
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_slug ON chunks(slug);")
    print("   [DB] Tables created")

    # Step 3: ivfflat index in SEPARATE transaction
    # If this fails (empty table), the tables above are already safely committed
    try:
        with db_cursor() as cur:
            cur.execute("""
                CREATE INDEX IF NOT EXISTS idx_chunks_embedding
                ON chunks USING ivfflat (embedding vector_cosine_ops)
                WITH (lists = 100);
            """)
        print("   [DB] ivfflat index ready")
    except Exception as e:
        print(f"   [DB] ivfflat index skipped (will auto-create when data exists): {e}")

    print("   [DB] Schema initialized")


# ---------------------------------------------------------------------------
# Creator CRUD
# ---------------------------------------------------------------------------

def upsert_creator(slug, channel_name="", channel_url="", voice_profile=None,
                   manifest=None, channel_metrics=None, tradition="none"):
    """Insert or update a creator record."""
    with db_cursor() as cur:
        cur.execute("""
            INSERT INTO creators (slug, channel_name, channel_url, voice_profile, manifest, channel_metrics, tradition, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (slug) DO UPDATE SET
                channel_name = EXCLUDED.channel_name,
                channel_url = EXCLUDED.channel_url,
                voice_profile = COALESCE(EXCLUDED.voice_profile, creators.voice_profile),
                manifest = COALESCE(EXCLUDED.manifest, creators.manifest),
                channel_metrics = COALESCE(EXCLUDED.channel_metrics, creators.channel_metrics),
                tradition = EXCLUDED.tradition,
                updated_at = NOW()
        """, (
            slug, channel_name, channel_url,
            json.dumps(voice_profile or {}),
            json.dumps(manifest or {}),
            json.dumps(channel_metrics or {}),
            tradition,
        ))


def get_creator(slug):
    """Get creator record. Returns dict or None."""
    with db_cursor(commit=False) as cur:
        cur.execute("SELECT * FROM creators WHERE slug = %s", (slug,))
        return cur.fetchone()


def update_voice_profile(slug, voice_profile):
    """Update just the voice profile for a creator."""
    with db_cursor() as cur:
        cur.execute("""
            UPDATE creators SET voice_profile = %s, updated_at = NOW()
            WHERE slug = %s
        """, (json.dumps(voice_profile), slug))


def update_channel_metrics(slug, metrics):
    """Update channel metrics for a creator."""
    with db_cursor() as cur:
        cur.execute("""
            UPDATE creators SET channel_metrics = %s, updated_at = NOW()
            WHERE slug = %s
        """, (json.dumps(metrics), slug))


# ---------------------------------------------------------------------------
# Sources CRUD
# ---------------------------------------------------------------------------

def upsert_sources(slug, sources_list):
    """Bulk upsert sources for a creator. sources_list is the sources.json array."""
    if not sources_list:
        return
    with db_cursor() as cur:
        for s in sources_list:
            cur.execute("""
                INSERT INTO sources (slug, video_id, title, url, views, duration_text, published_text, has_transcript, segment_count)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (slug, video_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    views = EXCLUDED.views,
                    published_text = EXCLUDED.published_text,
                    has_transcript = EXCLUDED.has_transcript,
                    segment_count = EXCLUDED.segment_count
            """, (
                slug,
                s.get("source_id", s.get("video_id", "")),
                s.get("title", ""),
                s.get("url", ""),
                s.get("views", 0),
                s.get("duration_text", ""),
                s.get("published_text", ""),
                s.get("has_transcript", False),
                s.get("segment_count", 0),
            ))


def get_sources(slug):
    """Get all sources for a creator."""
    with db_cursor(commit=False) as cur:
        cur.execute("SELECT * FROM sources WHERE slug = %s ORDER BY views DESC", (slug,))
        return cur.fetchall()


# ---------------------------------------------------------------------------
# Chunks CRUD + Vector Search
# ---------------------------------------------------------------------------

def store_chunks(slug, chunks_list):
    """Bulk insert chunks with embeddings. Replaces any existing chunks for this creator."""
    with db_cursor() as cur:
        # Delete existing chunks for this creator (full re-index)
        cur.execute("DELETE FROM chunks WHERE slug = %s", (slug,))

        # Batch insert
        for c in chunks_list:
            emb = c.get("embedding", [])
            if not emb:
                continue
            cur.execute("""
                INSERT INTO chunks (slug, chunk_id, video_id, text, timestamp, word_count, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
            """, (
                slug,
                c.get("chunk_id", ""),
                c.get("video_id", ""),
                c.get("text", ""),
                c.get("timestamp", 0),
                c.get("word_count", 0),
                str(emb),  # pgvector accepts string representation of array
            ))
    print(f"   [DB] Stored {len(chunks_list)} chunks for {slug}")


def add_chunks(slug, chunks_list):
    """Add chunks incrementally (for refresh/incremental update). Skips duplicates."""
    if not chunks_list:
        return
    with db_cursor() as cur:
        for c in chunks_list:
            emb = c.get("embedding", [])
            if not emb:
                continue
            cur.execute("""
                INSERT INTO chunks (slug, chunk_id, video_id, text, timestamp, word_count, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (slug, chunk_id) DO NOTHING
            """, (
                slug,
                c.get("chunk_id", ""),
                c.get("video_id", ""),
                c.get("text", ""),
                c.get("timestamp", 0),
                c.get("word_count", 0),
                str(emb),
            ))
    print(f"   [DB] Added {len(chunks_list)} chunks for {slug}")


def search_chunks(slug, query_embedding, k=5):
    """
    Vector similarity search using pgvector cosine distance.
    Returns top-k chunks with scores + source metadata.
    """
    with db_cursor(commit=False) as cur:
        cur.execute("""
            SELECT
                c.text,
                c.video_id,
                c.timestamp,
                c.chunk_id,
                1 - (c.embedding <=> %s::vector) AS score,
                s.title AS source_title,
                s.url AS source_url
            FROM chunks c
            LEFT JOIN sources s ON s.slug = c.slug AND s.video_id = c.video_id
            WHERE c.slug = %s
            ORDER BY c.embedding <=> %s::vector
            LIMIT %s
        """, (str(query_embedding), slug, str(query_embedding), k))
        rows = cur.fetchall()
        return [dict(r) for r in rows]


def get_chunk_count(slug):
    """Get the number of chunks stored for a creator."""
    with db_cursor(commit=False) as cur:
        cur.execute("SELECT COUNT(*) as cnt FROM chunks WHERE slug = %s", (slug,))
        row = cur.fetchone()
        return row["cnt"] if row else 0


# ---------------------------------------------------------------------------
# Sync from JSON bundles (migration helper)
# ---------------------------------------------------------------------------

def sync_from_bundle(slug, bundle_path):
    """
    One-time migration: read JSON files from a bundle directory
    and populate the database. Safe to run multiple times.
    """
    from pathlib import Path
    bp = Path(bundle_path)

    # Creator basics
    manifest = {}
    mp = bp / "manifest.json"
    if mp.exists():
        manifest = json.loads(mp.read_text(encoding="utf-8"))

    voice = {}
    vp = bp / "voice_profile.json"
    if vp.exists():
        voice = json.loads(vp.read_text(encoding="utf-8"))

    metrics = {}
    cm = bp / "channel_metrics.json"
    if cm.exists():
        metrics = json.loads(cm.read_text(encoding="utf-8"))

    upsert_creator(
        slug=slug,
        channel_name=manifest.get("channel", slug),
        channel_url=manifest.get("channel_url", ""),
        voice_profile=voice,
        manifest=manifest,
        channel_metrics=metrics,
    )

    # Sources
    sp = bp / "sources.json"
    if sp.exists():
        sources = json.loads(sp.read_text(encoding="utf-8"))
        upsert_sources(slug, sources)

    # Chunks
    cp = bp / "chunks.json"
    if cp.exists():
        chunks = json.loads(cp.read_text(encoding="utf-8"))
        # Only store if we don't already have chunks for this creator
        existing = get_chunk_count(slug)
        if existing == 0:
            store_chunks(slug, chunks)
            print(f"   [DB] Migrated {len(chunks)} chunks from bundle")
        else:
            print(f"   [DB] Already have {existing} chunks, skipping migration")

    print(f"   [DB] Synced {slug} from bundle")


# Alias for server.py import
sync_bundle_to_db = sync_from_bundle
