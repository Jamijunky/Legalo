import pathways from "@/data/pathways.json";
import directory from "@/data/directory.json";

export type Domain =
  | "welfare_records"
  | "consumer"
  | "tenancy"
  | "police_accountability"
  | "workplace"
  | "unsupported";

export type Intent = "rti" | "consumer" | "tenant" | "nhrc" | "labour" | "unsupported";

const PENDING_KINDS = [
  "pending_application",
  "disbursement_failed",
  "verification_gap",
  "eligibility_question",
] as const;

export type Interpretation = {
  domain: Domain;
  situation_type: string;
  primary_action: string;
  secondary_action?: string | null;
  government_level: "union" | "state" | "unknown";
  benefit?: string | null;
  department_id?: string | null;
  why: string;
  not_this: string;
  alternatives: { situation_type: string; why: string }[];
  evidence: string[];
  confidence: number;
  needs_pending_kind: boolean;
  needs_scheme_level: boolean;
  source: string;
};

const TABLE = pathways as {
  benefits: Record<string, { department_union?: string | null; department_state?: string | null }>;
  pathways: Record<string, { primary_action?: string; secondary_action?: string | null; why_en?: string; not_en?: string }>;
};

function has(blob: string, ...needles: string[]) {
  const low = blob.toLowerCase();
  return needles.some((n) => {
    const nlow = n.toLowerCase();
    if (nlow.length <= 3 && /^[\x00-\x7F]+$/.test(nlow) && /[a-z0-9]$/i.test(nlow)) {
      return new RegExp(`\\b${nlow.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\b`, "i").test(blob);
    }
    return low.includes(nlow);
  });
}

export function detectBenefit(blob: string): string | null {
  if (has(blob, "provident", "epf", "epfo", "uan") || (/\bpf\b/i.test(blob) && has(blob, "fund", "pending", "contribution", "employer", "withdraw"))) {
    return "pf";
  }
  if (has(blob, "scholarship", "छात्रवृत्ति", "nsp")) return "scholarship";
  if (has(blob, "ration", "राशन", "pds", "nfsa", "ration card")) return "ration";
  if (has(blob, "pension", "पेंशन")) return "pension";
  return null;
}

export function detectState(blob: string): string | null {
  const mapping: [RegExp, string][] = [
    [/prayagraj|allahabad|lucknow|noida|uttar pradesh|\bup\b|उत्तर प्रदेश|प्रयागराज|लखनऊ/i, "Uttar Pradesh"],
    [/mumbai|pune|maharashtra|महाराष्ट्र/i, "Maharashtra"],
    [/bengaluru|bangalore|karnataka/i, "Karnataka"],
    [/chennai|tamil nadu/i, "Tamil Nadu"],
    [/hyderabad|telangana/i, "Telangana"],
    [/delhi|gnct/i, "Delhi"],
    [/patna|bihar/i, "Bihar"],
    [/jaipur|rajasthan/i, "Rajasthan"],
    [/kolkata|west bengal/i, "West Bengal"],
  ];
  for (const [pat, name] of mapping) if (pat.test(blob)) return name;
  return null;
}

function detectLevel(blob: string, benefit: string | null): "union" | "state" | "unknown" {
  if (benefit === "pf") return "union";
  if (has(blob, "nsp", "national scholarship", "central scheme", "pm-")) return "union";
  if (has(blob, "state scholarship", "state scheme")) return "state";
  if (benefit === "ration") return "state";
  if (has(blob, "prayagraj", "lucknow", "uttar pradesh", "उत्तर प्रदेश", "state government")) {
    return benefit === "scholarship" ? "unknown" : "state";
  }
  return "unknown";
}

function pendingKindFromText(blob: string): string | null {
  if (has(blob, "am i eligible", "do i qualify", "eligibility", "क्या मैं पात्र", "पात्रता", "पात्र हूँ", "पात्र हूं")) return "eligibility_question";
  if (has(blob, "approved", "selected", "sanctioned", "money has not", "payment not", "disburs", "dbt", "amount not credit")) {
    return "disbursement_failed";
  }
  if (has(blob, "kyc", "verification", "document pending", "ask for document", "aadhaar pending")) return "verification_gap";
  if (has(blob, "file noting", "status of my", "certified cop", "copies of", "want the status", "प्रतियाँ", "स्थिति")) {
    return "explicit_information_request";
  }
  if (has(blob, "pending", "stuck", "no update", "heard nothing", "लंबित", "अटका", "चार महीने", "four month")) {
    return "pending_application";
  }
  return null;
}

function isPoliceAssault(blob: string) {
  const actor = has(blob, "police", "constable", "inspector", "थाना", "पुलिस") || (has(blob, "officer") && has(blob, "police", "पुलिस"));
  const harm = has(
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
    "मारा"
  );
  return actor && harm;
}

function isWorkplace(blob: string) {
  if (has(blob, "refund", "defective", "smartphone", "landlord", "tenant")) return false;
  return (
    has(blob, "unpaid salary", "salary unpaid", "wages not paid", "unpaid wages", "employer fired", "terminated me", "i was fired", "retrench", "वेतन नहीं", "नौकरी से निकाल") ||
    (has(blob, "employer", "naukri", "नियोक्ता") && has(blob, "salary", "wage", "fired", "terminat", "वेतन"))
  );
}

function isTenancy(blob: string) {
  const negated = has(blob, "not a tenant", "not the tenant", "i am not a tenant");
  const landlordish = has(blob, "landlord", "मकान मालिक", "evict", "vacate", "खाली कर", "किरायेदार");
  if (negated && !landlordish) return false;
  return has(blob, "landlord", "tenant", "evict", "vacate", "मकान मालिक", "किरायेदार", "खाली कर");
}

function isConsumer(blob: string) {
  return has(blob, "refund", "defective", "warranty", "smartphone", "वापसी", "खराब");
}

function isBareRtiQuestion(blob: string) {
  return has(blob, "what is rti", "explain the act", "meaning of rti", "what is the rti");
}

function domainFromBlob(blob: string): Domain {
  if (isPoliceAssault(blob)) return "police_accountability";
  if (isWorkplace(blob)) return "workplace";
  if (isTenancy(blob)) return "tenancy";
  if (isConsumer(blob)) return "consumer";
  if (detectBenefit(blob) === "pf") return "welfare_records";
  if (detectBenefit(blob) || has(blob, "application has been pending", "public authority", "file noting", "certified cop")) {
    return "welfare_records";
  }
  if (has(blob, "rti") && !isBareRtiQuestion(blob)) return "welfare_records";
  return "unsupported";
}

export function interpret(text: string, slots: Record<string, string> = {}, notice = ""): Interpretation {
  const citizen = `${text}\n${notice}`;
  const blob = `${citizen}\n` + Object.entries(slots).map(([k, v]) => `${k}=${v}`).join(" ");
  let domain = domainFromBlob(citizen);
  let benefit = detectBenefit(citizen) || slots.benefit || null;
  let level = detectLevel(citizen, benefit);
  if (slots.scheme_level === "union" || slots.scheme_level === "state") level = slots.scheme_level;
  if (isPoliceAssault(blob)) domain = "police_accountability";
  if (isWorkplace(blob) && domain !== "consumer" && domain !== "tenancy" && domain !== "police_accountability" && benefit !== "pf") {
    domain = "workplace";
  }

  let situation = slots.pending_kind || pendingKindFromText(blob);
  const evidence: string[] = [];
  if (benefit) evidence.push(`benefit=${benefit}`);
  if (situation) evidence.push(`kind=${situation}`);
  const st = detectState(blob) || slots.state;
  if (st) {
    evidence.push(`place=${st}`);
    slots.state ||= st;
  }

  let alternatives: { situation_type: string; why: string }[] = [];
  let needs_kind = false;
  let needs_level = false;

  if (domain === "tenancy") {
    if (has(blob, "electric", "बिजली", "water cut", "essential")) {
      situation = "essential_supply_cut";
      if (has(blob, "vacate", "two day", "2 day", "evict", "खाली")) {
        alternatives = [{ situation_type: "informal_eviction", why: "The same facts also include an extra-legal vacate demand." }];
        situation = "informal_eviction";
      }
    } else {
      situation = "informal_eviction";
    }
    level = "state";
  } else if (domain === "consumer") {
    situation = "defect_refund_refused";
    level = "unknown";
  } else if (domain === "welfare_records") {
    if (situation === "explicit_information_request") needs_kind = false;
    else if (!slots.pending_kind && (situation == null || situation === "pending_application")) {
      situation = "pending_application";
      needs_kind = true;
      alternatives = [
        { situation_type: "pending_application", why: "Applied, no decision / no update." },
        { situation_type: "disbursement_failed", why: "Told approved/selected but money not credited." },
        { situation_type: "verification_gap", why: "Office says documents or KYC are incomplete." },
        { situation_type: "eligibility_question", why: "Asking whether they qualify — we will not invent that." },
      ];
      evidence.push("vague welfare delay — discriminating question required");
    }
    if (!situation) {
      situation = "pending_application";
      needs_kind = true;
    }
    if (benefit === "scholarship" && level === "unknown" && !slots.scheme_level) {
      needs_level = true;
      evidence.push("scholarship scheme-level unknown — NSP vs State changes the PIO portal");
    }
    if (benefit === "ration") {
      level = "state";
      needs_level = false;
    }
    if (benefit === "pf") {
      level = "union";
      needs_level = false;
    }
  } else if (domain === "police_accountability") {
    situation = "police_assault";
    level = "union";
    evidence.push("alleged police use of force — human-rights complaint, not RTI");
  } else if (domain === "workplace") {
    situation = "unpaid_wages";
    level = "state";
    evidence.push("employment dispute — not consumer, not unsourced IDA sections");
  } else {
    situation = "unsupported";
  }

  const pathway = TABLE.pathways[situation || ""] || TABLE.pathways.pending_application;
  if (domain === "unsupported" || situation === "unsupported") {
    return {
      domain: "unsupported",
      situation_type: "unsupported",
      primary_action: "none",
      government_level: "unknown",
      benefit,
      why: "No civic pathway in the v1 table matches this. Legalo will not invent one.",
      not_this: "Not RTI, not consumer, not tenancy.",
      alternatives: [],
      evidence,
      confidence: 0.9,
      needs_pending_kind: false,
      needs_scheme_level: false,
      source: "rules",
    };
  }

  let department_id: string | null = null;
  if (domain === "police_accountability") department_id = "nhrc";
  else if (domain === "workplace") department_id = "labour-commissioner";
  else if (benefit && TABLE.benefits[benefit]) {
    const b = TABLE.benefits[benefit];
    department_id = (level === "union" ? b.department_union : b.department_state) || null;
  }

  let confidence = !needs_kind && !needs_level ? 0.82 : 0.55;
  if (situation === "explicit_information_request") confidence = 0.9;
  if (situation === "police_assault") confidence = 0.88;

  let why = pathway.why_en || "";
  if (benefit === "scholarship" && level === "unknown") {
    why += " Scholarship may be a State scheme or a Central/NSP scheme — that choice decides the PIO and whether rtionline.gov.in is even lawful to use.";
  }
  if (benefit === "ration") why += " Ration / PDS is a State Food & Civil Supplies record. rtionline.gov.in will bounce it.";
  if (benefit === "pf") why += " Provident-fund records are held by EPFO, a Central public authority — not a shop forum, and not a State PDS RTI.";

  return {
    domain,
    situation_type: situation || "pending_application",
    primary_action: pathway.primary_action || "rti",
    secondary_action: pathway.secondary_action,
    government_level: level,
    benefit,
    department_id,
    why,
    not_this: pathway.not_en || "",
    alternatives,
    evidence,
    confidence,
    needs_pending_kind: needs_kind,
    needs_scheme_level: needs_level,
    source: "rules",
  };
}

export function intentOf(interp: Interpretation): Intent {
  if (interp.domain === "consumer") return "consumer";
  if (interp.domain === "tenancy") return "tenant";
  if (interp.domain === "police_accountability") return "nhrc";
  if (interp.domain === "workplace") return "labour";
  if (interp.domain === "unsupported" || interp.primary_action === "none") return "unsupported";
  return "rti";
}

export function departmentLabel(interp: Interpretation): string | null {
  const rows = (directory as { authorities: { id: string; label_en: string }[] }).authorities;
  return rows.find((r) => r.id === interp.department_id)?.label_en || null;
}

export function discriminatingQuestion(interp: Interpretation, slots: Record<string, string>) {
  if (interp.needs_pending_kind && !slots.pending_kind) {
    return {
      key: "pending_kind",
      prompt_en:
        "A pending scholarship/benefit can mean different civic problems. Which is closest?\n1) I applied and have heard nothing (file still pending).\n2) I was told I was selected/approved but the money has not come.\n3) They say documents or KYC/verification are still pending.\n4) I mainly want to know if I am eligible.",
      prompt_hi:
        "लंबित छात्रवृत्ति/लाभ कई तरह की समस्या हो सकती है। कौन-सा सबसे नज़दीक है?\n1) आवेदन किया, कोई खबर नहीं (फ़ाइल लंबित)।\n2) चयन/मंज़ूरी हुई बताई गई, पैसे नहीं आए।\n3) दस्तावेज़ या KYC बाकी बता रहे हैं।\n4) मैं मुख्यतः पात्रता पूछ रहा/रही हूँ।",
      required: true,
      choices: [...PENDING_KINDS],
    };
  }
  if (interp.needs_scheme_level && !slots.scheme_level) {
    return {
      key: "scheme_level",
      prompt_en:
        "Is this a Central / National Scholarship Portal (NSP) scheme, or a State government scholarship? This decides the public authority and whether you may use rtionline.gov.in (Central only).",
      prompt_hi:
        "क्या यह केंद्रीय / National Scholarship Portal (NSP) योजना है, या राज्य सरकार की छात्रवृत्ति? इसी से लोक प्राधिकरण और rtionline.gov.in का उपयोग तय होता है (केवल केंद्र)।",
      required: true,
      choices: ["union", "state", "unknown"],
    };
  }
  return null;
}

export function applyDiscriminator(slots: Record<string, string>, key: string | null, answer: string) {
  const updated = { ...slots };
  const raw = (answer || "").trim();
  const low = raw.toLowerCase();
  if (key === "pending_kind" || (!key && ["1", "2", "3", "4", "eligible", "approved", "kyc"].some((x) => low.includes(x)))) {
    if ((PENDING_KINDS as readonly string[]).includes(raw)) updated.pending_kind = raw;
    else if (low.startsWith("1") || has(low, "heard nothing", "still pending", "no update", "applied")) updated.pending_kind = "pending_application";
    else if (low.startsWith("2") || has(low, "approved", "selected", "money", "disburs")) updated.pending_kind = "disbursement_failed";
    else if (low.startsWith("3") || has(low, "kyc", "document", "verification")) updated.pending_kind = "verification_gap";
    else if (low.startsWith("4") || has(low, "eligible", "qualify", "eligibility", "पात्र")) updated.pending_kind = "eligibility_question";
    else if (key !== "pending_kind") updated.pending_kind = raw;
    if (key === "pending_kind") return updated;
  }
  if (key === "scheme_level") {
    if (has(low, "nsp", "national", "central", "union")) updated.scheme_level = "union";
    else if (has(low, "state")) updated.scheme_level = "state";
    else updated.scheme_level = raw || "unknown";
  } else if (key && raw) updated[key] = raw;
  return updated;
}

export function informationSought(interp: Interpretation) {
  const benefit = interp.benefit || "benefit / application";
  if (interp.situation_type === "disbursement_failed") {
    return `For my ${benefit}: (a) certified copies of the sanction/selection order; (b) payment file notings and PFMS/DBT / treasury status with dates; (c) if payment was returned or rejected, the memo and reason; (d) name and designation of the officer with whom the payment file is pending.`;
  }
  if (interp.situation_type === "verification_gap") {
    return `For my ${benefit} application: (a) the written list of documents/KYC still pending, with dates of each demand; (b) copy of any deficiency memo; (c) file notings on verification; (d) officer presently holding the file.`;
  }
  if (interp.situation_type === "eligibility_question") {
    return `Certified copies of the eligibility criteria, governing circulars and the evaluation/scrutiny note on my ${benefit} application, including marks or grounds if it was rejected or kept pending on eligibility.`;
  }
  return `Current status of my ${benefit} application; certified copies of file notings, orders and reasons for delay; name and designation of officers with whom the file is pending; and the date-wise movement of the file.`;
}
