import chunksJson from "@/data/chunks.json";
import documentsJson from "@/data/documents.json";
import templatesJson from "@/data/templates.json";
import type { CaseResponse, DraftBody, PathStep, ProvenanceRow, SourceRef } from "@/lib/api";
import {
  applyDiscriminator,
  departmentLabel,
  detectState,
  discriminatingQuestion,
  informationSought,
  intentOf,
  interpret,
  type Intent,
  type Interpretation,
} from "@/lib/civic/interpret";

const DOC_FILTER: Record<Intent, Set<string>> = {
  rti: new Set(["rti-act-2005", "rti-rules-2012", "rti-faq-dopt-2012", "rti-online-portal", "epfo-portal"]),
  consumer: new Set(["cpa-2019", "cpa-jurisdiction-rules-2021", "e-jagriti-portal"]),
  tenant: new Set(["model-tenancy-act-2021"]),
  nhrc: new Set(["nhrc-hrcnet-portal", "nhrc-faq-complaints"]),
  labour: new Set(["labour-gov-portal"]),
  unsupported: new Set(),
};

type Doc = {
  id: string;
  title: string;
  publisher: string;
  source_url: string;
  doc_type: string;
  published_on: string;
  effective_on: string;
  retrieved_on: string;
  notes: string;
  stale_procedural: boolean;
  state_law_may_differ: boolean;
};

type Chunk = { id: string; doc_id: string; section: string; title: string; text: string };

const DOCS = Object.fromEntries((documentsJson as Doc[]).map((d) => [d.id, d]));
const CHUNKS = chunksJson as Chunk[];
const TEMPLATES = templatesJson as Record<string, string>;

function tokenize(text: string) {
  return (text.toLowerCase().match(/[\p{L}\p{N}]+/gu) || []).filter((t) => t.length > 1);
}

function retrieve(intent: Intent, query: string): SourceRef[] {
  const allow = DOC_FILTER[intent];
  const q = tokenize(query);
  const pool = CHUNKS.filter((c) => !allow.size || allow.has(c.doc_id));
  const scored = pool
    .map((c) => {
      const toks = new Set(tokenize(`${c.title} ${c.section} ${c.text}`));
      const score = q.reduce((s, t) => s + (toks.has(t) ? 1 : 0), 0);
      return { c, score };
    })
    .filter((x) => x.score > 0)
    .sort((a, b) => b.score - a.score)
    .slice(0, 6);
  const hits = scored.length ? scored.map((x) => x.c) : pool.slice(0, 6);
  return hits.map((c) => {
    const d = DOCS[c.doc_id];
    return {
      chunk_id: c.id,
      doc_id: c.doc_id,
      title: d?.title || c.title,
      publisher: d?.publisher || "",
      section: c.section,
      source_url: d?.source_url || "",
      published_on: d?.published_on || "",
      effective_on: d?.effective_on || "",
      retrieved_on: d?.retrieved_on || "",
      doc_type: d?.doc_type || "",
      stale_procedural: !!d?.stale_procedural,
      state_law_may_differ: !!d?.state_law_may_differ,
      notes: d?.notes || "",
    };
  });
}

function explain(intent: Intent, sources: SourceRef[], slots: Record<string, string>, language: string) {
  if (intent === "unsupported" || !sources.length) {
    return language === "hi"
      ? "इस अनुरोध के लिए मेरे पास कोई आधिकारिक स्रोत-दस्तावेज़ नहीं है, इसलिए मैं उत्तर गढ़ूँगा नहीं। लीगैलो केवल दिनांकित कॉर्पस पर आधारित अधिकार बताता है।"
      : "I do not have a sourced official document for this request, so I will not invent an answer. Legalo only explains rights that are grounded in the dated corpus (RTI Act 2005, CPA 2019, jurisdiction Rules 2021, Model Tenancy Act 2021, NHRC/HRCNet, labour.gov.in, and official portal snapshots).";
  }
  const bits: string[] = [];
  if (intent === "rti") {
    bits.push(
      "You can ask a public authority for records it holds. RTI Act 2005 s.3 gives every citizen the right to information, subject to the Act. s.6 lets you apply in writing or electronically in English, Hindi or the official language of the area. You do not have to give reasons (s.6(2)). You do need a name and postal address so they can contact you."
    );
    bits.push(
      "The PIO must decide within thirty days of receiving the request (s.7(1)); if the information concerns life or liberty, within forty-eight hours. Silence after that period is a deemed refusal (s.7(2)). First appeal: thirty days to the senior officer (s.19(1)). Second appeal: ninety days to the Information Commission (s.19(3))."
    );
    bits.push(
      "For Central public authorities the application fee is ₹10 (RTI Rules, 2012, G.S.R. 603(E) dated 31 July 2012, rule 3). BPL applicants are exempt with the certificate in rule 5. State Governments may notify different fees under ss.27–28."
    );
    bits.push(
      "rtionline.gov.in (DoPT, snapshot 18 August 2026) is only for Central Ministries/Departments and other Central public authorities. Do not file there for State offices, including GNCT Delhi — the portal says such applications are returned without refund."
    );
    if (slots.benefit === "ration") bits.push("A pending ration-card file is a State Food & Civil Supplies matter.");
    if (slots.benefit === "scholarship") {
      bits.push("A scholarship file is State education unless it is a Central/NSP scheme. That distinction is the routing decision — not a translation of the word scholarship.");
    }
    if (slots.benefit === "pf") bits.push("EPFO is a Central public authority. Confirm it on the live RTI portal before using rtionline.gov.in.");
  } else if (intent === "consumer") {
    bits.push(
      "If you bought goods or hired a service for personal use (including online), you are a consumer under CPA 2019 s.2(7). A defect is s.2(10); a deficiency in service is s.2(11). Consumer rights in s.2(9) include the right to seek redressal against unfair trade practice."
    );
    bits.push(
      "You may file a complaint with the District Commission under s.35. Which Commission hears it depends on consideration paid, not on how much compensation you claim: G.S.R. 912(E) of 30 December 2021 sets District ≤ ₹50 lakh, State ₹50 lakh–₹2 crore, National > ₹2 crore. Those rules replaced the original 2019 Act figures (₹1 crore / ₹10 crore). Confirm the live limit before filing."
    );
    bits.push(
      "File on e-Jagriti (https://e-jagriti.gov.in/), the Department of Consumer Affairs nodal platform (ministry page last updated 03-06-2025). The older e-Daakhil site is not treated as current as of 18 August 2026. Helpline 1915."
    );
  } else if (intent === "tenant") {
    bits.push(
      "The Model Tenancy Act, 2021 (MoHUA, approved 2 June 2021) is a model for States and UTs. It is not automatically the law of every State. If your State has not enacted it, follow that State's rent control / tenancy statute. The points below are from the model and may differ locally."
    );
    bits.push(
      "Model s.20: a landlord or property manager shall not withhold essential supply or service, including electricity and water. You may apply to the Rent Authority for an interim restoration order; inquiry within one month; compensation up to two months' rent."
    );
    bits.push(
      "Model s.21: eviction is an order of the Rent Court on listed grounds after notice — not a two-day informal letter. A notice to vacate in 48 hours, by itself, is not an eviction order under this model."
    );
  } else if (intent === "nhrc") {
    bits.push(
      "This is not an RTI and not a consumer complaint. A complaint that a police officer used force against you is a human-rights complaint. The National Human Rights Commission (established under the Protection of Human Rights Act, 1993) publishes Lodge & Track Complaints on nhrc.nic.in (page last updated 07-Apr-2026)."
    );
    bits.push(
      "File on HRCNet (https://hrcnet.nic.in/HRCNet/public/webcomplaint.aspx): pick the State of the incident, choose NHRC or the State Human Rights Commission, verify your mobile number with OTP, and keep the Unique Diary Number. HRCNet publishes NHRC toll-free 14433. Legalo does not file for you."
    );
    bits.push(
      "Legalo’s dated corpus does not include the Bharatiya Nyaya Sanhita, 2023 or the Indian Penal Code. It will not invent offence section numbers."
    );
  } else if (intent === "labour") {
    bits.push(
      "This is a workplace dispute with an employer, not a consumer complaint and not an RTI unless the record is held by a public authority such as EPFO. The Ministry of Labour and Employment portal is https://labour.gov.in/ (snapshot 19 August 2026)."
    );
    bits.push(
      "The dated corpus does not include the Industrial Disputes Act or your State’s Shops and Establishments Act. Legalo will not invent those section numbers. State law may differ."
    );
  }
  bits.push(`Sources used: ${sources.slice(0, 5).map((s) => `${s.title} s.${s.section} (published ${s.published_on})`).join("; ")}.`);
  bits.push("This is not legal advice. Review every draft. Legalo does not file on government portals.");
  return bits.join(" ");
}

function fill(templateId: string, fields: Record<string, string>) {
  let src = TEMPLATES[templateId] || "";
  for (const [k, v] of Object.entries(fields)) {
    src = src.replaceAll(`{{ ${k} }}`, v).replaceAll(`{{${k}}}`, v);
  }
  return src;
}

function htmlToPlain(html: string) {
  return html
    .replace(/<\/(p|div|li|h1)>/g, "\n")
    .replace(/<br\s*\/?>/g, "\n")
    .replace(/<[^>]+>/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function today() {
  return new Date().toISOString().slice(0, 10);
}

function buildPath(intent: Intent, slots: Record<string, string>): PathStep[] {
  if (intent === "rti") {
    const portal =
      slots.scheme_level === "union"
        ? "This file looks Central — rtionline.gov.in may be the right channel. Confirm the public authority is Central."
        : slots.scheme_level === "state" || (slots.public_authority || "").includes("State")
          ? "This file looks like a State authority (scholarship/PDS/education). File with the State PIO or State RTI portal, not rtionline.gov.in."
          : "If you still do not know whether the scheme is Central (e.g. NSP) or State, do not file yet — the wrong portal wastes the fee.";
    return [
      { title: "Review and sign the RTI draft", detail: "Section 6 does not require you to give reasons. Keep the request precise." },
      { title: "Pay the fee if it applies", detail: "For Central public authorities the application fee is ₹10 (RTI Rules, 2012, rule 3).", deadline: "Pay with the application" },
      {
        title: "File with the correct PIO — Central vs State",
        detail: "rtionline.gov.in is only for Central Ministries/Departments and other Central public authorities. " + portal,
        url: "https://rtionline.gov.in/",
        verify: "Confirm the live instructions on rtionline.gov.in. Snapshot retrieved 2026-08-18.",
      },
      { title: "Wait thirty days, then appeal", detail: "PIO must decide within thirty days of receipt (section 7(1)). First appeal within thirty days (section 19(1)).", deadline: "30 days from PIO receipt" },
    ];
  }
  if (intent === "consumer") {
    return [
      { title: "Collect proof", detail: "Invoice, warranty, chat/email with the seller, photos of the defect. You are a consumer under CPA 2019 s.2(7)." },
      { title: "Pick the Commission by consideration paid", detail: "G.S.R. 912(E) dated 30 December 2021: District ≤ ₹50 lakh; State ₹50 lakh–₹2 crore; National above ₹2 crore.", verify: "PIB PRID 1786342; confirm live limits on e-jagriti.gov.in." },
      { title: "File on e-Jagriti — not e-Daakhil", detail: "Nodal portal https://e-jagriti.gov.in/ (ministry page last updated 03-06-2025). edaakhil.nic.in is not treated as current.", url: "https://e-jagriti.gov.in/", verify: "Open e-jagriti.gov.in and follow the live screens." },
      { title: "Helpline", detail: "National Consumer Helpline 1915." },
    ];
  }
  if (intent === "tenant") {
    const st = slots.state || "the State where the house is";
    return [
      { title: "State law first", detail: `The Model Tenancy Act, 2021 applies in ${st} only if ${st} has enacted it.`, verify: "MoHUA Model Tenancy Act PDF; State gazette." },
      { title: "Essential services cannot be cut as pressure", detail: "Model s.20: a landlord shall not withhold essential supply including electricity." },
      { title: "A two-day notice is not an eviction order", detail: "Model s.21: eviction is by Rent Court on listed grounds — not by informal 48-hour letters." },
      { title: "Send a written representation and keep proof", detail: "Use the draft reply. This tool does not file for you." },
    ];
  }
  if (intent === "nhrc") {
    return [
      { title: "Write a self-contained complaint — no invented offence sections", detail: "NHRC FAQ: complaints should be self-contained. Legalo will not insert BNS/IPC section numbers." },
      { title: "Lodge on HRCNet (NHRC or State Commission)", detail: "nhrc.nic.in Lodge & Track (last updated 07-Apr-2026) opens HRCNet. OTP + Unique Diary Number.", url: "https://hrcnet.nic.in/HRCNet/public/webcomplaint.aspx", verify: "Confirm live fields on HRCNet. Snapshot retrieved 2026-08-19." },
      { title: "No fee; language", detail: "Hindi, English or any Eighth Schedule language; no fee.", url: "https://nhrc.nic.in/faq" },
    ];
  }
  if (intent === "labour") {
    const st = slots.state || "the State where you worked";
    return [
      { title: "Write a demand to the employer first", detail: "Do not paste invented IDA/Shops Act section numbers." },
      { title: "Find the live labour office", detail: `Locate the labour machinery of ${st} via the Union labour portal.`, url: "https://labour.gov.in/", verify: "Confirm live State labour office links on labour.gov.in." },
      { title: "PF is a different route", detail: "If the missing money is provident-fund, that is an EPFO/RTI path.", url: "https://www.epfindia.gov.in/" },
    ];
  }
  return [];
}

function buildDraft(intent: Intent, slots: Record<string, string>, language: string): DraftBody | null {
  const date = today();
  if (intent === "rti") {
    const fields = {
      public_authority: slots.public_authority || "[public authority]",
      public_authority_address: slots.state || "[office address / district]",
      applicant_name: slots.applicant_name || "[name]",
      applicant_address: slots.applicant_address || "[address]",
      applicant_contact: slots.applicant_contact || "[contact]",
      information_sought: slots.information_sought || "[particulars]",
      period: slots.period || "From the date of application to the date of this RTI",
      delivery: "By post / email to the address above",
      place: slots.state || "",
      date,
      retrieved_on: "2026-08-18",
    };
    const html = fill("rti", fields);
    return { template_id: "rti", title: "RTI application (section 6)", language, fields, html, plain: htmlToPlain(html) };
  }
  if (intent === "consumer") {
    const amount = slots.amount || "0";
    const val = parseInt(String(amount).replace(/[,]/g, ""), 10) || 0;
    let forum = "DISTRICT CONSUMER DISPUTES REDRESSAL COMMISSION";
    if (val > 2_00_00_000) forum = "NATIONAL CONSUMER DISPUTES REDRESSAL COMMISSION";
    else if (val > 50_00_000) forum = "STATE CONSUMER DISPUTES REDRESSAL COMMISSION";
    const fields = {
      forum,
      forum_place: slots.complainant_address || "[district]",
      complainant_name: slots.complainant_name || "[name]",
      complainant_address: slots.complainant_address || "[address]",
      opposite_party: slots.opposite_party || "[seller]",
      opposite_party_address: slots.opposite_party_address || "[seller address]",
      purchase_date: slots.purchase_date || "[date]",
      goods_service: slots.goods_service || "[goods/service]",
      amount: String(amount),
      defect: slots.defect || "[defect]",
      prior_contact: slots.prior_contact || "several occasions",
      cause_place: slots.complainant_address || "[place]",
      relief: slots.relief || "Refund of the consideration paid",
      place: slots.complainant_address || "",
      date,
      retrieved_on: "2026-08-18",
    };
    const html = fill("consumer", fields);
    return { template_id: "consumer", title: "Consumer complaint draft (CPA 2019 s.35)", language, fields, html, plain: htmlToPlain(html) };
  }
  if (intent === "tenant") {
    const issue = slots.issue || "unlawful pressure in respect of the tenancy";
    const fields = {
      tenant_address: slots.premises || "",
      date,
      landlord_name: slots.landlord_name || "[landlord]",
      landlord_address: slots.landlord_address || "",
      issue_title: issue.slice(0, 80),
      premises: slots.premises || "[premises]",
      facts: `On ${slots.facts_date || "[date]"}: ${issue}`,
      legal_paragraph:
        "The Model Tenancy Act, 2021 s.20 (MoHUA, 2 June 2021) says no landlord shall withhold essential supply including electricity. s.21 channels eviction through a Rent Court on listed grounds. This is model law — confirm whether your State has enacted it.",
      request: "immediately restore essential supply and withdraw any extra-legal eviction threat",
      state: slots.state || "[State]",
      tenant_name: slots.tenant_name || "[name]",
      tenant_contact: slots.tenant_contact || "",
      retrieved_on: "2026-08-18",
    };
    const html = fill("tenant", fields);
    return { template_id: "tenant", title: "Tenant representation (Model Tenancy Act 2021)", language, fields, html, plain: htmlToPlain(html) };
  }
  if (intent === "nhrc") {
    const fields = {
      commission: "National Human Rights Commission / the State Human Rights Commission of the incident State",
      date,
      complainant_name: slots.complainant_name || slots.applicant_name || "[name]",
      complainant_contact: slots.complainant_contact || slots.applicant_contact || "[contact / address]",
      state: slots.state || "[State / UT of incident]",
      facts: slots.facts || slots.issue || "[Describe what the officer did, with date, place, and any witness or injury details.]",
      place_time: slots.place_time || "[place and date/time]",
      officer_detail: slots.officer_detail || "[station / name / belt number if known; else unknown]",
      relief: slots.relief || "Inquire into the incident, record the officer’s identity, and recommend action and relief as the Commission finds fit.",
      retrieved_on: "2026-08-19",
    };
    const html = fill("nhrc", fields);
    return { template_id: "nhrc", title: "Human rights complaint draft (HRCNet)", language, fields, html, plain: htmlToPlain(html) };
  }
  if (intent === "labour") {
    const fields = {
      worker_address: slots.worker_address || slots.state || "",
      date,
      employer_name: slots.employer_name || "[employer]",
      employer_address: slots.employer_address || "[employer address]",
      issue_title: (slots.issue || "unpaid wages / termination").slice(0, 80),
      facts: slots.facts || slots.issue || "[period, amount, what happened]",
      request: slots.request || "pay the outstanding wages / reverse the unlawful termination and reply in writing",
      state: slots.state || "[State]",
      worker_name: slots.worker_name || slots.complainant_name || "[name]",
      worker_contact: slots.worker_contact || slots.complainant_contact || "[contact]",
      retrieved_on: "2026-08-19",
    };
    const html = fill("labour", fields);
    return { template_id: "labour", title: "Workplace demand letter (no unsourced IDA sections)", language, fields, html, plain: htmlToPlain(html) };
  }
  return null;
}

function extract(intent: Intent, text: string) {
  const found: Record<string, string> = {};
  const interp = interpret(text, {});
  if (interp.benefit) found.benefit = interp.benefit;
  const st = detectState(text);
  if (st) found.state = st;
  if (intent === "consumer") {
    const m = text.match(/(?:₹|rs\.?|inr|rupees?)\s*([0-9][0-9,]*)/i) || text.match(/\b([0-9]{4,7})\b/);
    if (m) found.amount = m[1].replace(/,/g, "");
    if (/phone|smartphone|mobile/i.test(text)) found.goods_service = "smartphone";
    if (/refund/i.test(text)) found.relief = "Refund of the purchase amount with compensation for harassment";
    if (/lucknow/i.test(text)) found.complainant_address = "Lucknow, Uttar Pradesh";
    if (/last month/i.test(text)) found.purchase_date = "last month (exact date to be filled by complainant)";
    if (/refused|no returns/i.test(text)) found.defect = "Device is defective; seller refused refund citing a no-returns policy.";
    if (/shop/i.test(text)) found.opposite_party = "The retail shop that sold the goods (name to be completed)";
  }
  if (intent === "nhrc") {
    found.facts = text.trim().slice(0, 800);
    if (/slap/i.test(text)) found.issue = "Alleged slap / use of force by a police officer.";
  }
  if (intent === "labour") {
    found.facts = text.trim().slice(0, 800);
    found.issue = "Unpaid wages / termination by employer (complete dates and amounts).";
  }
  if (intent === "tenant") {
    if (/electric/i.test(text)) found.issue = "Landlord withheld electricity / essential supply and demanded vacation of the premises.";
    if (/two days|2 days|vacate/i.test(text)) found.issue = (found.issue || "") + " Informal notice to vacate within two days.";
  }
  return found;
}

function viewOf(interp: Interpretation) {
  return {
    domain: interp.domain,
    situation_type: interp.situation_type,
    primary_action: interp.primary_action,
    secondary_action: interp.secondary_action,
    government_level: interp.government_level,
    benefit: interp.benefit,
    department_id: interp.department_id,
    department_label: departmentLabel(interp),
    why: interp.why,
    not_this: interp.not_this,
    alternatives: interp.alternatives,
    evidence: interp.evidence,
    confidence: interp.confidence,
    source: interp.source,
  };
}

type Case = {
  id: string;
  language: string;
  ui_locale: string;
  raw_text: string;
  notice_text: string;
  slots: Record<string, string>;
  pending_slot: string | null;
};

function banners(intent: Intent, sources: SourceRef[]) {
  const out = ["Not legal advice. Official procedures change — verify URLs, fees and forums on the live government site before you file."];
  if (intent === "tenant" || intent === "labour" || sources.some((s) => s.state_law_may_differ)) {
    out.push("State law may differ. Verify the statute of the State where this happened. Model or Union texts are not automatically local law.");
  }
  for (const s of sources) {
    if (s.stale_procedural) out.push(`Verify on the official portal — “${s.title}” is dated ${s.published_on} (retrieved ${s.retrieved_on}).`);
  }
  return [...new Set(out)];
}

function respond(case_: Case): CaseResponse {
  const interp = interpret(case_.raw_text, case_.slots, case_.notice_text);
  const intent = intentOf(interp);
  if (interp.department_id && !case_.slots.public_authority) {
    const label = departmentLabel(interp);
    if (label) case_.slots.public_authority = label;
  }
  if (!case_.slots.information_sought && interp.domain === "welfare_records") {
    case_.slots.information_sought = informationSought(interp);
  }
  if (interp.government_level !== "unknown") case_.slots.scheme_level ||= interp.government_level;
  if (interp.benefit) case_.slots.benefit ||= interp.benefit;

  const base = {
    case_id: case_.id,
    intent,
    language: case_.language,
    ui_locale: case_.ui_locale,
    restatement: (case_.notice_text || case_.raw_text).replace(/\n/g, " ").slice(0, 500),
    interpretation: viewOf(interp),
    slots: case_.slots,
    sources: [] as SourceRef[],
    path: [] as PathStep[],
    banners: banners(intent, []),
    ready_for_pdf: false,
    routed_on_device: true,
  };

  if (intent === "unsupported") {
    return { ...base, step: "understand", explanation: explain("unsupported", [], case_.slots, case_.language) };
  }

  const q = discriminatingQuestion(interp, case_.slots);
  if (q) {
    case_.pending_slot = q.key;
    return { ...base, step: "understand", question: q };
  }

  const sources = retrieve(intent, case_.raw_text);
  const explanation = interp.why + " " + explain(intent, sources, case_.slots, case_.language);
  const path = buildPath(intent, case_.slots);
  const draft = interp.primary_action === "none" ? null : buildDraft(intent, case_.slots, case_.language);
  return {
    ...base,
    step: draft ? "draft" : "path",
    explanation,
    sources,
    path,
    draft: draft || undefined,
    banners: banners(intent, sources),
    ready_for_pdf: !!draft,
  };
}

const CASES = new Map<string, Case>();

function newId() {
  return Math.random().toString(36).slice(2, 10);
}

export function localCreate(text: string, language: string, uiLocale: string): CaseResponse {
  const interp = interpret(text);
  const intent = intentOf(interp);
  const id = newId();
  const case_: Case = {
    id,
    language: language || "en",
    ui_locale: uiLocale || "en",
    raw_text: text,
    notice_text: "",
    slots: extract(intent, text),
    pending_slot: null,
  };
  CASES.set(id, case_);
  return respond(case_);
}

export function localMessage(caseId: string, text: string, language: string): CaseResponse {
  const case_ = CASES.get(caseId);
  if (!case_) throw new Error("Unknown case");
  if (language) case_.language = language;
  const key = case_.pending_slot;
  case_.slots = applyDiscriminator(case_.slots, key, text);
  if (key && key !== "pending_kind" && key !== "scheme_level" && text.trim()) case_.slots[key] = text.trim();
  const extra = extract(intentOf(interpret(case_.raw_text + " " + text, case_.slots)), text);
  for (const [k, v] of Object.entries(extra)) case_.slots[k] ||= v;
  case_.pending_slot = null;
  case_.raw_text = `${case_.raw_text}\n${text}`.trim();
  return respond(case_);
}

export function localUpload(caseId: string, notice: string): CaseResponse {
  const case_ = CASES.get(caseId);
  if (!case_) throw new Error("Unknown case");
  case_.notice_text = notice;
  case_.raw_text = `${case_.raw_text}\n${notice}`.trim();
  const intent = intentOf(interpret(case_.raw_text, case_.slots, notice));
  Object.assign(case_.slots, extract(intent, case_.raw_text));
  return respond(case_);
}

export function localPatch(caseId: string, fields: Record<string, string>): CaseResponse {
  const case_ = CASES.get(caseId);
  if (!case_) throw new Error("Unknown case");
  Object.assign(case_.slots, fields);
  return respond(case_);
}

export function localProvenance(): ProvenanceRow[] {
  return (documentsJson as Doc[])
    .slice()
    .sort((a, b) => a.published_on.localeCompare(b.published_on))
    .map((d) => ({
      id: d.id,
      title: d.title,
      publisher: d.publisher,
      doc_type: d.doc_type,
      published_on: d.published_on,
      effective_on: d.effective_on,
      retrieved_on: d.retrieved_on,
      source_url: d.source_url,
      notes: d.notes,
    }));
}
