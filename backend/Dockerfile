FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# PROCESS_TYPE selects which process this container runs.
# Deploy this same image twice: once as "api", once as "worker".
ENV PROCESS_TYPE=api
CMD ["sh", "-c", "if [ \"$PROCESS_TYPE\" = \"worker\" ]; then python worker.py; else uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}; fi"]
