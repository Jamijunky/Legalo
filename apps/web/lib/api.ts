import { localCreate, localMessage, localPatch, localProvenance, localUpload } from "@/lib/civic/engine";

export const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export type InterpretationView = {
  domain: string;
  situation_type: string;
  primary_action: string;
  secondary_action?: string | null;
  government_level: string;
  benefit?: string | null;
  department_id?: string | null;
  department_label?: string | null;
  why: string;
  not_this: string;
  alternatives: { situation_type: string; why: string }[];
  evidence: string[];
  confidence: number;
  source: string;
};

export type SlotQuestion = {
  key: string;
  prompt_en: string;
  prompt_hi: string;
  required: boolean;
  choices?: string[];
};

export type SourceRef = {
  chunk_id: string;
  doc_id: string;
  title: string;
  publisher: string;
  section: string;
  source_url: string;
  published_on: string;
  effective_on: string;
  retrieved_on: string;
  doc_type: string;
  stale_procedural: boolean;
  state_law_may_differ: boolean;
  notes: string;
};

export type PathStep = {
  title: string;
  detail: string;
  deadline?: string | null;
  url?: string | null;
  verify?: string | null;
};

export type DraftBody = {
  template_id: string;
  title: string;
  language: string;
  fields: Record<string, string>;
  html: string;
  plain: string;
};

export type CaseResponse = {
  case_id: string;
  step: string;
  intent: "rti" | "consumer" | "tenant" | "nhrc" | "labour" | "unsupported" | null;
  language: string;
  ui_locale: string;
  restatement?: string | null;
  interpretation?: InterpretationView | null;
  question?: SlotQuestion | null;
  slots: Record<string, string>;
  explanation?: string | null;
  sources: SourceRef[];
  path: PathStep[];
  draft?: DraftBody | null;
  banners: string[];
  ready_for_pdf: boolean;
  routed_on_device?: boolean;
  error?: string | null;
};

export type ProvenanceRow = {
  id: string;
  title: string;
  publisher: string;
  doc_type: string;
  published_on: string;
  effective_on: string;
  retrieved_on: string;
  source_url: string;
  notes: string;
};

async function parse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const j = await res.json();
      detail = j.detail || JSON.stringify(j);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

function useRemoteApi() {
  if (typeof window === "undefined") return false;
  const host = window.location.hostname;
  if (host === "localhost" || host === "127.0.0.1") return true;
  const url = process.env.NEXT_PUBLIC_API_URL || "";
  return Boolean(url) && !/localhost|127\.0\.0\.1/.test(url);
}

async function tryApi<T>(run: (signal: AbortSignal) => Promise<T>, fallback: () => T | Promise<T>): Promise<T> {
  if (!useRemoteApi()) return fallback();
  try {
    const ctrl = new AbortController();
    const t = window.setTimeout(() => ctrl.abort(), 1200);
    const out = await run(ctrl.signal);
    window.clearTimeout(t);
    return out;
  } catch {
    return fallback();
  }
}

export async function createCase(text: string, language: string, uiLocale: string) {
  return tryApi(
    async (signal) =>
      parse<CaseResponse>(
        await fetch(`${API_URL}/v1/cases`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, language, ui_locale: uiLocale }),
          signal,
        })
      ),
    () => localCreate(text, language, uiLocale)
  );
}

export async function sendMessage(caseId: string, text: string, language: string) {
  return tryApi(
    async (signal) =>
      parse<CaseResponse>(
        await fetch(`${API_URL}/v1/cases/${caseId}/message`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text, language }),
          signal,
        })
      ),
    () => localMessage(caseId, text, language)
  );
}

export async function uploadNotice(caseId: string, file: File) {
  return tryApi(
    async (signal) => {
      const fd = new FormData();
      fd.append("file", file);
      return parse<CaseResponse>(await fetch(`${API_URL}/v1/cases/${caseId}/upload`, { method: "POST", body: fd, signal }));
    },
    async () => {
      const notice = file.type.startsWith("text/") || file.name.endsWith(".txt") ? await file.text() : `[Could not read ${file.name} in the browser. Paste the notice text.]`;
      return localUpload(caseId, notice);
    }
  );
}

export async function patchDraft(caseId: string, fields: Record<string, string>) {
  return tryApi(
    async (signal) =>
      parse<CaseResponse>(
        await fetch(`${API_URL}/v1/cases/${caseId}/draft`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ fields }),
          signal,
        })
      ),
    () => localPatch(caseId, fields)
  );
}

export function pdfUrl(caseId: string) {
  return `${API_URL}/v1/cases/${caseId}/pdf`;
}

export function downloadDraft(draft: DraftBody) {
  const blob = new Blob([draft.plain], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `legalo-${draft.template_id}.txt`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function fetchProvenance() {
  return tryApi(
    async (signal) => parse<ProvenanceRow[]>(await fetch(`${API_URL}/v1/provenance`, { signal })),
    () => localProvenance()
  );
}
