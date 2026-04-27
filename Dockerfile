FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies (MT5 excluded — Linux incompatible)
COPY requirements.txt .
RUN pip install --no-cache-dir \
    pandas \
    numpy \
    ccxt \
    pydantic \
    "fastapi[all]" \
    uvicorn \
    python-dotenv \
    schedule \
    matplotlib \
    requests \
    websockets \
    "alpaca-trade-api" \
    scikit-learn \
    joblib \
    fpdf2 \
    yfinance \
    httpx \
    aiofiles

# Copy full bot source
COPY . .

# Remove Windows-only imports gracefully via env flag
ENV MT5_DISABLED=true
ENV PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
  CMD curl -f http://localhost:8080/api/status || exit 1

EXPOSE 8080

CMD ["uvicorn", "web_server:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "2"]
