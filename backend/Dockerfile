FROM python:3.11-slim

WORKDIR /app

ENV PATH="/root/.local/bin:${PATH}"

COPY requirements.txt .
RUN pip install --no-cache-dir pipx && pipx install kaggle && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
