FROM python:3.11-slim

# Install system dependencies required by solc and Slither
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    git \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install solc-select for multi-version Solidity compiler management
RUN pip install --no-cache-dir solc-select && solc-select install 0.8.19 && solc-select use 0.8.19

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip install --no-cache-dir slither-analyzer

# Mythril is an optional deep-analysis tool.  It depends on numpy==1.19.0 which
# is incompatible with Python 3.11+ build tooling.  Install it separately so
# that the main image still works even if mythril installation fails.
RUN pip install --no-cache-dir mythril || echo "WARNING: mythril installation failed; symbolic execution will be unavailable"

# Copy application source
COPY . .

# Create model directory
RUN mkdir -p models

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
