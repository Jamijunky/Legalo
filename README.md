# Legalo

**The product is situation interpretation, not a feature pile.**

Multilingual UI, RAG, PDFs and jurisdiction notes are table stakes. A judge will not care that Legalo has them unless they work together on a vague sentence:

> “My scholarship has been pending for four months.”

A weak system translates that and retrieves scholarship FAQs. Legalo has to decide what *kind* of civic problem it is (silent file vs missing payment vs KYC gap vs eligibility question), what would change the route (NSP vs State), whether this is an information request or a grievance, and only then draft.

v1 is therefore **not** “AI for every civic problem in 22 languages.” It is a router that is unusually careful in **three domains** (welfare/records → RTI, consumer, tenancy), with pathways in [`data/routing/pathways.json`](data/routing/pathways.json) so a fourth domain is a new row, not a new chatbot.

## What the router must get right

1. **Situation type** — pending application, failed disbursement, verification gap, eligibility question, shop refund, essential-supply cut, informal eviction.
2. **Discriminating questions** — asked *before* name/address when the one-liner is ambiguous.
3. **Action** — RTI vs consumer complaint vs tenant representation. A shop refund must not become an RTI to a ministry. A silent scholarship file should not get a fake eligibility answer.
4. **Authority level** — State PDS / State scholarship vs Central/NSP, because rtionline.gov.in will bounce State filings.

## Demo journeys (narrow on purpose)

| Probe | Input | What must happen |
|---|---|---|
| Vague welfare | “My scholarship has been pending for four months.” | Ask what “pending” means, then NSP vs State, then RTI for the *right* file |
| Explicit records | Ration card in Prayagraj, wants notings | Skip the discriminator; State Food & Civil Supplies RTI |
| Wrong forum trap | Shop refused refund | Consumer Commission / e-Jagriti — **not** RTI |
| Mixed tenancy | Electricity cut + 2-day vacate notice | Model Tenancy ss.20–21; state law may differ; **not** a consumer forum |

This is **not legal advice**. Legalo does not file on government portals.

## Freshness / provenance

Every corpus item has `published_on`, `effective_on`, `retrieved_on`, publisher, official URL and `doc_type`. Ingest **fails closed** if those fields are missing. Blogs and commentary are not in the retrieval index.

Procedural pages (portals, fees, forms, older circulars) show a **verify on the official portal — this source is dated …** banner. Acts of Parliament may be old; how-to pages may not silently be treated as current.

Live table in the app: [/sources](http://localhost:3000/sources)

| Title | Publisher | Published | Effective | Retrieved | Official URL |
|---|---|---|---|---|---|
| Right to Information Act, 2005 | DoPT / India Code | 2005-06-15 | 2005-10-12 | 2026-08-18 | [indiacode](https://www.indiacode.nic.in/handle/123456789/2065) |
| RTI Rules, 2012 (G.S.R. 603(E)) | DoPT | 2012-07-31 | 2012-07-31 | 2026-08-18 | [dopt.gov.in](https://dopt.gov.in/acts/rti-rules-2012-0) |
| DoPT RTI FAQ (as on Jan 2012) | DoPT | 2012-01-01 | 2012-01-01 | 2026-08-18 | [PDF](https://dopt.gov.in/sites/default/files/FAQ_RTI_2012%20(1).pdf) |
| RTI Online portal snapshot | DoPT / NIC | 2026-08-18 | 2026-08-18 | 2026-08-18 | [rtionline.gov.in](https://rtionline.gov.in/) |
| Consumer Protection Act, 2019 | Dept of Consumer Affairs | 2019-08-09 | 2020-07-20 | 2026-08-18 | [indiacode](https://www.indiacode.nic.in/handle/123456789/17942?locale=en) |
| Jurisdiction Rules, 2021 (G.S.R. 912(E)) | Dept of Consumer Affairs / PIB | 2021-12-30 | 2021-12-30 | 2026-08-18 | [PIB PRID 1786342](https://www.pib.gov.in/PressReleasePage.aspx?PRID=1786342) |
| e-Jagriti platform | Dept of Consumer Affairs | 2025-06-03 | 2025-06-03 | 2026-08-18 | [e-jagriti.gov.in](https://e-jagriti.gov.in/) |
| Model Tenancy Act, 2021 | MoHUA | 2021-06-02 | 2021-06-02 | 2026-08-18 | [MoHUA PDF](https://mohua.gov.in/upload/uploadfiles/files/Model-Tenancy-Act-English-02_06_2021.pdf) |

**Deliberate correction vs older tutorials:** e-Daakhil (`edaakhil.nic.in`) returned HTTP 500 on 2026-08-18. The ministry lists **e-Jagriti** as the nodal filing platform. The original CPA 2019 pecuniary figures (₹1 crore / ₹10 crore) were replaced by the 30 December 2021 Rules (₹50 lakh / ₹2 crore). Legalo cites the later rules and tells you to re-check the live portal.

## Architecture

```
Citizen sentence
    → situation interpreter (data/routing/pathways.json)
    → discriminating questions
    → dated official RAG (only after the route is chosen)
    → template draft for that pathway
```

Optional `pgvector` Postgres is in Compose under the `pgvector` profile for a later embeddings overlay. The prototype retrieval path is in-process BM25 so `uvicorn` works with zero infrastructure. New Acts/states are new corpus packs, not new product code.

## Run locally

Needs Python 3.12+ and Node 22+.

```bash
cp .env.example .env
# optional: GEMINI_API_KEY=...   (Indic generation + stronger classification)

python3 -m venv .venv
source .venv/bin/activate
pip install -r apps/api/requirements.txt
cd apps/api && PYTHONPATH=. pytest -q && uvicorn app.main:app --reload --port 8000
```

In another terminal:

```bash
cd apps/web
npm install
npm run dev
```

Open http://localhost:3000

### Docker

```bash
docker compose up --build
```

API: http://localhost:8000/health  
Web: http://localhost:3000

Postgres + pgvector (optional): `docker compose --profile pgvector up db`

## API

- `GET /health`
- `GET /v1/provenance`
- `POST /v1/cases` `{ text, language, ui_locale }`
- `POST /v1/cases/{id}/message`
- `POST /v1/cases/{id}/upload` multipart file
- `PATCH /v1/cases/{id}/draft` `{ fields }`
- `GET /v1/cases/{id}/pdf`
- `POST /v1/eval` gold cases

Languages: UI chrome is English + Hindi. Generated explanations can target any scheduled Indian language when `GEMINI_API_KEY` is set; without a key, English template text is used (still fully cited).

## Tests

```bash
cd apps/api && PYTHONPATH=. pytest -q
```

Gold eval checks: intent routing, required Act citations, e-Jagriti mention, tenant “state law may differ”, and refusal when the corpus has no source.

## What this prototype will not do

- File on rtionline.gov.in or e-jagriti.gov.in
- Invent PIO names
- Answer from blogs
- Cover workplace disputes in v1 (state-law variance)

## Demo video

See [docs/DEMO.md](docs/DEMO.md) (script ≤ 10 minutes).

## Licence / sources

Government of India Acts, Rules, PIB releases and portal copy are cited with URLs. Keep original PDFs in `data/corpus/official/` when the host allows download. Markdown/JSONL extracts are derived; sidecars are the source of truth for dates.
