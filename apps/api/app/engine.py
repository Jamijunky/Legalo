from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from .config import settings
from .corpus import Chunk, load_chunks, load_documents
from .drafts import build_draft, build_path
from .interpret import (
    Interpretation,
    department_label,
    discriminating_question,
    information_sought,
    intent_of,
    interpret,
)
from .llm import detect_language, rewrite_in_language
from .rag import LexicalIndex, to_source_ref
from .schemas import CaseResponse, GenerationTrace, Intent, InterpretationView, SourceRef, Step
from .slots import apply_answer, extract_from_text, next_question

DOC_FILTER: dict[Intent, set[str]] = {
    "rti": {"rti-act-2005", "rti-rules-2012", "rti-faq-dopt-2012", "rti-online-portal", "epfo-portal"},
    "consumer": {"cpa-2019", "cpa-jurisdiction-rules-2021", "e-jagriti-portal"},
    "tenant": {"model-tenancy-act-2021"},
    "nhrc": {"nhrc-hrcnet-portal", "nhrc-faq-complaints"},
    "labour": {"labour-gov-portal"},
    "unsupported": set(),
}


def _explain(intent: Intent, sources: list[SourceRef], slots: dict[str, str]) -> str:
    if intent == "unsupported" or not sources:
        return (
            "I do not have a sourced official document for this request, so I will not invent an answer. "
            "Legalo only explains rights that are grounded in the dated corpus (RTI Act 2005, CPA 2019, "
            "jurisdiction Rules 2021, Model Tenancy Act 2021, and official portal snapshots)."
        )
    bits: list[str] = []
    if intent == "rti":
        bits.append(
            "You can ask a public authority for records it holds. RTI Act 2005 s.3 gives every citizen the right "
            "to information, subject to the Act. s.6 lets you apply in writing or electronically in English, Hindi "
            "or the official language of the area. You do not have to give reasons (s.6(2)). You do need a name "
            "and postal address so they can contact you."
        )
        bits.append(
            "The PIO must decide within thirty days of receiving the request (s.7(1)); if the information concerns "
            "life or liberty, within forty-eight hours. Silence after that period is a deemed refusal (s.7(2)). "
            "First appeal: thirty days to the senior officer (s.19(1)). Second appeal: ninety days to the "
            "Information Commission (s.19(3))."
        )
        bits.append(
            "For Central public authorities the application fee is ₹10 (RTI Rules, 2012, G.S.R. 603(E) dated "
            "31 July 2012, rule 3). BPL applicants are exempt with the certificate in rule 5. State Governments "
            "may notify different fees under ss.27–28."
        )
        bits.append(
            "rtionline.gov.in (DoPT, snapshot 18 August 2026) is only for Central Ministries/Departments and "
            "other Central public authorities. Do not file there for State offices, including GNCT Delhi — the "
            "portal says such applications are returned without refund."
        )
        if slots.get("benefit") == "ration":
            bits.append("A pending ration-card file is a State Food & Civil Supplies matter.")
        if slots.get("benefit") == "scholarship":
            bits.append(
                "A scholarship file is State education unless it is a Central/NSP scheme. "
                "That distinction is the routing decision — not a translation of the word scholarship."
            )
        if slots.get("public_authority"):
            bits.append(f"Suggested public authority category from your facts: {slots['public_authority']}.")
    elif intent == "consumer":
        bits.append(
            "If you bought goods or hired a service for personal use (including online), you are a consumer "
            "under CPA 2019 s.2(7). A defect is s.2(10); a deficiency in service is s.2(11). Consumer rights in "
            "s.2(9) include the right to seek redressal against unfair trade practice."
        )
        bits.append(
            "You may file a complaint with the District Commission under s.35. Which Commission hears it depends "
            "on consideration paid, not on how much compensation you claim: G.S.R. 912(E) of 30 December 2021 "
            "sets District ≤ ₹50 lakh, State ₹50 lakh–₹2 crore, National > ₹2 crore. Those rules replaced the "
            "original 2019 Act figures (₹1 crore / ₹10 crore). Confirm the live limit before filing."
        )
        bits.append(
            "File on e-Jagriti (https://e-jagriti.gov.in/), the Department of Consumer Affairs nodal platform "
            "(ministry page last updated 03-06-2025). The older e-Daakhil site is not treated as current as of "
            "18 August 2026. Helpline 1915."
        )
    elif intent == "tenant":
        bits.append(
            "The Model Tenancy Act, 2021 (MoHUA, approved 2 June 2021) is a model for States and UTs. It is not "
            "automatically the law of every State. If your State has not enacted it, follow that State's rent "
            "control / tenancy statute. The points below are from the model and may differ locally."
        )
        bits.append(
            "Model s.20: a landlord or property manager shall not withhold essential supply or service, including "
            "electricity and water. You may apply to the Rent Authority for an interim restoration order; inquiry "
            "within one month; compensation up to two months' rent."
        )
        bits.append(
            "Model s.21: eviction is an order of the Rent Court on listed grounds after notice — not a two-day "
            "informal letter. A notice to vacate in 48 hours, by itself, is not an eviction order under this model."
        )
    elif intent == "nhrc":
        bits.append(
            "This is not an RTI and not a consumer complaint. A complaint that a police officer used force against you "
            "is a human-rights complaint. The National Human Rights Commission (established under the Protection of "
            "Human Rights Act, 1993) publishes Lodge & Track Complaints on nhrc.nic.in (page last updated 07-Apr-2026)."
        )
        bits.append(
            "File on HRCNet (https://hrcnet.nic.in/HRCNet/public/webcomplaint.aspx): pick the State of the incident, "
            "choose NHRC or the State Human Rights Commission, verify your mobile number with OTP, and keep the Unique "
            "Diary Number. HRCNet publishes NHRC toll-free 14433. Legalo does not file for you."
        )
        bits.append(
            "NHRC FAQ (retrieved 19 August 2026): complaints may be in Hindi, English or any Eighth Schedule language; "
            "they should be self-contained; no fee is charged. Other listed channels include post, email and Common "
            "Service Centres — confirm the live address on nhrc.nic.in/faq."
        )
        bits.append(
            "Legalo’s dated corpus does not include the Bharatiya Nyaya Sanhita, 2023 or the Indian Penal Code. "
            "It will not invent offence section numbers for a slap or assault. A station complaint or FIR, if you choose "
            "that path, must follow the live criminal-procedure law — verify on the official India Code / local police "
            "instructions; this tool will not draft unsourced charge language."
        )
    elif intent == "labour":
        bits.append(
            "This is a workplace dispute with an employer, not a consumer complaint (you were not buying goods) and not "
            "an RTI unless the record is held by a public authority such as EPFO. The Ministry of Labour and Employment "
            "portal is https://labour.gov.in/ (snapshot 19 August 2026). Use it to find the live State labour office."
        )
        bits.append(
            "The dated corpus does not include the Industrial Disputes Act or your State’s Shops and Establishments Act. "
            "Legalo will not invent those section numbers. Send a written demand first; then approach the competent "
            "labour machinery of the State where you worked. State law may differ."
        )
    dated = "; ".join(f"{s.title} s.{s.section} (published {s.published_on})" for s in sources[:5])
    bits.append(f"Sources used: {dated}.")
    bits.append("This is not legal advice. Review every draft. Legalo does not file on government portals.")
    return " ".join(bits)


def _explain_hi(intent: Intent, sources: list[SourceRef], slots: dict[str, str]) -> str:
    if intent == "unsupported" or not sources:
        return (
            "इस अनुरोध के लिए मेरे पास कोई आधिकारिक स्रोत-दस्तावेज़ नहीं है, इसलिए मैं उत्तर गढ़ूँगा नहीं। "
            "लीगैलो केवल दिनांकित कॉर्पस (RTI Act 2005, CPA 2019, Jurisdiction Rules 2021, Model Tenancy Act 2021) पर आधारित अधिकार बताता है।"
        )
    bits: list[str] = []
    if intent == "rti":
        bits.append(
            "आप लोक प्राधिकरण से उसके पास मौजूद अभिलेख माँग सकते हैं। RTI Act 2005 धारा 3 हर नागरिक को सूचना का अधिकार देती है। "
            "धारा 6 अंग्रेज़ी, हिन्दी या क्षेत्र की राजभाषा में लिखित/इलेक्ट्रॉनिक आवेदन की अनुमति देती है। कारण बताना ज़रूरी नहीं (धारा 6(2)), "
            "लेकिन नाम और डाक पता चाहिए।"
        )
        bits.append(
            "PIO को आवेदन मिलने के तीस दिन में निर्णय करना है (धारा 7(1)); जीवन/स्वतंत्रता पर 48 घंटे। समय पर उत्तर न देना माना गया इंकार है (धारा 7(2))। "
            "पहली अपील 30 दिन में वरिष्ठ अधिकारी को (धारा 19(1)); दूसरी अपील 90 दिन में सूचना आयोग को (धारा 19(3))।"
        )
        bits.append(
            "केंद्रीय लोक प्राधिकरणों के लिए आवेदन शुल्क ₹10 है (RTI Rules, 2012, G.S.R. 603(E), 31 July 2012, नियम 3)। "
            "BPL आवेदक नियम 5 के प्रमाणपत्र पर मुक्त हैं। राज्य सरकारें धारा 27–28 के अधीन अलग शुल्क अधिसूचित कर सकती हैं।"
        )
        bits.append(
            "rtionline.gov.in (DoPT, snapshot 18 August 2026) केवल केंद्र सरकार के मंत्रालयों/विभागों के लिए है। "
            "राज्य कार्यालयों (GNCT दिल्ली सहित) के लिए वहाँ दाखिल न करें — पोर्टल कहता है आवेदन बिना रिफंड लौटाया जा सकता है। "
            "लंबित राशन कार्ड आमतौर पर राज्य खाद्य एवं नागरिक आपूर्ति का विषय है।"
        )
        if slots.get("public_authority"):
            bits.append(f"आपके तथ्यों से सुझाया गया प्राधिकरण: {slots['public_authority']}।")
    elif intent == "consumer":
        bits.append(
            "यदि आपने व्यक्तिगत उपयोग के लिए सामान खरीदा या सेवा ली (ऑनलाइन सहित), तो आप CPA 2019 धारा 2(7) के उपभोक्ता हैं। "
            "दोष धारा 2(10), सेवा में कमी धारा 2(11)। धारा 2(9) में अनुचित व्यापार व्यवहार के विरुद्ध निवारण का अधिकार है।"
        )
        bits.append(
            "धारा 35 के अधीन जिला आयोग में शिकायत दाखिल की जा सकती है। मंच का निर्धारण चुकाए गए मूल्य (consideration) से होता है, "
            "दावा की गई क्षतिपूर्ति से नहीं: G.S.R. 912(E), 30 December 2021 — जिला ≤ ₹50 लाख, राज्य ₹50 लाख–₹2 करोड़, राष्ट्रीय > ₹2 करोड़। "
            "2019 अधिनियम की मूल सीमाएँ अब चालू नहीं हैं। दाखिल करने से पहले लाइव सीमा जाँचें।"
        )
        bits.append(
            "दाखिल करें e-Jagriti पर (https://e-jagriti.gov.in/) — उपभोक्ता मामले विभाग का नोडल पोर्टल "
            "(मंत्रालय पृष्ठ last updated 03-06-2025)। पुराना e-Daakhil 18 August 2026 को चालू नहीं माना गया। हेल्पलाइन 1915।"
        )
    elif intent == "tenant":
        bits.append(
            "Model Tenancy Act, 2021 (MoHUA, 2 June 2021) राज्यों/केंद्र शासित प्रदेशों के लिए एक मॉडल है। "
            "यह अपने-आप हर राज्य का कानून नहीं है। यदि आपके राज्य ने इसे नहीं अपनाया, तो उस राज्य का किराया/किरायेदारी अधिनियम देखें। राज्य कानून भिन्न हो सकता है।"
        )
        bits.append(
            "मॉडल धारा 20: मकान मालिक आवश्यक आपूर्ति (बिजली/पानी सहित) नहीं काट सकता। किराया प्राधिकरण से तत्काल बहाली का अंतरिम आदेश माँगा जा सकता है; जाँच एक महीने में; मुआवज़ा दो महीने के किराए तक।"
        )
        bits.append(
            "मॉडल धारा 21: बेदखली Rent Court के आदेश से, सूचीबद्ध आधारों पर होती है — दो दिन के अनौपचारिक पत्र से नहीं।"
        )
    elif intent == "nhrc":
        bits.append(
            "यह आरटीआई नहीं है और उपभोक्ता शिकायत भी नहीं है। पुलिस अधिकारी द्वारा बल प्रयोग का आरोप मानवाधिकार शिकायत है। "
            "राष्ट्रीय मानवाधिकार आयोग (Protection of Human Rights Act, 1993) nhrc.nic.in पर Lodge & Track Complaints प्रकाशित करता है "
            "(पृष्ठ last updated 07-Apr-2026)।"
        )
        bits.append(
            "HRCNet पर दाखिल करें (https://hrcnet.nic.in/HRCNet/public/webcomplaint.aspx): घटना का राज्य चुनें, NHRC या राज्य आयोग चुनें, "
            "मोबाइल OTP से सत्यापित करें, Unique Diary Number संभाल कर रखें। HRCNet पर टोल-फ्री 14433 प्रकाशित है। लीगैलो दाखिल नहीं करता।"
        )
        bits.append(
            "NHRC FAQ (प्राप्ति 19 August 2026): शिकायत हिन्दी, अंग्रेज़ी या आठवीं अनुसूची की भाषा में हो सकती है; स्वयंपूर्ण हो; शुल्क नहीं। "
            "BNS/IPC की धाराएँ इस कॉर्पस में नहीं हैं — लीगैलो वे गढ़ेगा नहीं।"
        )
    elif intent == "labour":
        bits.append(
            "यह नियोक्ता से कार्यस्थल विवाद है, उपभोक्ता शिकायत नहीं, और आरटीआई तभी जब अभिलेख EPFO जैसे लोक प्राधिकरण के पास हो। "
            "श्रम मंत्रालय पोर्टल https://labour.gov.in/ (19 August 2026)। राज्य श्रम कार्यालय वहीं से खोजें। IDA धाराएँ गढ़ेंगे नहीं। राज्य कानून भिन्न हो सकता है।"
        )
    dated = "; ".join(f"{s.title} s.{s.section} (published {s.published_on})" for s in sources[:5])
    bits.append(f"प्रयुक्त स्रोत: {dated}।")
    bits.append("यह कानूनी सलाह नहीं है। हर मसौदा जाँचें। लीगैलो सरकारी पोर्टल पर दाखिल नहीं करता।")
    return " ".join(bits)


def explain_for(language: str, intent: Intent, sources: list[SourceRef], slots: dict[str, str]) -> str:
    if language == "hi":
        return _explain_hi(intent, sources, slots)
    text = _explain(intent, sources, slots)
    if language not in ("en", "hi", ""):
        return rewrite_in_language(text, language, sources)
    return text


def _view(interp: Interpretation) -> InterpretationView:
    alts = [{"situation_type": a.situation_type, "why": a.why} for a in interp.alternatives]
    return InterpretationView(
        domain=interp.domain,
        situation_type=interp.situation_type,
        primary_action=interp.primary_action,
        secondary_action=interp.secondary_action,
        government_level=interp.government_level,
        benefit=interp.benefit,
        department_id=interp.department_id,
        department_label=department_label(interp),
        why=interp.why,
        not_this=interp.not_this,
        alternatives=alts,
        evidence=interp.evidence,
        confidence=interp.confidence,
        source=interp.source,
    )


def _fill_from_interp(case: "Case", interp: Interpretation) -> None:
    if interp.department_id and not case.slots.get("public_authority"):
        label = department_label(interp)
        if label:
            case.slots["public_authority"] = label
    if not case.slots.get("information_sought") and interp.domain == "welfare_records":
        case.slots["information_sought"] = information_sought(interp, case.slots)
    if interp.government_level != "unknown":
        case.slots.setdefault("scheme_level", interp.government_level)


def _banners(intent: Intent, sources: list[SourceRef]) -> list[str]:
    out = [
        "Not legal advice. Official procedures change — verify URLs, fees and forums on the live government site before you file."
    ]
    if intent == "tenant" or intent == "labour" or any(s.state_law_may_differ for s in sources):
        out.append("State law may differ. Verify the statute of the State where this happened. Model or Union texts are not automatically local law.")
    for s in sources:
        if s.stale_procedural:
            out.append(
                f"Verify on the official portal — “{s.title}” is dated {s.published_on} (retrieved {s.retrieved_on})."
            )
    seen: set[str] = set()
    uniq = []
    for b in out:
        if b not in seen:
            seen.add(b)
            uniq.append(b)
    return uniq


@dataclass
class Case:
    id: str
    language: str
    ui_locale: str
    raw_text: str
    notice_text: str = ""
    intent: Intent | None = None
    classifier: str = ""
    slots: dict[str, str] = field(default_factory=dict)
    pending_slot: str | None = None
    sources: list[SourceRef] = field(default_factory=list)
    interpretation: Interpretation | None = None

    @property
    def query_blob(self) -> str:
        return f"{self.raw_text}\n{self.notice_text}\n" + " ".join(self.slots.values())


class Engine:
    def __init__(self) -> None:
        self.docs = load_documents()
        self.chunks: list[Chunk] = load_chunks(self.docs)
        self.index = LexicalIndex(self.chunks)
        self.cases: dict[str, Case] = {}

    def _retrieve(self, intent: Intent, query: str) -> list[SourceRef]:
        allow = DOC_FILTER.get(intent) or None
        hits = self.index.search(query, k=settings.retrieve_k, doc_ids=allow)
        if not hits and allow:
            hits = [(c, 1.0) for c in self.chunks if c.doc_id in allow][: settings.retrieve_k]
        return [to_source_ref(c, settings.procedural_stale_days) for c, _ in hits]

    def _respond(self, case: Case) -> CaseResponse:
        interp = interpret(case.query_blob, case.slots, case.notice_text)
        case.interpretation = interp
        case.intent = intent_of(interp)
        case.classifier = interp.source
        _fill_from_interp(case, interp)
        view = _view(interp)

        if case.intent == "unsupported":
            return CaseResponse(
                case_id=case.id,
                step="understand",
                intent=case.intent,
                language=case.language,
                ui_locale=case.ui_locale,
                restatement=self._restate(case),
                interpretation=view,
                explanation=explain_for(case.language, "unsupported", [], case.slots),
                banners=_banners("unsupported", []),
                ready_for_pdf=False,
                trace=GenerationTrace(
                    template_id=None,
                    language=case.language,
                    source_ids=[],
                    llm_used=False,
                    classifier=case.classifier,
                ),
            )

        q = discriminating_question(interp, case.slots) or next_question(case.intent, case.slots, case.query_blob)
        if q:
            case.pending_slot = q.key
            return CaseResponse(
                case_id=case.id,
                step="understand",
                intent=case.intent,
                language=case.language,
                ui_locale=case.ui_locale,
                restatement=self._restate(case),
                interpretation=view,
                question=q,
                slots=case.slots,
                banners=_banners(case.intent, []),
                trace=GenerationTrace(
                    language=case.language,
                    source_ids=[],
                    llm_used=bool(settings.gemini_api_key),
                    classifier=case.classifier,
                ),
            )

        sources = self._retrieve(case.intent, case.query_blob)
        case.sources = sources
        if not sources:
            return CaseResponse(
                case_id=case.id,
                step="rights",
                intent=case.intent,
                language=case.language,
                ui_locale=case.ui_locale,
                restatement=self._restate(case),
                interpretation=view,
                slots=case.slots,
                explanation=explain_for(case.language, "unsupported", [], case.slots),
                banners=_banners(case.intent, []),
                ready_for_pdf=False,
            )

        explanation = interp.why + " " + explain_for(case.language, case.intent, sources, case.slots)
        if case.language == "hi":
            explanation = explain_for("hi", case.intent, sources, case.slots)
        path = build_path(case.intent, case.slots, sources)
        draft = None
        if interp.primary_action != "none":
            draft = build_draft(case.intent, case.slots, case.language)
        return CaseResponse(
            case_id=case.id,
            step="draft" if draft else "path",
            intent=case.intent,
            language=case.language,
            ui_locale=case.ui_locale,
            restatement=self._restate(case),
            interpretation=view,
            slots=case.slots,
            explanation=explanation,
            sources=sources,
            path=path,
            draft=draft,
            banners=_banners(case.intent, sources),
            ready_for_pdf=draft is not None,
            trace=GenerationTrace(
                template_id=draft.template_id if draft else None,
                language=case.language,
                source_ids=[s.chunk_id for s in sources],
                llm_used=bool(settings.gemini_api_key),
                classifier=case.classifier,
            ),
        )

    def _restate(self, case: Case) -> str:
        blob = (case.notice_text or case.raw_text).strip().replace("\n", " ")
        return blob[:500]

    def create(self, text: str, language: str, ui_locale: str) -> CaseResponse:
        lang = language if language and language != "auto" else detect_language(text)
        detected = detect_language(text)
        if language in ("en", "", "auto") and detected != "en":
            lang = detected
        interp = interpret(text)
        intent = intent_of(interp)
        case = Case(
            id=str(uuid.uuid4())[:8],
            language=lang,
            ui_locale=ui_locale or "en",
            raw_text=text,
            intent=intent,
            classifier=interp.source,
            slots=extract_from_text(intent, text),
            interpretation=interp,
        )
        self.cases[case.id] = case
        return self._respond(case)

    def attach_notice(self, case_id: str, filename: str, data: bytes, ocr_text: str) -> CaseResponse:
        case = self.cases[case_id]
        case.notice_text = ocr_text
        case.raw_text = (case.raw_text + "\n" + ocr_text).strip()
        interp = interpret(case.raw_text, case.slots, ocr_text)
        case.intent = intent_of(interp)
        case.classifier = interp.source
        case.interpretation = interp
        case.slots.update(extract_from_text(case.intent, case.raw_text))
        return self._respond(case)

    def message(self, case_id: str, text: str, language: str | None) -> CaseResponse:
        case = self.cases[case_id]
        if language:
            case.language = language
        key = case.pending_slot
        case.slots = apply_answer(case.intent or "unsupported", case.slots, key, text)
        case.pending_slot = None
        case.raw_text = (case.raw_text + "\n" + text).strip()
        if case.intent in (None, "unsupported"):
            interp = interpret(case.raw_text, case.slots, case.notice_text)
            case.intent = intent_of(interp)
            case.classifier = interp.source
            case.slots.update(extract_from_text(case.intent, case.raw_text))
        return self._respond(case)

    def patch_draft(self, case_id: str, fields: dict[str, str]) -> CaseResponse:
        case = self.cases[case_id]
        case.slots.update({k: v for k, v in fields.items() if v is not None})
        return self._respond(case)

    def get(self, case_id: str) -> Case:
        if case_id not in self.cases:
            raise KeyError(case_id)
        return self.cases[case_id]


engine = Engine()
