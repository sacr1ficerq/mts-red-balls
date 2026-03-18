.PHONY: install run clean test test-openrouter test-model-access test-all

install:
	python3 -m pip install -r requirements.txt

run:
	python3 -m uvicorn server:app --reload --port 8000

clean:
	rm -rf __pycache__ .pytest_cache

test:
	python3 -m pytest tests/ -v

test-openrouter:
	python3 -m pytest tests/test_openrouter.py -v -s

test-model-access:
	python3 -m pytest tests/test_openrouter.py::TestModelAccess -v -s

test-all:
	python3 -m pytest tests/ -v --tb=short
