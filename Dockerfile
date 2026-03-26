
FROM python:3.11-slim

WORKDIR /app

# weasyprint (PDF)
RUN apt-get update && apt-get install -y \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libffi-dev \
    libcairo2 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/uv \
    pip install uv && \
    uv pip install --system --index-strategy unsafe-best-match -r requirements.txt

RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system weasyprint openai httpx

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]