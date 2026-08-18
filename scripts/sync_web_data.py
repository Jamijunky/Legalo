#!/usr/bin/env python3
"""Copy dated corpus + pathways into the Next.js app so Vercel can route on-device."""

from __future__ import annotations

import json
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / "apps" / "web" / "data"
WEB.mkdir(parents=True, exist_ok=True)

docs = []
for path in sorted((ROOT / "data" / "corpus" / "official").glob("*.yaml")):
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    docs.append(
        {
            "id": raw["id"],
            "title": raw["title"],
            "publisher": raw["publisher"],
            "source_url": raw["source_url"],
            "doc_type": raw["doc_type"],
            "jurisdiction": raw["jurisdiction"],
            "published_on": raw["published_on"],
            "effective_on": raw["effective_on"],
            "retrieved_on": raw["retrieved_on"],
            "notes": raw.get("notes") or "",
            "stale_procedural": bool(raw.get("stale_procedural")),
            "state_law_may_differ": bool(raw.get("state_law_may_differ")),
        }
    )
(WEB / "documents.json").write_text(json.dumps(docs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

chunks = []
for line in (ROOT / "data" / "corpus" / "chunks.jsonl").read_text(encoding="utf-8").splitlines():
    if line.strip():
        chunks.append(json.loads(line))
(WEB / "chunks.json").write_text(json.dumps(chunks, ensure_ascii=False) + "\n", encoding="utf-8")

(WEB / "pathways.json").write_text((ROOT / "data" / "routing" / "pathways.json").read_text(encoding="utf-8"), encoding="utf-8")
(WEB / "directory.json").write_text((ROOT / "data" / "departments" / "directory.json").read_text(encoding="utf-8"), encoding="utf-8")

templates = {}
for path in sorted((ROOT / "data" / "templates").glob("*.html")):
    templates[path.stem] = path.read_text(encoding="utf-8")
(WEB / "templates.json").write_text(json.dumps(templates, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print(f"synced {len(docs)} docs, {len(chunks)} chunks, {len(templates)} templates -> {WEB}")
