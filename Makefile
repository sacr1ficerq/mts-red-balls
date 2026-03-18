.PHONY: run run-local build down clean install test test-openrouter test-model-access test-all

run:
	docker compose up --build

run-local:
	cd backend && make install
	cd backend && make run

build:
	docker compose build

down:
	docker compose down

clean:
	docker compose down -v

install:
	cd backend && make install

test:
	cd backend && python3 -m pytest tests/ -v

test-openrouter:
	cd backend && python3 -m pytest tests/test_openrouter.py -v -s

test-model-access:
	cd backend && python3 -m pytest tests/test_openrouter.py::TestModelAccess -v -s

test-all:
	cd backend && python3 -m pytest tests/ -v --tb=short
