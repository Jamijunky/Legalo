from __future__ import annotations

import math
import re
from collections import Counter

from .corpus import Chunk
from .schemas import SourceRef

TOKEN = re.compile(r"[\w]+", re.UNICODE)


def tokenize(text: str) -> list[str]:
    return [t.lower() for t in TOKEN.findall(text or "") if len(t) > 1]


class LexicalIndex:
    """In-process BM25-style index. Always available; pgvector is an optional overlay."""

    def __init__(self, chunks: list[Chunk], k1: float = 1.5, b: float = 0.75):
        self.chunks = chunks
        self.k1 = k1
        self.b = b
        self.doc_tokens = [tokenize(c.searchable) for c in chunks]
        self.doc_len = [len(toks) or 1 for toks in self.doc_tokens]
        self.avgdl = sum(self.doc_len) / max(len(self.doc_len), 1)
        df: Counter[str] = Counter()
        for toks in self.doc_tokens:
            df.update(set(toks))
        n = max(len(chunks), 1)
        self.idf = {t: math.log((n - f + 0.5) / (f + 0.5) + 1) for t, f in df.items()}

    def search(self, query: str, k: int = 6, doc_ids: set[str] | None = None) -> list[tuple[Chunk, float]]:
        q = tokenize(query)
        if not q:
            return []
        scored: list[tuple[int, float]] = []
        for i, toks in enumerate(self.doc_tokens):
            if doc_ids and self.chunks[i].doc_id not in doc_ids:
                continue
            tf = Counter(toks)
            score = 0.0
            dl = self.doc_len[i]
            for term in q:
                if term not in tf:
                    continue
                idf = self.idf.get(term, 0.0)
                freq = tf[term]
                denom = freq + self.k1 * (1 - self.b + self.b * dl / self.avgdl)
                score += idf * (freq * (self.k1 + 1) / denom)
            if score > 0:
                scored.append((i, score))
        scored.sort(key=lambda x: x[1], reverse=True)
        return [(self.chunks[i], s) for i, s in scored[:k]]


def to_source_ref(chunk: Chunk, procedural_stale_days: int) -> SourceRef:
    doc = chunk.document
    age_days = (doc.retrieved_on - doc.published_on).days
    stale = bool(doc.stale_procedural) or (
        doc.doc_type in {"portal_help", "circular", "form", "rules"} and age_days > procedural_stale_days
    )
    return SourceRef(
        chunk_id=chunk.id,
        doc_id=doc.id,
        title=doc.title,
        publisher=doc.publisher,
        section=chunk.section,
        source_url=doc.source_url,
        published_on=doc.published_on.isoformat(),
        effective_on=doc.effective_on.isoformat(),
        retrieved_on=doc.retrieved_on.isoformat(),
        doc_type=doc.doc_type,
        stale_procedural=stale,
        state_law_may_differ=doc.state_law_may_differ,
        notes=doc.notes,
    )
