from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml

from .config import settings

REQUIRED_DOC_FIELDS = (
    "id",
    "title",
    "publisher",
    "source_url",
    "doc_type",
    "jurisdiction",
    "published_on",
    "effective_on",
    "retrieved_on",
)

ALLOWED_DOC_TYPES = {"act", "rules", "circular", "form", "portal_help"}


class CorpusError(ValueError):
    pass


def _parse_iso(value: str, field: str, doc_id: str) -> date:
    try:
        return datetime.strptime(str(value), "%Y-%m-%d").date()
    except ValueError as exc:
        raise CorpusError(f"{doc_id}: {field} must be ISO YYYY-MM-DD, got {value!r}") from exc


@dataclass
class Document:
    id: str
    title: str
    publisher: str
    source_url: str
    doc_type: str
    jurisdiction: str
    published_on: date
    effective_on: date
    retrieved_on: date
    notes: str = ""
    pdf_url: str = ""
    stale_procedural: bool = False
    state_law_may_differ: bool = False
    original_file: str = ""

    def as_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "publisher": self.publisher,
            "source_url": self.source_url,
            "doc_type": self.doc_type,
            "jurisdiction": self.jurisdiction,
            "published_on": self.published_on.isoformat(),
            "effective_on": self.effective_on.isoformat(),
            "retrieved_on": self.retrieved_on.isoformat(),
            "notes": self.notes,
            "stale_procedural": self.stale_procedural,
            "state_law_may_differ": self.state_law_may_differ,
        }


@dataclass
class Chunk:
    id: str
    doc_id: str
    section: str
    title: str
    text: str
    document: Document

    @property
    def searchable(self) -> str:
        return f"{self.title}\n{self.section}\n{self.text}\n{self.document.title}"


def load_documents(official_dir: Path | None = None) -> dict[str, Document]:
    official_dir = official_dir or (settings.data_dir / "corpus" / "official")
    docs: dict[str, Document] = {}
    sidecars = sorted(official_dir.glob("*.yaml")) + sorted(official_dir.glob("*.yml"))
    if not sidecars:
        raise CorpusError(f"No corpus sidecars in {official_dir}")
    for path in sidecars:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise CorpusError(f"{path.name}: sidecar is not a mapping")
        missing = [f for f in REQUIRED_DOC_FIELDS if not raw.get(f)]
        if missing:
            raise CorpusError(f"{path.name}: missing required fields {missing}")
        if raw["doc_type"] not in ALLOWED_DOC_TYPES:
            raise CorpusError(f"{path.name}: invalid doc_type {raw['doc_type']!r}")
        doc = Document(
            id=str(raw["id"]),
            title=str(raw["title"]),
            publisher=str(raw["publisher"]),
            source_url=str(raw["source_url"]),
            doc_type=str(raw["doc_type"]),
            jurisdiction=str(raw["jurisdiction"]),
            published_on=_parse_iso(raw["published_on"], "published_on", raw["id"]),
            effective_on=_parse_iso(raw["effective_on"], "effective_on", raw["id"]),
            retrieved_on=_parse_iso(raw["retrieved_on"], "retrieved_on", raw["id"]),
            notes=str(raw.get("notes") or ""),
            pdf_url=str(raw.get("pdf_url") or ""),
            stale_procedural=bool(raw.get("stale_procedural")),
            state_law_may_differ=bool(raw.get("state_law_may_differ")),
            original_file=str(raw.get("original_file") or ""),
        )
        docs[doc.id] = doc
    return docs


def load_chunks(docs: dict[str, Document] | None = None) -> list[Chunk]:
    docs = docs if docs is not None else load_documents()
    path = settings.data_dir / "corpus" / "chunks.jsonl"
    chunks: list[Chunk] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        for field in ("id", "doc_id", "section", "title", "text"):
            if not row.get(field):
                raise CorpusError(f"chunks.jsonl:{line_no} missing {field}")
        doc = docs.get(row["doc_id"])
        if not doc:
            raise CorpusError(f"chunks.jsonl:{line_no} unknown doc_id {row['doc_id']}")
        chunks.append(
            Chunk(
                id=row["id"],
                doc_id=row["doc_id"],
                section=str(row["section"]),
                title=str(row["title"]),
                text=str(row["text"]),
                document=doc,
            )
        )
    if not chunks:
        raise CorpusError("corpus has zero chunks")
    return chunks


def provenance_rows(docs: dict[str, Document] | None = None) -> list[dict]:
    docs = docs if docs is not None else load_documents()
    rows = []
    for doc in sorted(docs.values(), key=lambda d: d.published_on):
        rows.append(doc.as_dict())
    return rows
