"""Fail-closed corpus ingest. Run from apps/api: python -m app.ingest"""

from .corpus import CorpusError, load_chunks, load_documents, provenance_rows


def main() -> None:
    docs = load_documents()
    chunks = load_chunks(docs)
    print(f"docs={len(docs)} chunks={len(chunks)}")
    for row in provenance_rows(docs):
        print(
            f"{row['id']}\t{row['published_on']}\t{row['effective_on']}\t{row['retrieved_on']}\t{row['source_url']}"
        )


if __name__ == "__main__":
    try:
        main()
    except CorpusError as exc:
        raise SystemExit(f"INGEST FAILED: {exc}") from exc
