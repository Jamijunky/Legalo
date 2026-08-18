from __future__ import annotations

import json

from .config import settings
from .engine import Engine


def _advance(engine: Engine, resp, answers: dict[str, str]):
    dummy = resp
    guard = 0
    while dummy.question and guard < 14:
        key = dummy.question.key
        text = answers.get(key) or answers.get("default") or "Demo citizen"
        dummy = engine.message(dummy.case_id, text, "en")
        guard += 1
    return dummy


def run_gold(engine: Engine) -> dict:
    path = settings.data_dir / "eval" / "gold_cases.json"
    cases = json.loads(path.read_text(encoding="utf-8"))
    results = []
    passed = 0
    for item in cases:
        resp = engine.create(item["query"], "en", "en")
        interp = resp.interpretation
        details: dict = {
            "intent": resp.intent,
            "situation_type": interp.situation_type if interp else None,
            "primary_action": interp.primary_action if interp else None,
            "question": resp.question.key if resp.question else None,
        }
        ok = True
        if item.get("expect_intent") and resp.intent != item["expect_intent"]:
            ok = False
            details["intent_fail"] = True
        if item.get("expect_situation_type") and (not interp or interp.situation_type != item["expect_situation_type"]):
            # first-turn type may still be pending until discriminator; allow after answers
            details["first_situation"] = details["situation_type"]
        if item.get("must_ask_keys_any"):
            asked = resp.question.key if resp.question else ""
            if asked not in item["must_ask_keys_any"]:
                ok = False
                details["ask_fail"] = asked
        dummy = _advance(engine, resp, item.get("answers") or {})
        if dummy.interpretation:
            details["situation_type"] = dummy.interpretation.situation_type
            details["primary_action"] = dummy.interpretation.primary_action
            details["why"] = dummy.interpretation.why
        if item.get("expect_situation_type") and dummy.interpretation:
            if dummy.interpretation.situation_type != item["expect_situation_type"]:
                ok = False
                details["situation_fail"] = dummy.interpretation.situation_type
        if item.get("expect_primary_action") and dummy.interpretation:
            if dummy.interpretation.primary_action != item["expect_primary_action"]:
                ok = False
                details["action_fail"] = dummy.interpretation.primary_action
        have = {s.doc_id for s in dummy.sources}
        details["source_docs"] = sorted(have)
        if item.get("must_cite_doc_ids") and item.get("expect_intent") != "unsupported":
            need = set(item["must_cite_doc_ids"])
            if not need.issubset(have):
                ok = False
                details["missing_docs"] = sorted(need - have)
            if item.get("must_cite_sections_any"):
                secs = " ".join(s.section for s in dummy.sources)
                if not any(sec in secs for sec in item["must_cite_sections_any"]):
                    ok = False
                    details["missing_sections"] = item["must_cite_sections_any"]
        if item.get("must_mention"):
            blob = " ".join(
                [
                    dummy.explanation or "",
                    dummy.interpretation.why if dummy.interpretation else "",
                    dummy.interpretation.not_this if dummy.interpretation else "",
                    " ".join(p.detail for p in dummy.path),
                    " ".join(dummy.banners),
                ]
            ).lower()
            for phrase in item["must_mention"]:
                if phrase.lower() not in blob:
                    ok = False
                    details.setdefault("missing_phrases", []).append(phrase)
        if item.get("must_refuse_unsourced"):
            if resp.intent != "unsupported":
                ok = False
                details["refuse_fail"] = resp.intent
        results.append({"id": item["id"], "passed": ok, "details": details})
        if ok:
            passed += 1
    return {"passed": passed, "total": len(cases), "results": results}
