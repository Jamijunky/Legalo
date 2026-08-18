from __future__ import annotations

from datetime import date

from .config import settings
from .schemas import DraftBody, Intent, PathStep, SourceRef


def _fill(template_id: str, fields: dict[str, str]) -> str:
    path = settings.data_dir / "templates" / f"{template_id}.html"
    src = path.read_text(encoding="utf-8")
    for key, value in fields.items():
        src = src.replace("{{ " + key + " }}", str(value))
        src = src.replace("{{" + key + "}}", str(value))
    return src


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
    if intent == "nhrc":
        return [
            PathStep(
                title="Write a self-contained complaint — no invented offence sections",
                detail="NHRC FAQ: complaints should be self-contained. State who, when, where, and what the officer did. Legalo will not insert BNS/IPC section numbers; those Acts are not in the dated corpus.",
            ),
            PathStep(
                title="Lodge on HRCNet (NHRC or State Commission)",
                detail="nhrc.nic.in Lodge & Track (last updated 07-Apr-2026) opens https://hrcnet.nic.in/HRCNet/public/webcomplaint.aspx. Select the State of incident, choose NHRC or SHRC, verify mobile OTP, upload a PDF if you have one, keep the Unique Diary Number.",
                url="https://hrcnet.nic.in/HRCNet/public/webcomplaint.aspx",
                verify="Confirm live fields on HRCNet. Snapshot retrieved 2026-08-19.",
            ),
            PathStep(
                title="No fee; language",
                detail="NHRC FAQ (retrieved 2026-08-19): Hindi, English or any Eighth Schedule language; no fee. Other listed channels include post, email and CSC — confirm the live email on nhrc.nic.in/faq.",
                url="https://nhrc.nic.in/faq",
            ),
            PathStep(
                title="Helpline published on HRCNet",
                detail="HRCNet publishes NHRC toll-free 14433 for queries. This is not an emergency dispatch number. Legalo does not file.",
            ),
        ]
    if intent == "labour":
        st = slots.get("state", "the State where you worked")
        return [
            PathStep(
                title="Write a demand to the employer first",
                detail="State the period, amount, and what happened, in your own words. Do not paste invented IDA/Shops Act section numbers — those Acts are not in this dated corpus and vary by State.",
            ),
            PathStep(
                title="Find the live labour office",
                detail=f"Use the Ministry of Labour and Employment portal to locate services and the labour machinery of {st}. Snapshot retrieved 2026-08-19.",
                url="https://labour.gov.in/",
                verify="Confirm the live State labour office / Shram Suvidha links on labour.gov.in.",
            ),
            PathStep(
                title="PF is a different route",
                detail="If the missing money is provident-fund (EPFO), that record is held by a Central public authority. That is an RTI/EPFO path, not this wage letter. epfindia.gov.in snapshot 2026-08-19.",
                url="https://www.epfindia.gov.in/",
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
    if intent == "nhrc":
        fields = {
            "commission": "National Human Rights Commission / the State Human Rights Commission of the incident State",
            "date": today,
            "complainant_name": slots.get("complainant_name") or slots.get("applicant_name", "[name]"),
            "complainant_contact": slots.get("complainant_contact") or slots.get("applicant_contact", "[contact / address]"),
            "state": slots.get("state", "[State / UT of incident]"),
            "facts": slots.get("facts")
            or slots.get("issue")
            or "[Describe what the officer did, with date, place, and any witness or injury details.]",
            "place_time": slots.get("place_time", "[place and date/time]"),
            "officer_detail": slots.get("officer_detail", "[station / name / belt number if known; else unknown]"),
            "relief": slots.get(
                "relief",
                "Inquire into the incident, record the officer’s identity, and recommend action and relief as the Commission finds fit.",
            ),
            "retrieved_on": "2026-08-19",
        }
        html = _fill("nhrc", fields)
        return DraftBody(
            template_id="nhrc",
            title="Human rights complaint draft (HRCNet)",
            language=language,
            fields=fields,
            html=html,
            plain=_html_to_plain(html),
        )
    if intent == "labour":
        fields = {
            "worker_address": slots.get("worker_address") or slots.get("state", ""),
            "date": today,
            "employer_name": slots.get("employer_name", "[employer]"),
            "employer_address": slots.get("employer_address", "[employer address]"),
            "issue_title": (slots.get("issue") or "unpaid wages / termination")[:80],
            "facts": slots.get("facts") or slots.get("issue") or "[period, amount, what happened]",
            "request": slots.get("request", "pay the outstanding wages / reverse the unlawful termination and reply in writing"),
            "state": slots.get("state", "[State]"),
            "worker_name": slots.get("worker_name") or slots.get("complainant_name", "[name]"),
            "worker_contact": slots.get("worker_contact") or slots.get("complainant_contact", "[contact]"),
            "retrieved_on": "2026-08-19",
        }
        html = _fill("labour", fields)
        return DraftBody(
            template_id="labour",
            title="Workplace demand letter (no unsourced IDA sections)",
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
