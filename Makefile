.PHONY: run debug run-local build down clean install hello-world hello-world-backend test test-openrouter test-model-access test-all

run:
	docker compose up --build backend

debug:
	LOG_LEVEL=debug $(MAKE) run

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

hello-world:
	LOG_LEVEL=debug docker compose up -d --build backend
	@LOG_FOLLOW_PID=""; \
	docker compose logs -f backend & LOG_FOLLOW_PID=$$!; \
	python3 tests/test_hello_world_docker.py; TEST_STATUS=$$?; \
	if [ -n "$$LOG_FOLLOW_PID" ]; then kill $$LOG_FOLLOW_PID 2>/dev/null || true; fi; \
	exit $$TEST_STATUS

hello-world-backend:
	$(MAKE) -C backend hello-world

test:
	cd backend && python3 -m pytest tests/ -v

test-openrouter:
	cd backend && python3 -m pytest tests/test_openrouter.py -v -s

test-model-access:
	cd backend && python3 -m pytest tests/test_openrouter.py::TestModelAccess -v -s

test-all:
	cd backend && python3 -m pytest tests/ -v --tb=short
