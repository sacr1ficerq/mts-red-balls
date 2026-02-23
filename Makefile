.PHONY: run build down clean

run:
	docker compose up --build

build:
	docker compose build

down:
	docker compose down

clean:
	docker compose down -v
