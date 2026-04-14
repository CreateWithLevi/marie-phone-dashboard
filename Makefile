.PHONY: setup seed run dev pipeline evaluate clean

# Quick start: make setup && make seed && make run
setup:
	@echo "=== Setting up backend ==="
	uv sync
	.venv/bin/python manage.py migrate
	@echo "=== Setting up frontend ==="
	cd frontend && npm install
	cd frontend && npm run build
	@echo "=== Done! Run 'make seed' then 'make run' ==="

seed:
	@echo "=== Loading seed data ==="
	.venv/bin/python manage.py seed_data

run:
	@echo "=== Starting server at http://localhost:8000 ==="
	.venv/bin/python manage.py runserver 8000

dev:
	@echo "=== Starting Django (8000) + Vite (5173) ==="
	@.venv/bin/python manage.py runserver 8000 & cd frontend && npm run dev -- --port 5173

pipeline:
	@echo "=== Running full pipeline (requires Whisper + LLM) ==="
	.venv/bin/python -m pipeline.run_pipeline

pipeline-resume:
	.venv/bin/python -m pipeline.run_pipeline --resume

evaluate:
	@echo "=== Extraction Accuracy vs Ground Truth ==="
	@curl -s http://localhost:8000/api/evaluation/ | python3 -m json.tool

clean:
	rm -f db.sqlite3
	rm -rf frontend/dist
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
