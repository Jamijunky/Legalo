from __future__ import annotations

from datetime import date
from pathlib import Path
from string import Template

from .config import settings
from .schemas import DraftBody, Intent, PathStep, SourceRef


def _fill(template_id: str, fields: dict[str, str]) -> str:
    path = settings.data_dir / "templates" / f"{template_id}.html"
    src = path.read_text(encoding="utf-8")
    # Use safe_substitute so missing keys remain visible.
    return Template(src).safe_substitute(fields)


def _today() -> str:
    return date.today().isoformat()


def build_path(intent: Intent, slots: dict[str, str], sources: list[SourceRef]) -> list[PathStep]:
    if intent == "rti":
        state = slots.get("state", "your State")
        return [
            PathStep(
                title="Review and sign the RTI draft",
                detail="Section 6 does not require you to give reasons. Keep the request precise. Central Rules 2012 ordinarily expect about 500 words; an application cannot be rejected only for being longer.",
            ),
            PathStep(
                title="Pay the fee if it applies",
                detail="For Central public authorities the application fee is ₹10 (RTI Rules, 2012, rule 3). BPL applicants are exempt with the certificate under rule 5. State Governments may notify different fees.",
                deadline="Pay with the application",
            ),
            PathStep(
                title="File with the correct PIO — Central vs State",
                detail=(
                    "rtionline.gov.in is only for Central Ministries/Departments and other Central public authorities. "
                    "Do not use it for State departments (including GNCT Delhi); if filed, the application can be returned without refund. "
                    + (
                        "This file looks Central — rtionline.gov.in may be the right channel. Confirm the public authority is Central."
                        if slots.get("scheme_level") == "union"
                        else "This file looks like a State authority (scholarship/PDS/education). File with the State PIO or State RTI portal, not rtionline.gov.in."
                        if slots.get("scheme_level") == "state" or "State" in slots.get("public_authority", "")
                        else "If you still do not know whether the scheme is Central (e.g. NSP) or State, do not file yet — the wrong portal wastes the fee."
                    )
                ),
                url="https://rtionline.gov.in/",
                verify="Confirm the live instructions on rtionline.gov.in. Snapshot retrieved 2026-08-18.",
            ),
            PathStep(
                title="Wait thirty days, then appeal",
                detail="PIO must decide within thirty days of receipt (section 7(1)); life-or-liberty requests: 48 hours. First appeal within thirty days to the senior officer (section 19(1)); second appeal to the Information Commission within ninety days (section 19(3)).",
                deadline="30 days from PIO receipt",
            ),
        ]
    if intent == "consumer":
        return [
            PathStep(
                title="Collect proof",
                detail="Invoice, warranty, chat/email with the seller, photos of the defect. You are a consumer under CPA 2019 s.2(7) for personal (non-resale) purchases, including online purchases.",
            ),
            PathStep(
                title="Pick the Commission by consideration paid",
                detail="G.S.R. 912(E) dated 30 December 2021: District Commission if consideration paid does not exceed ₹50 lakh; State Commission ₹50 lakh–₹2 crore; National Commission above ₹2 crore. These replaced the original 2019 Act figures. Verify before filing.",
                verify="PIB PRID 1786342; confirm live limits on e-jagriti.gov.in.",
            ),
            PathStep(
                title="File on e-Jagriti — not e-Daakhil",
                detail="The Department of Consumer Affairs nodal portal is https://e-jagriti.gov.in/ (ministry page last updated 03-06-2025). edaakhil.nic.in is not treated as current (HTTP 500 on 2026-08-18).",
                url="https://e-jagriti.gov.in/",
                verify="Open e-jagriti.gov.in and follow the live complaint-filing screens.",
            ),
            PathStep(
                title="Helpline",
                detail="National Consumer Helpline 1915 if you want a first administrative grievance before or besides the Commission.",
            ),
        ]
    if intent == "tenant":
        st = slots.get("state", "the State where the house is")
        return [
            PathStep(
                title="State law first",
                detail=f"The Model Tenancy Act, 2021 is a Union model (Cabinet 2 June 2021). It applies in {st} only if {st} has enacted it. Check that State's rent-control / tenancy Act before relying on these sections.",
                verify="MoHUA Model Tenancy Act PDF; State gazette.",
            ),
            PathStep(
                title="Essential services cannot be cut as pressure",
                detail="Model s.20: a landlord/property manager shall not withhold essential supply (explicitly including electricity). A tenant may apply to the Rent Authority for immediate restoration; inquiry within one month; compensation up to two months' rent.",
            ),
            PathStep(
                title="A two-day notice is not an eviction order",
                detail="Model s.21: eviction is by Rent Court on listed grounds after due process — not by informal 48-hour letters. If your State has not adopted the model, the State Act still typically requires a court/authority process.",
            ),
            PathStep(
                title="Send a written representation and keep proof",
                detail="Use the draft reply. If supply stays cut, approach the local police for a cognizable safety issue and the competent Rent Authority / civil court as per State law. This tool does not file for you.",
            ),
        ]
    return []


def build_draft(intent: Intent, slots: dict[str, str], language: str) -> DraftBody | None:
    today = _today()
    if intent == "rti":
        fields = {
            "public_authority": slots.get("public_authority", "[public authority]"),
            "public_authority_address": slots.get("state", "[office address / district]"),
            "applicant_name": slots.get("applicant_name", "[name]"),
            "applicant_address": slots.get("applicant_address", "[address]"),
            "applicant_contact": slots.get("applicant_contact", "[contact]"),
            "information_sought": slots.get("information_sought", "[particulars]"),
            "period": slots.get("period", "From the date of application to the date of this RTI"),
            "delivery": "By post / email to the address above",
            "place": slots.get("state", ""),
            "date": today,
            "retrieved_on": "2026-08-18",
        }
        html = _fill("rti", fields)
        return DraftBody(
            template_id="rti",
            title="RTI application (section 6)",
            language=language,
            fields=fields,
            html=html,
            plain=_html_to_plain(html),
        )
    if intent == "consumer":
        amount = slots.get("amount", "0")
        try:
            val = int(str(amount).replace(",", "").split(".")[0])
        except ValueError:
            val = 0
        forum = "DISTRICT CONSUMER DISPUTES REDRESSAL COMMISSION"
        if val > 2_00_00_000:
            forum = "NATIONAL CONSUMER DISPUTES REDRESSAL COMMISSION"
        elif val > 50_00_000:
            forum = "STATE CONSUMER DISPUTES REDRESSAL COMMISSION"
        fields = {
            "forum": forum,
            "forum_place": slots.get("complainant_address", "[district]"),
            "complainant_name": slots.get("complainant_name", "[name]"),
            "complainant_address": slots.get("complainant_address", "[address]"),
            "opposite_party": slots.get("opposite_party", "[seller]"),
            "opposite_party_address": slots.get("opposite_party_address", "[seller address]"),
            "purchase_date": slots.get("purchase_date", "[date]"),
            "goods_service": slots.get("goods_service", "[goods/service]"),
            "amount": str(amount),
            "defect": slots.get("defect", "[defect]"),
            "prior_contact": slots.get("prior_contact", "several occasions"),
            "cause_place": slots.get("complainant_address", "[place]"),
            "relief": slots.get("relief", "Refund of the consideration paid"),
            "place": slots.get("complainant_address", ""),
            "date": today,
            "retrieved_on": "2026-08-18",
        }
        html = _fill("consumer", fields)
        return DraftBody(
            template_id="consumer",
            title="Consumer complaint draft (CPA 2019 s.35)",
            language=language,
            fields=fields,
            html=html,
            plain=_html_to_plain(html),
        )
    if intent == "tenant":
        issue = slots.get("issue", "unlawful pressure in respect of the tenancy")
        fields = {
            "tenant_address": slots.get("premises", ""),
            "date": today,
            "landlord_name": slots.get("landlord_name", "[landlord]"),
            "landlord_address": slots.get("landlord_address", ""),
            "issue_title": issue[:80],
            "premises": slots.get("premises", "[premises]"),
            "facts": f"On {slots.get('facts_date', '[date]')}: {issue}",
            "legal_paragraph": (
                "The Model Tenancy Act, 2021 s.20 (MoHUA, 2 June 2021) says no landlord shall withhold essential "
                "supply including electricity. s.21 channels eviction through a Rent Court on listed grounds. "
                "This is model law — confirm whether your State has enacted it."
            ),
            "request": "immediately restore essential supply and withdraw any extra-legal eviction threat",
            "state": slots.get("state", "[State]"),
            "tenant_name": slots.get("tenant_name", "[name]"),
            "tenant_contact": slots.get("tenant_contact", ""),
            "retrieved_on": "2026-08-18",
        }
        html = _fill("tenant", fields)
        return DraftBody(
            template_id="tenant",
            title="Tenant representation (Model Tenancy Act 2021)",
            language=language,
            fields=fields,
            html=html,
            plain=_html_to_plain(html),
        )
    return None


def _html_to_plain(html: str) -> str:
    text = html
    for tag in ("</p>", "</div>", "</li>", "</h1>", "<br/>", "<br>"):
        text = text.replace(tag, "\n")
    import re

    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
