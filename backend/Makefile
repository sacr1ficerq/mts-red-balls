.PHONY: install run hello-world test

VENV = venv
PYTHON = $(VENV)/bin/python3
PIP = $(VENV)/bin/pip

install:
	python3 -m venv $(VENV)
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt

run:
	$(PYTHON) server.py

hello-world:
	$(PYTHON) -c "print('Hello from Backend')"

test:
	$(PYTHON) -m pytest tests/ -v
