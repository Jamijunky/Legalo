"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  CaseResponse,
  createCase,
  downloadDraft,
  patchDraft,
  pdfUrl,
  sendMessage,
  uploadNotice,
} from "@/lib/api";
import { GENERATION_LANGUAGES, copy, type UiLocale } from "@/lib/i18n";

const DEMOS = {
  scholarship: "My scholarship has been pending for four months.",
  eligibility: "Am I eligible for a scholarship?",
  police: "a police officer slapped me.",
  rti: "My ration card application has been pending for four months in Prayagraj. I want the current status and certified copies of file notings and reasons for delay.",
  rtiHi:
    "प्रयागराज में मेरा राशन कार्ड का आवेदन चार महीने से लंबित है। मुझे वर्तमान स्थिति और फ़ाइल नोटिंग की प्रमाणित प्रतियाँ चाहिए।",
  consumer:
    "A shop in Lucknow refused refund for a defective smartphone I bought last month for 18000 rupees. They said no returns after 7 days.",
  workplace: "My employer has not paid my salary for three months.",
  notice:
    "Please read the uploaded notice. My landlord cut the electricity yesterday and says I must vacate in two days. The house is in Prayagraj, Uttar Pradesh.",
};

const STEPS = ["understand", "rights", "path", "draft"] as const;
type Pane = (typeof STEPS)[number];

const HIDDEN_FIELDS = new Set(["retrieved_on", "date", "delivery", "legal_paragraph", "prior_contact"]);

const FIELD_LABEL: Record<string, string> = {
  complainant_name: "Your name",
  complainant_contact: "Phone / email / address",
  complainant_address: "Your address",
  applicant_name: "Your name",
  applicant_address: "Postal address",
  applicant_contact: "Phone or email",
  state: "State / UT",
  facts: "What happened, in your words",
  place_time: "Place and date / time",
  officer_detail: "Officer / station if known",
  relief: "What you want done",
  public_authority: "Public authority / department",
  information_sought: "Information / copies sought",
  opposite_party: "Shop / seller",
  goods_service: "Goods or service",
  amount: "Amount paid (₹)",
  defect: "What went wrong",
  tenant_name: "Your name",
  landlord_name: "Landlord",
  premises: "Address of the house",
  issue: "What happened",
  employer_name: "Employer",
  worker_name: "Your name",
};

const CHOICE_LABEL: Record<string, { en: string; hi: string }> = {
  pending_application: { en: "I applied. Silence. No decision.", hi: "आवेदन किया, कोई खबर नहीं।" },
  disbursement_failed: { en: "Told selected / approved. Money never came.", hi: "चयन/मंज़ूरी हुई, पैसे नहीं आए।" },
  verification_gap: { en: "They say documents or KYC are still pending.", hi: "दस्तावेज़ या KYC बाकी बता रहे हैं।" },
  eligibility_question: { en: "I mainly want to know if I qualify.", hi: "मुख्यतः पात्रता पूछ रहा/रही हूँ।" },
  union: { en: "Central / NSP scheme", hi: "केंद्रीय / NSP योजना" },
  state: { en: "State government scheme", hi: "राज्य सरकार की योजना" },
  unknown: { en: "I am not sure", hi: "पता नहीं" },
};

function paperHtml(html: string) {
  const body = html.match(/<body[^>]*>([\s\S]*)<\/body>/i)?.[1] || html;
  return body.replace(/<style[\s\S]*?<\/style>/gi, "");
}

function pretty(s: string) {
  return s.replaceAll("_", " ");
}

function splitRights(text: string) {
  return text
    .split(/(?<=\.)\s+(?=[A-Z“"I])|(?<=।)\s+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

function notChips(text: string) {
  return text
    .split(/\.\s+(?=[A-Z“"N])|।\s+/)
    .map((s) => s.replace(/\.+$/, "").trim())
    .filter((s) => s.length > 6);
}

export default function HomePage() {
  const [ui, setUi] = useState<UiLocale>("en");
  const [language, setLanguage] = useState("en");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [cas, setCas] = useState<CaseResponse | null>(null);
  const [answer, setAnswer] = useState("");
  const [pane, setPane] = useState<Pane>("understand");
  const [form, setForm] = useState<Record<string, string>>({});

  const t = copy[ui];

  useEffect(() => {
    if (!cas) return;
    setForm(cas.draft?.fields || {});
    setPane(cas.question ? "understand" : "rights");
  }, [cas?.case_id]);

  const unlocked = useMemo(() => {
    if (!cas) return 0;
    if (cas.question) return 0;
    if (cas.draft) return 3;
    if (cas.path.length) return 2;
    if (cas.explanation) return 1;
    return 0;
  }, [cas]);

  async function start(seed?: string, langOverride?: string) {
    setErr(null);
    setBusy(true);
    try {
      const body = seed ?? text;
      const lang = langOverride || language;
      if (langOverride) setLanguage(langOverride);
      if (!body.trim() && !file) {
        setErr("Write a few sentences, or upload a notice.");
        return;
      }
      const created = await createCase(body || "Please read the attached notice.", lang, ui);
      let next = created;
      if (file) next = await uploadNotice(created.case_id, file);
      setCas(next);
      setForm(next.draft?.fields || {});
      setPane(next.question ? "understand" : "rights");
      setAnswer("");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not start");
    } finally {
      setBusy(false);
    }
  }

  async function reply(value?: string) {
    const msg = (value ?? answer).trim();
    if (!cas || !msg) return;
    setBusy(true);
    setErr(null);
    try {
      const next = await sendMessage(cas.case_id, msg, language);
      setCas(next);
      setForm(next.draft?.fields || {});
      setAnswer("");
      setPane(next.question ? "understand" : "rights");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not continue");
    } finally {
      setBusy(false);
    }
  }

  async function stampDraft() {
    if (!cas) return;
    setBusy(true);
    try {
      const next = await patchDraft(cas.case_id, form);
      setCas(next);
      setForm(next.draft?.fields || form);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not update draft");
    } finally {
      setBusy(false);
    }
  }

  const interp = cas?.interpretation;
  const citizenFields = Object.keys(form).filter((k) => !HIDDEN_FIELDS.has(k));

  return (
    <div className="wrap">
      <header className="topbar">
        <div className="brand">
          <Link href="/">{t.brand}</Link>
          <span className="mark">civic docket</span>
        </div>
        <div className="row">
          <label>
            {t.ui}{" "}
            <select className="lang" value={ui} onChange={(e) => setUi(e.target.value as UiLocale)}>
              <option value="en">English</option>
              <option value="hi">हिन्दी</option>
            </select>
          </label>
          <label>
            {t.language}{" "}
            <select className="lang" value={language} onChange={(e) => setLanguage(e.target.value)}>
              {GENERATION_LANGUAGES.map((l) => (
                <option key={l.code} value={l.code}>
                  {l.label}
                </option>
              ))}
            </select>
          </label>
          <Link href="/sources">{t.corpus}</Link>
        </div>
      </header>

      {!cas && (
        <>
          <section className="hero">
            <p className="kicker">{t.kicker}</p>
            <h1 className="serif">{t.tagline}</h1>
            <p>{t.blurb}</p>
            <p className="note">{t.freshness}</p>
          </section>
          <section className="card intake">
            <h2>{t.start}</h2>
            <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={t.placeholder} />
            <p className="note">{t.orUpload}</p>
            <input type="file" accept=".pdf,.txt,image/*" onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            <div className="row" style={{ marginTop: 12 }}>
              <button className="primary" disabled={busy} onClick={() => start()}>
                {t.routeIt}
              </button>
            </div>
            {err && <p className="err">{err}</p>}
            <h3 style={{ marginTop: 22 }}>{t.demos}</h3>
            <div className="demos">
              {(
                [
                  ["scholarship", t.demoRti, t.demoRtiHint],
                  ["eligibility", t.demoElig, t.demoEligHint],
                  ["police", t.demoPolice, t.demoPoliceHint],
                  ["rti", t.demoRation, t.demoRationHint],
                  ["consumer", t.demoConsumer, t.demoConsumerHint],
                  ["workplace", t.demoWork, t.demoWorkHint],
                ] as const
              ).map(([key, title, hint]) => (
                <button key={key} className="demo" type="button" disabled={busy} onClick={() => start(DEMOS[key])}>
                  <strong>{title}</strong>
                  <span className="note">{hint}</span>
                </button>
              ))}
              <button className="demo" type="button" disabled={busy} onClick={() => start(DEMOS.rtiHi, "hi")}>
                <strong>{t.demoHi}</strong>
                <span className="note">{t.demoHiHint}</span>
              </button>
              <button
                className="demo"
                type="button"
                disabled={busy}
                onClick={async () => {
                  const blob = new Blob(
                    [
                      `NOTICE TO VACATE\nDate: 16 August 2026\nTo Ramesh Kumar, Civil Lines, Prayagraj\nFrom Suresh Sharma, Landlord\nVacate within two days. Electricity disconnected today.\n`,
                    ],
                    { type: "text/plain" }
                  );
                  setFile(new File([blob], "eviction_notice.txt", { type: "text/plain" }));
                  setText(DEMOS.notice);
                  setErr(null);
                  setBusy(true);
                  try {
                    const created = await createCase(DEMOS.notice, language, ui);
                    const next = await uploadNotice(
                      created.case_id,
                      new File([blob], "eviction_notice.txt", { type: "text/plain" })
                    );
                    setCas(next);
                    setForm(next.draft?.fields || {});
                    setPane(next.question ? "understand" : "rights");
                  } catch (e) {
                    setErr(e instanceof Error ? e.message : "Demo failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <strong>{t.demoNotice}</strong>
                <span className="note">{t.demoNoticeHint}</span>
              </button>
            </div>
          </section>
        </>
      )}

      {cas && (
        <div className="docket">
          <div className="docket-meta">
            <span>File {cas.case_id}</span>
            {cas.routed_on_device && <span>{t.onDevice}</span>}
            <button
              className="ghost"
              onClick={() => {
                setCas(null);
                setFile(null);
              }}
            >
              ← {t.start}
            </button>
          </div>

          {interp && (
            <section className="stamp-card">
              <div className="stamp" aria-hidden>
                <span>{Math.round(interp.confidence * 100)}%</span>
                routed
              </div>
              <div>
                <p className="kicker">{t.interpret}</p>
                <h2 className="serif situation">{pretty(interp.situation_type)}</h2>
                <p className="route-line">
                  {pretty(interp.primary_action)}
                  {interp.government_level !== "unknown" ? ` · ${interp.government_level}` : ""}
                  {interp.department_label ? ` · ${interp.department_label}` : ""}
                </p>
                <p>{interp.why}</p>
                <div className="not-row">
                  {notChips(interp.not_this || "").map((bit) => (
                    <span key={bit} className="not-chip">
                      {bit}
                    </span>
                  ))}
                </div>
                {interp.alternatives.length > 0 && (
                  <p className="note alts">
                    {t.alts}: {interp.alternatives.map((a) => pretty(a.situation_type)).join(" · ")}
                  </p>
                )}
              </div>
            </section>
          )}

          <div className="steps" role="tablist">
            {STEPS.map((s, i) => (
              <button
                key={s}
                className={pane === s ? "step on" : "step"}
                disabled={i > unlocked}
                onClick={() => setPane(s)}
              >
                <span className="step-n">{i + 1}</span>
                {t[s]}
              </button>
            ))}
          </div>

          {err && <p className="err">{err}</p>}

          <section className="card pane">
            {pane === "understand" && (
              <>
                <p className="quote">{cas.restatement}</p>
                {cas.question ? (
                  <div className="ask">
                    <h3>{ui === "hi" ? cas.question.prompt_hi : cas.question.prompt_en}</h3>
                    {cas.question.choices && cas.question.choices.length > 0 && (
                      <div className="choice-grid">
                        {cas.question.choices.map((c) => (
                          <button key={c} className="choice" disabled={busy} onClick={() => void reply(c)}>
                            {CHOICE_LABEL[c]?.[ui] || c.replaceAll("_", " ")}
                          </button>
                        ))}
                      </div>
                    )}
                    <textarea value={answer} onChange={(e) => setAnswer(e.target.value)} placeholder={t.orOwnWords} />
                    <button className="primary" disabled={busy} onClick={() => void reply()}>
                      {t.answer}
                    </button>
                  </div>
                ) : (
                  <p className="note">{t.clickAhead}</p>
                )}
              </>
            )}

            {pane === "rights" && (
              <>
                <div className="rights">
                  {splitRights(cas.explanation || t.noRightsYet).map((p) => (
                    <p key={p.slice(0, 40)}>{p}</p>
                  ))}
                </div>
                {cas.sources.length > 0 && (
                  <div className="cites">
                    {cas.sources.map((s) => (
                      <a key={s.chunk_id} className="cite" href={s.source_url} target="_blank" rel="noreferrer">
                        <strong>
                          {s.title} {s.section}
                        </strong>
                        <span>
                          {s.published_on} · {t.retrieved} {s.retrieved_on}
                          {s.stale_procedural ? ` · ${t.verifyDated}` : ""}
                        </span>
                      </a>
                    ))}
                  </div>
                )}
              </>
            )}

            {pane === "path" && (
              <ol className="path">
                {cas.path.map((p) => (
                  <li key={p.title}>
                    <strong>{p.title}</strong>
                    <div>{p.detail}</div>
                    {p.deadline && <div className="deadline">{p.deadline}</div>}
                    {p.url && (
                      <a href={p.url} target="_blank" rel="noreferrer">
                        {p.url.replace(/^https?:\/\//, "")}
                      </a>
                    )}
                    {p.verify && <div className="note">{p.verify}</div>}
                  </li>
                ))}
              </ol>
            )}

            {pane === "draft" && cas.draft && (
              <div className="draft-grid">
                <div className="fill">
                  <h3>{t.completeDraft}</h3>
                  {citizenFields.map((k) => (
                    <label key={k} className="field">
                      {FIELD_LABEL[k] || k.replaceAll("_", " ")}
                      <textarea
                        className="mini"
                        value={form[k] || ""}
                        onChange={(e) => setForm({ ...form, [k]: e.target.value })}
                      />
                    </label>
                  ))}
                  <button className="primary" disabled={busy} onClick={() => void stampDraft()}>
                    {t.stampDraft}
                  </button>
                </div>
                <div>
                  <article className="paper" dangerouslySetInnerHTML={{ __html: paperHtml(cas.draft.html) }} />
                  <div className="row" style={{ marginTop: 12 }}>
                    <button className="primary" type="button" onClick={() => downloadDraft(cas.draft!)}>
                      {t.downloadDraft}
                    </button>
                    {!cas.routed_on_device && (
                      <a className="ghost" href={pdfUrl(cas.case_id)} style={{ textDecoration: "none" }}>
                        {t.pdf}
                      </a>
                    )}
                    <button className="ghost" type="button" onClick={() => window.print()}>
                      {t.print}
                    </button>
                  </div>
                </div>
              </div>
            )}

            {pane === "draft" && !cas.draft && <p className="note">{t.noDraftYet}</p>}
          </section>
        </div>
      )}

      <footer>
        <p>{t.notAdvice}</p>
        <p>
          <Link href="/sources">{t.corpus}</Link>
        </p>
      </footer>
    </div>
  );
}
