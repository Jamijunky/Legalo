from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

Intent = Literal["rti", "consumer", "tenant", "nhrc", "labour", "unsupported"]
Step = Literal["ingest", "understand", "rights", "path", "draft", "takeaway"]


class SourceRef(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    publisher: str
    section: str
    source_url: str
    published_on: str
    effective_on: str
    retrieved_on: str
    doc_type: str
    stale_procedural: bool = False
    state_law_may_differ: bool = False
    notes: str = ""


class SlotQuestion(BaseModel):
    key: str
    prompt_en: str
    prompt_hi: str
    required: bool = True
    choices: list[str] = Field(default_factory=list)


class PathStep(BaseModel):
    title: str
    detail: str
    deadline: str | None = None
    url: str | None = None
    verify: str | None = None


class DraftBody(BaseModel):
    template_id: str
    title: str
    language: str
    fields: dict[str, str]
    html: str
    plain: str


class InterpretationView(BaseModel):
    domain: str
    situation_type: str
    primary_action: str
    secondary_action: str | None = None
    government_level: str
    benefit: str | None = None
    department_id: str | None = None
    department_label: str | None = None
    why: str
    not_this: str
    alternatives: list[dict[str, str]] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 0.0
    source: str = "rules"


class GenerationTrace(BaseModel):
    template_id: str | None = None
    language: str
    source_ids: list[str]
    llm_used: bool
    classifier: str


class CaseResponse(BaseModel):
    case_id: str
    step: Step
    intent: Intent | None = None
    language: str
    ui_locale: str
    restatement: str | None = None
    interpretation: InterpretationView | None = None
    question: SlotQuestion | None = None
    slots: dict[str, str] = Field(default_factory=dict)
    explanation: str | None = None
    sources: list[SourceRef] = Field(default_factory=list)
    path: list[PathStep] = Field(default_factory=list)
    draft: DraftBody | None = None
    banners: list[str] = Field(default_factory=list)
    trace: GenerationTrace | None = None
    ready_for_pdf: bool = False
    error: str | None = None


class CreateCaseRequest(BaseModel):
    text: str = ""
    language: str = "en"
    ui_locale: str = "en"


class MessageRequest(BaseModel):
    text: str
    language: str | None = None


class DraftPatchRequest(BaseModel):
    fields: dict[str, str]


class ProvenanceRow(BaseModel):
    id: str
    title: str
    publisher: str
    doc_type: str
    published_on: str
    effective_on: str
    retrieved_on: str
    source_url: str
    notes: str = ""


class HealthResponse(BaseModel):
    ok: bool
    corpus_docs: int
    corpus_chunks: int
    gemini: bool
    database: str


class EvalResult(BaseModel):
    id: str
    passed: bool
    details: dict[str, Any]
