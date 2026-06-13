.PHONY: install backend frontend test

install:
	python3 -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e ".[dev]"

backend:
	. .venv/bin/activate && uvicorn backend.main:app --reload --port 8000

frontend:
	. .venv/bin/activate && BACKEND_URL=http://localhost:8000 streamlit run frontend/app.py

test:
	. .venv/bin/activate && pytest -q
