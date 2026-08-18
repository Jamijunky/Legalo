from __future__ import annotations

"""Situation interpretation — the product core.

A weak system translates 'my scholarship is pending' and retrieves scholarship FAQs.
This module decides what kind of civic problem it is, which facts would change
the route, and which action is warranted. Pathways live in data/routing/pathways.json
so a new domain is a new row, not a new chatbot.
"""

import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Literal

from .config import settings
from .llm import generate_json
from .schemas import Intent, SlotQuestion

Domain = Literal["welfare_records", "consumer", "tenancy", "police_accountability", "workplace", "unsupported"]
Action = Literal[
    "rti",
    "rti_for_criteria",
    "consumer_complaint",
    "tenant_representation",
    "nhrc_complaint",
    "labour_representation",
    "none",
]
Level = Literal["union", "state", "unknown"]

PENDING_KINDS = ("pending_application", "disbursement_failed", "verification_gap", "eligibility_question")


@dataclass
class Alternative:
    situation_type: str
    why: str


@dataclass
class Interpretation:
    domain: Domain
    situation_type: str
    primary_action: Action
    secondary_action: str | None
    government_level: Level
    benefit: str | None
    department_id: str | None
    why: str
    not_this: str
    alternatives: list[Alternative] = field(default_factory=list)
    evidence: list[str] = field(default_factory=list)
    confidence: float = 0.5
    needs_pending_kind: bool = False
    needs_scheme_level: bool = False
    source: str = "rules"

    def as_public(self) -> dict[str, Any]:
        d = asdict(self)
        return d


def _load_table() -> dict[str, Any]:
    path: Path = settings.data_dir / "routing" / "pathways.json"
    return json.loads(path.read_text(encoding="utf-8"))


TABLE = _load_table()


def _has(blob: str, *needles: str) -> bool:
    low = blob.lower()
    for n in needles:
        nlow = n.lower()
        if len(nlow) <= 3 and nlow.isascii() and nlow[-1].isalnum():
            if re.search(rf"\b{re.escape(nlow)}\b", low):
                return True
        elif nlow in low:
            return True
    return False


def detect_benefit(blob: str) -> str | None:
    if _has(blob, "provident", "epf", "epfo", "uan") or (re.search(r"\bpf\b", blob, re.I) and _has(blob, "fund", "pending", "contribution", "employer", "withdraw")):
        return "pf"
    if _has(blob, "scholarship", "छात्रवृत्ति", "nsp"):
        return "scholarship"
    if _has(blob, "ration", "राशन", "pds", "nfsa", "ration card"):
        return "ration"
    if _has(blob, "pension", "पेंशन"):
        return "pension"
    return None


def detect_level(blob: str, benefit: str | None) -> Level:
    if benefit == "pf":
        return "union"
    if _has(blob, "nsp", "national scholarship", "central scheme", "pm-"):
        return "union"
    if _has(blob, "state scholarship", "state scheme"):
        return "state"
    if benefit == "ration":
        return "state"
    if _has(blob, "prayagraj", "lucknow", "uttar pradesh", "उत्तर प्रदेश", "state government"):
        if benefit == "scholarship":
            return "unknown"  # still could be NSP accessed from a State
        return "state"
    return "unknown"


def detect_state(blob: str) -> str | None:
    mapping = [
        (r"prayagraj|allahabad|lucknow|noida|uttar pradesh|\bup\b|उत्तर प्रदेश|प्रयागराज|लखनऊ", "Uttar Pradesh"),
        (r"mumbai|pune|maharashtra|महाराष्ट्र", "Maharashtra"),
        (r"bengaluru|bangalore|karnataka", "Karnataka"),
        (r"chennai|tamil nadu", "Tamil Nadu"),
        (r"hyderabad|telangana", "Telangana"),
        (r"delhi|gnct", "Delhi"),
        (r"patna|bihar", "Bihar"),
        (r"jaipur|rajasthan", "Rajasthan"),
        (r"kolkata|west bengal", "West Bengal"),
    ]
    for pat, name in mapping:
        if re.search(pat, blob, re.I):
            return name
    return None


def _pending_kind_from_text(blob: str) -> str | None:
    if _has(blob, "am i eligible", "do i qualify", "eligibility", "क्या मैं पात्र", "पात्रता", "पात्र हूँ", "पात्र हूं"):
        return "eligibility_question"
    if _has(blob, "approved", "selected", "sanctioned", "money has not", "payment not", "disburs", "dbt", "amount not credit"):
        return "disbursement_failed"
    if _has(blob, "kyc", "verification", "document pending", "ask for document", "aadhaar pending"):
        return "verification_gap"
    if _has(blob, "file noting", "status of my", "certified cop", "copies of", "want the status", "प्रतियाँ", "स्थिति"):
        return "explicit_information_request"
    if _has(blob, "pending", "stuck", "no update", "heard nothing", "लंबित", "अटका", "चार महीने", "four month"):
        return "pending_application"
    return None


def _is_police_assault(blob: str) -> bool:
    actor = _has(blob, "police", "constable", "inspector", "थाना", "पुलिस")
    actor = actor or (_has(blob, "officer") and _has(blob, "police", "पुलिस"))
    harm = _has(
        blob,
        "slap",
        "slapped",
        "beat",
        "beaten",
        "hit me",
        "thrash",
        "torture",
        "lathi",
        "punched",
        "custody",
        "थप्पड़",
        "पीटा",
        "मारपीट",
        "मारा",
    )
    return actor and harm


def _is_workplace(blob: str) -> bool:
    if _has(blob, "refund", "defective", "smartphone", "landlord", "tenant"):
        return False
    return _has(
        blob,
        "unpaid salary",
        "salary unpaid",
        "wages not paid",
        "unpaid wages",
        "employer fired",
        "terminated me",
        "i was fired",
        "retrench",
        "वेतन नहीं",
        "नौकरी से निकाल",
    ) or (
        _has(blob, "employer", "naukri", "नियोक्ता")
        and _has(blob, "salary", "wage", "fired", "terminat", "वेतन")
    )


def _is_tenancy(blob: str) -> bool:
    negated = _has(blob, "not a tenant", "not the tenant", "i am not a tenant")
    landlordish = _has(blob, "landlord", "मकान मालिक", "evict", "vacate", "खाली कर", "किरायेदार")
    if negated and not landlordish:
        return False
    return _has(blob, "landlord", "tenant", "evict", "vacate", "मकान मालिक", "किरायेदार", "खाली कर")


def _is_consumer(blob: str) -> bool:
    return _has(blob, "refund", "defective", "warranty", "smartphone", "वापसी", "खराब")


def _is_bare_rti_question(blob: str) -> bool:
    return _has(blob, "what is rti", "explain the act", "meaning of rti", "what is the rti")


def _domain_from_blob(blob: str) -> Domain:
    if _is_police_assault(blob):
        return "police_accountability"
    if _is_workplace(blob):
        return "workplace"
    if _is_tenancy(blob):
        return "tenancy"
    if _is_consumer(blob):
        return "consumer"
    if detect_benefit(blob) == "pf":
        return "welfare_records"
    if detect_benefit(blob) or _has(blob, "application has been pending", "public authority", "file noting", "certified cop"):
        return "welfare_records"
    if _has(blob, "rti") and not _is_bare_rti_question(blob):
        return "welfare_records"
    if _has(blob, "surgery", "hack", "bomb"):
        return "unsupported"
    return "unsupported"


def interpret(text: str, slots: dict[str, str] | None = None, notice: str = "") -> Interpretation:
    slots = dict(slots or {})
    citizen = f"{text}\n{notice}"
    blob = f"{citizen}\n" + " ".join(f"{k}={v}" for k, v in slots.items())

    llm = generate_json(
        "You interpret Indian civic situations. Do not give eligibility opinions. "
        "Choose domain: welfare_records | consumer | tenancy | police_accountability | unsupported. "
        "Choose situation_type: pending_application | disbursement_failed | verification_gap | "
        "eligibility_question | explicit_information_request | defect_refund_refused | "
        "essential_supply_cut | informal_eviction | police_assault | unsupported. "
        "police_accountability = alleged assault or illegal force by a police officer. "
        "unsupported = medical how-to or unrelated. Do not treat police assault as unsupported."
        "JSON keys: domain, situation_type, benefit, government_level, evidence (array of short quotes).",
        citizen[:4000],
    )

    domain = _domain_from_blob(citizen)
    benefit = detect_benefit(citizen) or slots.get("benefit")
    level = detect_level(citizen, benefit)
    if slots.get("scheme_level") in ("union", "state"):
        level = slots["scheme_level"]  # type: ignore[assignment]
    source = "rules"

    # LLM may fill gaps the keyword table cannot. It must not override a matched route.
    if domain == "unsupported" and llm and llm.get("domain") in {
        "welfare_records",
        "consumer",
        "tenancy",
        "police_accountability",
        "workplace",
        "unsupported",
    }:
        domain = llm["domain"]
        source = "llm+rules"
        if not benefit:
            benefit = llm.get("benefit") or benefit
        if llm.get("government_level") in {"union", "state", "unknown"}:
            level = llm["government_level"]

    if _is_police_assault(blob):
        domain = "police_accountability"
        source = "rules" if source == "rules" else "llm+rules"
    if _is_workplace(blob) and domain not in {"tenancy", "police_accountability"} and detect_benefit(blob) != "pf":
        domain = "workplace"

    situation = slots.get("pending_kind") or _pending_kind_from_text(blob)
    if domain == "unsupported" and llm and llm.get("situation_type") in TABLE["pathways"] and not slots.get("pending_kind"):
        situation = llm["situation_type"]

    evidence: list[str] = []
    if benefit:
        evidence.append(f"benefit={benefit}")
    if situation:
        evidence.append(f"kind={situation}")
    st = detect_state(blob) or slots.get("state")
    if st:
        evidence.append(f"place={st}")
        slots.setdefault("state", st)

    alternatives: list[Alternative] = []
    needs_kind = False
    needs_level = False

    if domain == "tenancy":
        if _has(blob, "electric", "बिजली", "water cut", "essential"):
            situation = "essential_supply_cut"
            if _has(blob, "vacate", "two day", "2 day", "evict", "खाली"):
                alternatives.append(
                    Alternative("informal_eviction", "The same facts also include an extra-legal vacate demand.")
                )
                situation = "informal_eviction" if _has(blob, "vacate", "evict", "two day", "खाली") else situation
        elif _has(blob, "vacate", "evict", "khali", "खाली"):
            situation = "informal_eviction"
        else:
            situation = "informal_eviction"
        level = "state"
    elif domain == "consumer":
        situation = "defect_refund_refused"
        level = "unknown"
    elif domain == "welfare_records":
        if situation == "explicit_information_request":
            needs_kind = False
        elif not slots.get("pending_kind") and situation in (None, "pending_application"):
            # "pending" alone is not enough — disbursement, KYC and eligibility look the same in a one-liner
            situation = "pending_application"
            needs_kind = True
            alternatives = [
                Alternative("pending_application", "Applied, no decision / no update."),
                Alternative("disbursement_failed", "Told approved/selected but money not credited."),
                Alternative("verification_gap", "Office says documents or KYC are incomplete."),
                Alternative("eligibility_question", "Asking whether they qualify — we will not invent that."),
            ]
            evidence.append("vague welfare delay — discriminating question required")
        if not situation:
            situation = "pending_application"
            needs_kind = True
        if benefit == "scholarship" and level == "unknown" and not slots.get("scheme_level"):
            needs_level = True
            evidence.append("scholarship scheme-level unknown — NSP vs State changes the PIO portal")
        if benefit == "ration":
            level = "state"
            needs_level = False
        if benefit == "pf":
            level = "union"
            needs_level = False
    elif domain == "police_accountability":
        situation = "police_assault"
        level = "union"
        evidence.append("alleged police use of force — human-rights complaint, not RTI")
    elif domain == "workplace":
        situation = "unpaid_wages"
        level = "state"
        evidence.append("employment dispute — not consumer, not unsourced IDA sections")
    else:
        situation = "unsupported"

    pathway = TABLE["pathways"].get(situation or "", TABLE["pathways"].get("pending_application", {}))
    if domain == "unsupported" or situation == "unsupported":
        return Interpretation(
            domain="unsupported",
            situation_type="unsupported",
            primary_action="none",
            secondary_action=None,
            government_level="unknown",
            benefit=benefit,
            department_id=None,
            why="No civic pathway in the v1 table matches this. Legalo will not invent one.",
            not_this="Not RTI, not consumer, not tenancy.",
            confidence=0.9,
            source=source,
            evidence=evidence,
        )

    dept = None
    if domain == "police_accountability":
        dept = "nhrc"
    elif domain == "workplace":
        dept = "labour-commissioner"
    elif benefit and benefit in TABLE["benefits"]:
        bmeta = TABLE["benefits"][benefit]
        if level == "union":
            dept = bmeta.get("department_union")
        else:
            dept = bmeta.get("department_state")

    conf = 0.55
    if not needs_kind and not needs_level:
        conf = 0.82
    if situation == "explicit_information_request":
        conf = 0.9
    if situation == "police_assault":
        conf = 0.88

    why = pathway.get("why_en", "")
    if benefit == "scholarship" and level == "unknown":
        why += " Scholarship may be a State scheme or a Central/NSP scheme — that choice decides the PIO and whether rtionline.gov.in is even lawful to use."
    if benefit == "ration":
        why += " Ration / PDS is a State Food & Civil Supplies record. rtionline.gov.in will bounce it."
    if benefit == "pf":
        why += " Provident-fund records are held by EPFO, a Central public authority — not a shop forum, and not a State PDS RTI."

    return Interpretation(
        domain=domain,  # type: ignore[arg-type]
        situation_type=situation or "pending_application",
        primary_action=pathway.get("primary_action", "rti"),
        secondary_action=pathway.get("secondary_action"),
        government_level=level,
        benefit=benefit,
        department_id=dept,
        why=why,
        not_this=pathway.get("not_en", ""),
        alternatives=alternatives,
        evidence=evidence,
        confidence=conf,
        needs_pending_kind=needs_kind,
        needs_scheme_level=needs_level,
        source=source,
    )


def intent_of(interp: Interpretation) -> Intent:
    if interp.domain == "consumer":
        return "consumer"
    if interp.domain == "tenancy":
        return "tenant"
    if interp.domain == "police_accountability":
        return "nhrc"
    if interp.domain == "workplace":
        return "labour"
    if interp.domain == "unsupported" or interp.primary_action == "none":
        return "unsupported"
    return "rti"


def discriminating_question(interp: Interpretation, slots: dict[str, str]) -> SlotQuestion | None:
    if interp.needs_pending_kind and not slots.get("pending_kind"):
        return SlotQuestion(
            key="pending_kind",
            prompt_en=(
                "A pending scholarship/benefit can mean different civic problems. Which is closest?\n"
                "1) I applied and have heard nothing (file still pending).\n"
                "2) I was told I was selected/approved but the money has not come.\n"
                "3) They say documents or KYC/verification are still pending.\n"
                "4) I mainly want to know if I am eligible."
            ),
            prompt_hi=(
                "लंबित छात्रवृत्ति/लाभ कई तरह की समस्या हो सकती है। कौन-सा सबसे नज़दीक है?\n"
                "1) आवेदन किया, कोई खबर नहीं (फ़ाइल लंबित)।\n"
                "2) चयन/मंज़ूरी हुई बताई गई, पैसे नहीं आए।\n"
                "3) दस्तावेज़ या KYC बाकी बता रहे हैं।\n"
                "4) मैं मुख्यतः पात्रता पूछ रहा/रही हूँ।"
            ),
            required=True,
            choices=["pending_application", "disbursement_failed", "verification_gap", "eligibility_question"],
        )
    if interp.needs_scheme_level and not slots.get("scheme_level"):
        return SlotQuestion(
            key="scheme_level",
            prompt_en=(
                "Is this a Central / National Scholarship Portal (NSP) scheme, or a State government scholarship? "
                "This decides the public authority and whether you may use rtionline.gov.in (Central only)."
            ),
            prompt_hi=(
                "क्या यह केंद्रीय / National Scholarship Portal (NSP) योजना है, या राज्य सरकार की छात्रवृत्ति? "
                "इसी से लोक प्राधिकरण और rtionline.gov.in का उपयोग तय होता है (केवल केंद्र)।"
            ),
            required=True,
            choices=["union", "state", "unknown"],
        )
    return None


def apply_discriminator(slots: dict[str, str], key: str | None, answer: str) -> dict[str, str]:
    updated = dict(slots)
    raw = (answer or "").strip()
    low = raw.lower()
    if key == "pending_kind" or (not key and any(x in low for x in ("1", "2", "3", "4", "eligible", "approved", "kyc"))):
        if raw in PENDING_KINDS:
            updated["pending_kind"] = raw
        elif low.startswith("1") or _has(low, "heard nothing", "still pending", "no update", "applied"):
            updated["pending_kind"] = "pending_application"
        elif low.startswith("2") or _has(low, "approved", "selected", "money", "disburs"):
            updated["pending_kind"] = "disbursement_failed"
        elif low.startswith("3") or _has(low, "kyc", "document", "verification"):
            updated["pending_kind"] = "verification_gap"
        elif low.startswith("4") or _has(low, "eligible", "qualify", "eligibility", "पात्र"):
            updated["pending_kind"] = "eligibility_question"
        elif key != "pending_kind":
            updated["pending_kind"] = raw
        if key == "pending_kind":
            return updated
    if key == "scheme_level":
        if _has(low, "nsp", "national", "central", "union"):
            updated["scheme_level"] = "union"
        elif _has(low, "state"):
            updated["scheme_level"] = "state"
        else:
            updated["scheme_level"] = raw or "unknown"
    elif key and raw:
        updated[key] = raw
    return updated


def information_sought(interp: Interpretation, slots: dict[str, str]) -> str:
    benefit = interp.benefit or "benefit / application"
    if interp.situation_type == "disbursement_failed":
        return (
            f"For my {benefit}: (a) certified copies of the sanction/selection order; "
            "(b) payment file notings and PFMS/DBT / treasury status with dates; "
            "(c) if payment was returned or rejected, the memo and reason; "
            "(d) name and designation of the officer with whom the payment file is pending."
        )
    if interp.situation_type == "verification_gap":
        return (
            f"For my {benefit} application: (a) the written list of documents/KYC still pending, with dates of each demand; "
            "(b) copy of any deficiency memo; (c) file notings on verification; "
            "(d) officer presently holding the file."
        )
    if interp.situation_type == "eligibility_question":
        return (
            f"Certified copies of the eligibility criteria, governing circulars and the evaluation/scrutiny note "
            f"on my {benefit} application, including marks or grounds if it was rejected or kept pending on eligibility."
        )
    return (
        f"Current status of my {benefit} application; certified copies of file notings, orders and reasons for delay; "
        "name and designation of officers with whom the file is pending; and the date-wise movement of the file."
    )


def department_label(interp: Interpretation) -> str | None:
    from .config import settings as st

    directory = json.loads((st.data_dir / "departments" / "directory.json").read_text(encoding="utf-8"))
    for row in directory["authorities"]:
        if row["id"] == interp.department_id:
            return row["label_en"]
    return None
