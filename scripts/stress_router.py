#!/usr/bin/env python3
"""Run citizen-style stress cases through the civic engine (create → answer → draft)."""

from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api"))

from app.engine import Engine  # noqa: E402


def blob_of(resp) -> str:
    parts = [
        resp.explanation or "",
        (resp.interpretation.why if resp.interpretation else ""),
        (resp.interpretation.not_this if resp.interpretation else ""),
        " ".join(p.detail for p in resp.path),
        " ".join(resp.banners),
        (resp.draft.plain if resp.draft else ""),
    ]
    return " ".join(parts)


def advance(engine: Engine, resp, answers: dict[str, str], language: str):
    asked: list[str] = []
    guard = 0
    while resp.question and guard < 14:
        asked.append(resp.question.key)
        key = resp.question.key
        if key in answers:
            text = answers[key]
        elif key == "pending_kind":
            text = "pending_application"
        elif key == "scheme_level":
            text = "unknown"
        else:
            text = answers.get("default") or "Citizen"
        resp = engine.message(resp.case_id, text, language)
        guard += 1
    return resp, asked, guard >= 14


def check(item: dict, first, final, asked: list[str], looped: bool) -> list[str]:
    fails: list[str] = []
    interp = final.interpretation
    if item.get("expect_intent") and final.intent != item["expect_intent"]:
        fails.append(f"intent {final.intent} != {item['expect_intent']}")
    if item.get("expect_situation") and (not interp or interp.situation_type != item["expect_situation"]):
        fails.append(f"situation {(interp.situation_type if interp else None)} != {item['expect_situation']}")
    if item.get("expect_benefit") and (not interp or interp.benefit != item["expect_benefit"]):
        fails.append(f"benefit {(interp.benefit if interp else None)} != {item['expect_benefit']}")
    if item.get("expect_level") and (not interp or interp.government_level != item["expect_level"]):
        fails.append(f"level {(interp.government_level if interp else None)} != {item['expect_level']}")
    if item.get("expect_asks_any"):
        first_q = first.question.key if first.question else None
        if first_q not in item["expect_asks_any"]:
            fails.append(f"first ask {first_q} not in {item['expect_asks_any']}")
    want_draft = item.get("expect_draft")
    if want_draft is True and not final.draft:
        fails.append("expected draft")
    if want_draft is False and final.draft:
        fails.append("unexpected draft")
    if looped:
        fails.append("question loop")
    text = blob_of(final).lower()
    for phrase in item.get("must_mention") or []:
        if phrase.lower() not in text:
            fails.append(f"missing phrase: {phrase}")
    for needle in item.get("must_not") or []:
        if needle.lower() in text:
            fails.append(f"forbidden: {needle}")
    plain = (final.draft.plain if final.draft else "") or ""
    if re.search(r"font-family|times new roman", plain, re.I):
        fails.append("css leak in draft")
    if "&amp;" in plain:
        fails.append("html entity in draft")
    return fails


def main() -> int:
    cases = json.loads((ROOT / "data" / "eval" / "stress_cases.json").read_text(encoding="utf-8"))
    engine = Engine()
    rows = []
    by_field: dict[str, dict[str, int]] = defaultdict(lambda: {"pass": 0, "fail": 0})
    by_intent = defaultdict(int)
    for item in cases:
        lang = item.get("language") or "en"
        first = engine.create(item["query"], lang, "hi" if lang == "hi" else "en")
        final, asked, looped = advance(engine, first, item.get("answers") or {}, lang)
        fails = check(item, first, final, asked, looped)
        interp = final.interpretation
        row = {
            "id": item["id"],
            "persona": item.get("persona"),
            "field": item.get("field"),
            "query": item["query"],
            "passed": not fails,
            "fails": fails,
            "intent": final.intent,
            "situation": interp.situation_type if interp else None,
            "benefit": interp.benefit if interp else None,
            "level": interp.government_level if interp else None,
            "confidence": interp.confidence if interp else None,
            "asked": asked,
            "first_question": first.question.key if first.question else None,
            "has_draft": bool(final.draft),
            "sources": sorted({s.doc_id for s in final.sources}),
        }
        rows.append(row)
        field = item.get("field") or "other"
        by_field[field]["pass" if row["passed"] else "fail"] += 1
        by_intent[final.intent or "none"] += 1

    passed = sum(1 for r in rows if r["passed"])
    report = {
        "passed": passed,
        "total": len(rows),
        "by_field": dict(by_field),
        "routed_intent_counts": dict(by_intent),
        "failures": [r for r in rows if not r["passed"]],
        "results": rows,
    }
    out = ROOT / "data" / "eval" / "stress_report.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{passed}/{len(rows)} passed")
    for r in report["failures"]:
        print(f"  FAIL {r['id']}: {r['intent']}/{r['situation']} — {'; '.join(r['fails'])}")
    return 0 if passed == len(rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
