.PHONY: run-local install hello-world-backend test test-openrouter test-model-access test-all test-titanic

run-local:
	cd backend && make install
	cd backend && make run

install:
	cd backend && make install

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

test-titanic:
	@BACKEND_PID=""; \
	(cd backend && PYTHONUNBUFFERED=1 LOG_LEVEL=debug python3 -m uvicorn server:app --port 8000 --log-level debug) & BACKEND_PID=$$!; \
	TITANIC_DEBUG=1 python3 tests/test_titanic_local.py; TEST_STATUS=$$?; \
	if [ -n "$$BACKEND_PID" ]; then kill $$BACKEND_PID 2>/dev/null || true; fi; \
	exit $$TEST_STATUS
