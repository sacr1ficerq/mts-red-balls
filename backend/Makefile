.PHONY: install run clean

install:
	python3 -m pip install -r requirements.txt

run:
	python3 -m uvicorn server:app --reload --port 8000

clean:
	rm -rf __pycache__ .pytest_cache
