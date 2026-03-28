FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    pkg-config \
    libcairo2-dev \
    libjpeg-dev \
    zlib1g-dev \
    libfreetype6-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN --mount=type=cache,target=/root/.cache/uv \
    pip install uv && \
    uv pip install --system --index-strategy unsafe-best-match -r requirements.txt && \
    uv pip install --system openai httpx

COPY . .

# 혹시 복사된 .pyc / __pycache__ 제거 (stale bytecode 방지)
RUN find . -name "*.pyc" -delete && find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]