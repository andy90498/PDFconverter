FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STORAGE_DIR=/app/storage

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libmagic1 libheif-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN groupadd -g 1000 appuser \
    && useradd -m -u 1000 -g 1000 appuser

COPY . .
RUN mkdir -p /app/storage \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 9013

CMD ["gunicorn", "--bind", "0.0.0.0:9013", "--workers", "2", "--threads", "2", "--timeout", "300", "app:app"]
