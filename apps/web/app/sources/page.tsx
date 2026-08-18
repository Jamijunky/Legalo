"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ProvenanceRow, fetchProvenance } from "@/lib/api";

export default function SourcesPage() {
  const [rows, setRows] = useState<ProvenanceRow[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    fetchProvenance()
      .then(setRows)
      .catch((e) => setErr(e instanceof Error ? e.message : "failed"));
  }, []);

  return (
    <div className="wrap">
      <header className="topbar">
        <div className="brand">
          <Link href="/">Legalo</Link>
          <span className="mark">civic docket</span>
        </div>
        <Link href="/">← Home</Link>
      </header>
      <section className="hero">
        <h1>Corpus provenance</h1>
        <p>
          Every retrieval chunk is tied to an official sidecar with publication, effective and retrieved dates. Ingest
          fails if those fields are missing. Prefer a small dated corpus over an undated scrape.
        </p>
      </section>
      {err && <p className="err">{err}</p>}
      <div className="card scroll">
        <table className="ledger">
          <thead>
            <tr>
              {["Title", "Publisher", "Type", "Published", "Effective", "Retrieved", "URL"].map((h) => (
                <th key={h}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.title}</td>
                <td>{r.publisher}</td>
                <td>{r.doc_type}</td>
                <td>{r.published_on}</td>
                <td>{r.effective_on}</td>
                <td>{r.retrieved_on}</td>
                <td>
                  <a href={r.source_url} target="_blank" rel="noreferrer">
                    source
                  </a>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
