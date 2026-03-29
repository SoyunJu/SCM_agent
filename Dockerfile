FROM python:3.11-slim

RUN sed -i 's/deb.debian.org/mirror.kakao.com/g' /etc/apt/sources.list.d/debian.sources

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    pkg-config \
    libcairo2-dev \
    fonts-nanum \
    && fc-cache -fv \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN pip install uv
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --system --index-strategy unsafe-best-match -r requirements.txt

COPY . .

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]