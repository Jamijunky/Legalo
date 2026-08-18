from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

from .config import settings
from .corpus import provenance_rows
from .engine import engine
from .ocr import extract_text
from .pdfgen import html_to_pdf
from .schemas import (
    CaseResponse,
    CreateCaseRequest,
    DraftPatchRequest,
    HealthResponse,
    MessageRequest,
    ProvenanceRow,
)

app = FastAPI(title="Legalo API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list + ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        ok=True,
        corpus_docs=len(engine.docs),
        corpus_chunks=len(engine.chunks),
        gemini=bool(settings.gemini_api_key),
        database=settings.database_url or "in-memory-lexical",
    )


@app.get("/v1/provenance", response_model=list[ProvenanceRow])
def provenance() -> list[ProvenanceRow]:
    return [ProvenanceRow(**row) for row in provenance_rows(engine.docs)]


@app.post("/v1/cases", response_model=CaseResponse)
def create_case(body: CreateCaseRequest) -> CaseResponse:
    if not body.text.strip():
        raise HTTPException(400, "Describe the situation in your own words.")
    return engine.create(body.text, body.language, body.ui_locale)


@app.get("/v1/cases/{case_id}", response_model=CaseResponse)
def get_case(case_id: str) -> CaseResponse:
    try:
        return engine._respond(engine.get(case_id))
    except KeyError:
        raise HTTPException(404, "Unknown case") from None


@app.post("/v1/cases/{case_id}/message", response_model=CaseResponse)
def message(case_id: str, body: MessageRequest) -> CaseResponse:
    try:
        return engine.message(case_id, body.text, body.language)
    except KeyError:
        raise HTTPException(404, "Unknown case") from None


@app.post("/v1/cases/{case_id}/upload", response_model=CaseResponse)
async def upload(case_id: str, file: UploadFile = File(...)) -> CaseResponse:
    try:
        engine.get(case_id)
    except KeyError:
        raise HTTPException(404, "Unknown case") from None
    data = await file.read()
    text = extract_text(data, file.filename or "notice.bin")
    if not text.strip():
        raise HTTPException(
            422,
            "Could not read text from that file. Try a .txt or a digital PDF, or paste the notice text.",
        )
    return engine.attach_notice(case_id, file.filename or "", data, text)


@app.patch("/v1/cases/{case_id}/draft", response_model=CaseResponse)
def patch_draft(case_id: str, body: DraftPatchRequest) -> CaseResponse:
    try:
        return engine.patch_draft(case_id, body.fields)
    except KeyError:
        raise HTTPException(404, "Unknown case") from None


@app.get("/v1/cases/{case_id}/pdf")
def pdf(case_id: str) -> Response:
    try:
        case = engine.get(case_id)
    except KeyError:
        raise HTTPException(404, "Unknown case") from None
    resp = engine._respond(case)
    if not resp.draft:
        raise HTTPException(400, "Draft is not ready")
    blob = html_to_pdf(resp.draft.plain, resp.draft.title)
    return Response(
        content=blob,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="legalo-{case_id}.pdf"'},
    )


@app.post("/v1/eval")
def run_eval() -> dict:
    from .eval_cases import run_gold

    return run_gold(engine)
