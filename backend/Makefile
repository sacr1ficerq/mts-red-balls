.PHONY: install run clean

install:
	pip install -r requirements.txt

run:
	uvicorn main:app --reload --port 8000

clean:
	rm -rf __pycache__ .pytest_cache
