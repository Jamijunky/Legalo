"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import {
  CaseResponse,
  createCase,
  patchDraft,
  pdfUrl,
  sendMessage,
  uploadNotice,
} from "@/lib/api";
import { GENERATION_LANGUAGES, copy, type UiLocale } from "@/lib/i18n";

const DEMOS = {
  scholarship: "My scholarship has been pending for four months.",
  rti: "My ration card application has been pending for four months in Prayagraj. I want the current status and certified copies of file notings and reasons for delay.",
  rtiHi:
    "प्रयागराज में मेरा राशन कार्ड का आवेदन चार महीने से लंबित है। मुझे वर्तमान स्थिति और फ़ाइल नोटिंग की प्रमाणित प्रतियाँ चाहिए।",
  consumer:
    "A shop in Lucknow refused refund for a defective smartphone I bought last month for 18000 rupees. They said no returns after 7 days.",
  notice:
    "Please read the uploaded notice. My landlord cut the electricity yesterday and says I must vacate in two days. The house is in Prayagraj, Uttar Pradesh.",
};

const STEPS = ["understand", "rights", "path", "draft"] as const;

export default function HomePage() {
  const [ui, setUi] = useState<UiLocale>("en");
  const [language, setLanguage] = useState("en");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [cas, setCas] = useState<CaseResponse | null>(null);
  const [answer, setAnswer] = useState("");
  const [editKey, setEditKey] = useState("");
  const [editVal, setEditVal] = useState("");

  const t = copy[ui];
  const stepIndex = useMemo(() => {
    if (!cas) return -1;
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
      setAnswer("");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not start");
    } finally {
      setBusy(false);
    }
  }

  async function reply() {
    if (!cas || !answer.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      setCas(await sendMessage(cas.case_id, answer, language));
      setAnswer("");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not continue");
    } finally {
      setBusy(false);
    }
  }

  async function saveField() {
    if (!cas || !editKey) return;
    setBusy(true);
    try {
      setCas(await patchDraft(cas.case_id, { [editKey]: editVal }));
      setEditKey("");
      setEditVal("");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Could not update draft");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="wrap">
      <header className="topbar">
        <div className="brand">
          <Link href="/">{t.brand}</Link>
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
            <h1 className="serif">{t.tagline}</h1>
            <p>{t.blurb}</p>
            <p className="note">{t.freshness}</p>
          </section>
          <section className="card">
            <h2>{t.start}</h2>
            <textarea value={text} onChange={(e) => setText(e.target.value)} placeholder={t.placeholder} />
            <p className="note">{t.orUpload}</p>
            <input
              type="file"
              accept=".pdf,.txt,image/*"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            />
            <div className="row" style={{ marginTop: 12 }}>
              <button className="primary" disabled={busy} onClick={() => start()}>
                {t.continue}
              </button>
            </div>
            {err && <p className="err">{err}</p>}
            <h3 style={{ marginTop: 22 }}>{t.demos}</h3>
            <div className="demos">
              <button className="demo" onClick={() => start(DEMOS.scholarship)}>
                <strong>{t.demoRti}</strong>
                <span className="note">Should ask what “pending” means — then NSP vs State</span>
              </button>
              <button className="demo" onClick={() => start(DEMOS.rti)}>
                <strong>{t.demoRation}</strong>
                <span className="note">Already an information request → RTI, State PDS</span>
              </button>
              <button className="demo" onClick={() => start(DEMOS.consumer)}>
                <strong>{t.demoConsumer}</strong>
                <span className="note">Must not become an RTI to a ministry</span>
              </button>
              <button
                className="demo"
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
                    const f = new File([blob], "eviction_notice.txt", { type: "text/plain" });
                    setCas(await uploadNotice(created.case_id, f));
                  } catch (e) {
                    setErr(e instanceof Error ? e.message : "Demo failed");
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <strong>{t.demoNotice}</strong>
                <span className="note">Model Tenancy Act 2021 · state law may differ</span>
              </button>
            </div>
          </section>
        </>
      )}

      {cas && (
        <>
          <div className="steps">
            {STEPS.map((s, i) => (
              <div key={s} className={i <= stepIndex ? "step on" : "step"}>
                {t[s]}
              </div>
            ))}
          </div>
          {cas.banners.map((b) => (
            <div key={b} className="banner">
              {b}
            </div>
          ))}
          {err && <p className="err">{err}</p>}

          <section className="card">
            {cas.interpretation && (
              <div className="interp">
                <h2>{t.interpret}</h2>
                <p>
                  <strong>{cas.interpretation.situation_type.replaceAll("_", " ")}</strong>
                  {" · "}
                  {t.action}: {cas.interpretation.primary_action.replaceAll("_", " ")}
                  {cas.interpretation.benefit ? ` · ${cas.interpretation.benefit}` : ""}
                  {cas.interpretation.government_level !== "unknown"
                    ? ` · ${cas.interpretation.government_level}`
                    : ""}
                  {cas.interpretation.department_label ? ` · ${cas.interpretation.department_label}` : ""}
                  <span className="note"> · confidence {Math.round(cas.interpretation.confidence * 100)}%</span>
                </p>
                <p>{cas.interpretation.why}</p>
                {cas.interpretation.not_this && (
                  <p className="note">
                    {t.notThis}: {cas.interpretation.not_this}
                  </p>
                )}
                {cas.interpretation.alternatives.length > 0 && (
                  <ul className="note">
                    {cas.interpretation.alternatives.map((a) => (
                      <li key={a.situation_type}>
                        If it were {a.situation_type.replaceAll("_", " ")}: {a.why}
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
            {cas.restatement && (
              <>
                <h2>{t.understand}</h2>
                <p>{cas.restatement}</p>
              </>
            )}

            {cas.question && (
              <div>
                <p>{ui === "hi" ? cas.question.prompt_hi : cas.question.prompt_en}</p>
                {cas.question.choices && cas.question.choices.length > 0 && (
                  <div className="demos" style={{ marginBottom: 12 }}>
                    {cas.question.choices.map((c) => (
                      <button
                        key={c}
                        className="demo"
                        disabled={busy}
                        onClick={() => {
                          setAnswer(c);
                          void (async () => {
                            if (!cas) return;
                            setBusy(true);
                            try {
                              setCas(await sendMessage(cas.case_id, c, language));
                              setAnswer("");
                            } finally {
                              setBusy(false);
                            }
                          })();
                        }}
                      >
                        <strong>{c.replaceAll("_", " ")}</strong>
                      </button>
                    ))}
                  </div>
                )}
                <textarea value={answer} onChange={(e) => setAnswer(e.target.value)} />
                <button className="primary" disabled={busy} onClick={reply}>
                  {t.answer}
                </button>
              </div>
            )}

            {cas.explanation && (
              <>
                <h2>{t.rights}</h2>
                <p>{cas.explanation}</p>
              </>
            )}

            {cas.path.length > 0 && (
              <>
                <h2>{t.path}</h2>
                <ol className="path">
                  {cas.path.map((p) => (
                    <li key={p.title}>
                      <strong>{p.title}</strong>
                      <div>{p.detail}</div>
                      {p.deadline && <div className="note">Deadline: {p.deadline}</div>}
                      {p.url && (
                        <div>
                          <a href={p.url} target="_blank" rel="noreferrer">
                            {p.url}
                          </a>
                        </div>
                      )}
                      {p.verify && <div className="note">{p.verify}</div>}
                    </li>
                  ))}
                </ol>
              </>
            )}
          </section>

          {cas.sources.length > 0 && (
            <section className="card" style={{ marginTop: 14 }}>
              <h2>{t.sources}</h2>
              {cas.sources.map((s) => (
                <div key={s.chunk_id} className="source">
                  <strong>
                    {s.title} · {t.section} {s.section}
                  </strong>
                  <div className="meta">
                    {s.publisher}
                    <br />
                    {t.published} {s.published_on} · {t.effective} {s.effective_on} · {t.retrieved} {s.retrieved_on}
                    {s.stale_procedural ? " · verify — procedural source is dated" : ""}
                  </div>
                  <a href={s.source_url} target="_blank" rel="noreferrer">
                    {t.openSource}
                  </a>
                </div>
              ))}
            </section>
          )}

          {cas.draft && (
            <section className="card" style={{ marginTop: 14 }}>
              <h2>{t.draft}</h2>
              <p className="note">
                {t.why}: template <code>{cas.draft.template_id}</code>
              </p>
              <pre className="draft">{cas.draft.plain}</pre>
              <div className="field">
                <label>{t.editField}</label>
                <select
                  value={editKey}
                  onChange={(e) => {
                    setEditKey(e.target.value);
                    setEditVal(cas.draft?.fields[e.target.value] || "");
                  }}
                >
                  <option value="">—</option>
                  {Object.keys(cas.draft.fields).map((k) => (
                    <option key={k} value={k}>
                      {k}
                    </option>
                  ))}
                </select>
                {editKey && (
                  <>
                    <input value={editVal} onChange={(e) => setEditVal(e.target.value)} />
                    <button className="ghost" onClick={saveField} disabled={busy}>
                      {t.continue}
                    </button>
                  </>
                )}
              </div>
              {cas.ready_for_pdf && (
                <a className="primary" href={pdfUrl(cas.case_id)} style={{ display: "inline-block", textDecoration: "none" }}>
                  {t.pdf}
                </a>
              )}
            </section>
          )}

          <p>
            <button
              className="ghost"
              onClick={() => {
                setCas(null);
                setFile(null);
              }}
            >
              ← {t.start}
            </button>
          </p>
        </>
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
