.PHONY: install lint test smoke ui-dev api-dev dev-up dev-down pre-commit-install format

install:
	pip install -r requirements.txt
	cd ui && npm install

lint:
	ruff check .
	cd ui && npm run lint

test:
	pytest

smoke:
	cd ui && npm run test:smoke

format:
	cd ui && npm run format

ui-dev:
	cd ui && npm run dev -- --host --port 5173

api-dev:
	uvicorn server.main:app --host 0.0.0.0 --port 8888 --reload

dev-up:
	docker compose -f docker-compose.dev.yml up --build

dev-down:
	docker compose -f docker-compose.dev.yml down

pre-commit-install:
	pre-commit install
