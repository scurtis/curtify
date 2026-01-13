FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# Cloud Run uses the PORT environment variable
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
