FROM python:3.11-slim

# Minimal system deps — curl for healthchecks only
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tram_analyzer.py .
COPY api.py .

RUN mkdir -p /app/output

# Flush Python stdout immediately — avoids buffered/stale docker logs
ENV PYTHONUNBUFFERED=1

EXPOSE 5001

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -sf http://localhost:5001/health || exit 1

CMD ["python", "api.py"]
