.PHONY: run run-local build down clean install test

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
