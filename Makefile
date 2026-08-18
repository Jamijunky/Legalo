.PHONY: api web test ingest

api:
	cd apps/api && PYTHONPATH=. $(CURDIR)/.venv/bin/uvicorn app.main:app --reload --port 8000

web:
	cd apps/web && npm run dev

test:
	cd apps/api && PYTHONPATH=. $(CURDIR)/.venv/bin/pytest -q

ingest:
	cd apps/api && PYTHONPATH=. $(CURDIR)/.venv/bin/python -m app.ingest
