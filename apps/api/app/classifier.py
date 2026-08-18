from __future__ import annotations

import re

from .llm import generate_json
from .schemas import Intent

RTI_HINTS = (
    "rti",
    "ration",
    "pds",
    "scholarship",
    "pending",
    "file noting",
    "public information",
    "सूचना",
    "राशन",
    "छात्रवृत्ति",
    "आवेदन अटका",
    "status of my application",
    "copies of",
)
CONSUMER_HINTS = (
    "refund",
    "defective",
    "warranty",
    "shop refused",
    "consumer",
    "phone",
    "smartphone",
    "product",
    "वापसी",
    "खराब",
    "दुकान",
    "refund",
)
TENANT_HINTS = (
    "landlord",
    "tenant",
    "evict",
    "vacate",
    "electricity",
    "rent",
    "notice to vacate",
    "मकान मालिक",
    "किरायेदार",
    "बिजली",
    "खाली",
)


def _score(text: str, hints: tuple[str, ...]) -> int:
    low = text.lower()
    return sum(1 for h in hints if h.lower() in low)


def classify(text: str, extracted_notice: str = "") -> tuple[Intent, str]:
    blob = f"{text}\n{extracted_notice}"
    payload = generate_json(
        "You classify Indian civic problems into rti, consumer, tenant, nhrc, or unsupported. "
        "rti = citizen needs records/status from a public authority. "
        "consumer = defect/deficiency/refund against a seller. "
        "tenant = landlord/tenant housing dispute. "
        "nhrc = alleged assault or illegal force by a police officer — human rights complaint, not RTI. "
        "unsupported = medical advice, crime how-to, or unrelated. "
        'JSON: {"intent": "...", "reason": "..."}',
        blob[:4000],
    )
    if payload and payload.get("intent") in {"rti", "consumer", "tenant", "nhrc", "unsupported"}:
        return payload["intent"], "llm"

    scores = {
        "rti": _score(blob, RTI_HINTS),
        "consumer": _score(blob, CONSUMER_HINTS),
        "tenant": _score(blob, TENANT_HINTS),
    }
    intent = max(scores, key=lambda k: scores[k])
    if scores[intent] == 0:
        if re.search(r"surgery|hack|bomb|kill", blob, re.I):
            return "unsupported", "rules"
        return "unsupported", "rules"
    return intent, "heuristic"  # type: ignore[return-value]
