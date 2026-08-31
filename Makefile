.PHONY: setup check dev test lint clean

PY := backend/.venv/bin/python
PIP := backend/.venv/bin/pip

setup:
	python3.11 -m venv backend/.venv
	$(PIP) install --upgrade pip
	$(PIP) install -r backend/requirements.txt
	cp -n backend/.env.example backend/.env || true

check:
	cd backend && .venv/bin/python -m scripts.check_engines

dev:
	cd backend && .venv/bin/python -m uvicorn app.main:app --reload

test:
	cd backend && .venv/bin/python -m pytest -q

lint:
	cd backend && .venv/bin/ruff check .

clean:
	rm -rf backend/.venv backend/.pytest_cache backend/**/__pycache__
	rm -rf backend/storage/uploads/* backend/storage/stems/* backend/storage/outputs/*
