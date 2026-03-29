.PHONY: install run debug clean test test-openrouter test-model-access test-all hello-world

install:
	python3 -m pip install --break-system-packages -r requirements.txt

run:
	python3 -m uvicorn server:app --reload --port 8000 --log-level $${LOG_LEVEL:-info}

debug:
	LOG_LEVEL=debug $(MAKE) run

clean:
	rm -rf __pycache__ .pytest_cache

test:
	python3 -m pytest --break-system-packages tests/ -v

test-openrouter:
	python3 -m pytest --break-system-packages tests/test_openrouter.py -v -s

test-model-access:
	python3 -m pytest --break-system-packages tests/test_openrouter.py::TestModelAccess -v -s

test-all:
	python3 -m pytest --break-system-packages tests/ -v --tb=short

hello-world:
	python3 -m pytest --break-system-packages tests/test_integration_real_llm.py::TestProductionFlow::test_hello_world_rust_production -v -s -m integration --log-cli-level=DEBUG
