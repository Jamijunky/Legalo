from app.corpus import CorpusError, load_chunks, load_documents
from app.engine import engine
from app.eval_cases import run_gold
from app.pdfgen import html_to_pdf


def test_ingest_loads_dated_corpus():
    docs = load_documents()
    assert "rti-act-2005" in docs
    assert docs["rti-act-2005"].published_on.isoformat() == "2005-06-15"
    chunks = load_chunks(docs)
    assert len(chunks) >= 10


def test_missing_dates_fail_closed(tmp_path, monkeypatch):
    sidecar = tmp_path / "bad.yaml"
    sidecar.write_text("id: x\ntitle: t\npublisher: p\nsource_url: http://x\ndoc_type: act\njurisdiction: union\n", encoding="utf-8")
    from app import corpus

    try:
        corpus.load_documents(tmp_path)
        assert False, "should have failed"
    except CorpusError as exc:
        assert "missing required fields" in str(exc)


def test_gold_eval():
    report = run_gold(engine)
    failed = [r for r in report["results"] if not r["passed"]]
    assert report["passed"] == report["total"], failed


def test_vague_scholarship_asks_what_pending_means():
    resp = engine.create("My scholarship has been pending for four months.", "en", "en")
    assert resp.interpretation
    assert resp.interpretation.benefit == "scholarship"
    assert resp.question and resp.question.key == "pending_kind"
    resp = engine.message(resp.case_id, "pending_application", "en")
    assert resp.question and resp.question.key == "scheme_level"
    resp = engine.message(resp.case_id, "state", "en")
    assert resp.interpretation.primary_action == "rti"
    assert resp.interpretation.government_level == "state"
    assert "rtionline" in " ".join(p.detail for p in resp.path).lower() or resp.question


def test_shop_refund_is_not_an_rti():
    resp = engine.create(
        "Shop refused refund for a defective smartphone I bought last month for 18000 rupees.",
        "en",
        "en",
    )
    assert resp.intent == "consumer"
    assert resp.interpretation and resp.interpretation.primary_action == "consumer_complaint"


def test_police_slap_is_nhrc_not_unsupported():
    resp = engine.create("a police officer slapped me.", "en", "en")
    assert resp.intent == "nhrc"
    assert resp.interpretation
    assert resp.interpretation.situation_type == "police_assault"
    assert resp.interpretation.primary_action == "nhrc_complaint"
    blob = " ".join(
        [resp.explanation or "", resp.interpretation.why, resp.interpretation.not_this, *(p.detail for p in resp.path)]
    ).lower()
    assert "hrcnet" in blob
    assert "not an rti" in resp.interpretation.not_this.lower() or "not an rti" in blob
    assert resp.draft
    assert "323" not in (resp.explanation or "")


def test_hindi_rti_explanation_without_llm():
    resp = engine.create(
        "प्रयागराज में मेरा राशन कार्ड का आवेदन चार महीने से लंबित है।",
        "hi",
        "hi",
    )
    while resp.question:
        resp = engine.message(resp.case_id, "आशा देवी", "hi")
    assert resp.language == "hi"
    assert resp.explanation and "धारा 6" in resp.explanation
    assert any(s.doc_id == "rti-act-2005" for s in resp.sources)


def test_pdf_accepts_rupee_and_dashes():
    blob = html_to_pdf("Fee is ₹10 — Central rules.", "RTI application")
    assert blob.startswith(b"%PDF")
    assert len(blob) > 200
