from __future__ import annotations

"""Optional pgvector overlay. Lexical BM25 is the default retrieval path so
local `uvicorn` works with zero infrastructure. When DATABASE_URL is set this
module can persist chunk metadata for operators."""

SCHEMA = """
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS legalo_chunks (
  id TEXT PRIMARY KEY,
  doc_id TEXT NOT NULL,
  section TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT NOT NULL,
  published_on DATE NOT NULL,
  effective_on DATE NOT NULL,
  retrieved_on DATE NOT NULL,
  source_url TEXT NOT NULL,
  embedding vector(768)
);
"""
