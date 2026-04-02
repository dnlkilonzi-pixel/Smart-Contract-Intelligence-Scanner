# Smart Contract Intelligence Scanner

A **production-grade Web3 security and analytics platform** that scans smart contracts, detects vulnerabilities, profiles behaviour, and assigns dynamic risk scores.

---

## 🏗️ Architecture

```
app/
├── api/v1/          # FastAPI route handlers (scanner, risk, wallet)
├── core/
│   ├── scanner/     # Slither + Mythril integrations
│   ├── analyzer/    # Vulnerability parser, risk engine, contract profiler
│   ├── intelligence/# Blockchain client, wallet analyzer, rug-pull detector
│   └── ai/          # ML classifier + feature extractor
├── models/          # SQLAlchemy ORM models
├── schemas/         # Pydantic request/response schemas
├── services/        # Orchestration services (scan, wallet, report)
└── utils/           # Logging, helpers
tests/               # pytest test suite
docker/              # Dockerfile + docker-compose
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- PostgreSQL 14+
- Redis 7+
- Slither: `pip install slither-analyzer`
- Mythril: `pip install mythril`
- solc: `pip install solc-select && solc-select install 0.8.19 && solc-select use 0.8.19`

### Local Setup

```bash
# 1. Clone and install
git clone <repo>
cd Smart-Contract-Intelligence-Scanner
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env — set DATABASE_URL, ETHERSCAN_API_KEY, ETH_RPC_URL

# 3. Start PostgreSQL + Redis (or use Docker)
docker-compose -f docker/docker-compose.yml up db redis -d

# 4. Run the API
uvicorn app.main:app --reload
```

### Docker (all-in-one)

```bash
docker-compose -f docker/docker-compose.yml up --build
```

API available at: `http://localhost:8000`
Swagger docs: `http://localhost:8000/docs`

---

## 📡 API Endpoints

### Contract Scanning

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/scanner/scan` | Scan a contract (source or address) |
| `POST` | `/api/v1/scanner/scan/report/json` | Scan + return JSON audit report |
| `POST` | `/api/v1/scanner/scan/report/html` | Scan + return HTML audit report |

**Example request:**
```json
POST /api/v1/scanner/scan
{
  "source_code": "pragma solidity ^0.8.0;\ncontract Foo { ... }",
  "compiler_version": "0.8.19",
  "enable_mythril": false
}
```

**Or by address (requires verified contract on Etherscan):**
```json
{
  "address": "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"
}
```

### Risk Scoring

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/risk/score` | Calculate risk score from findings list |

### Wallet Intelligence

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/wallet/{address}/intelligence` | Wallet behaviour + rug-pull assessment |

---

## 🔍 Features

### Vulnerability Detection
- **Reentrancy** (ETH + token variants)
- **Integer Overflow/Underflow**
- **Access Control** issues
- **Rug-pull patterns** (arbitrary ETH/ERC20 send)
- **Self-destruct** abuse
- **Flash loan** exploitation patterns
- 50+ Slither detectors + Mythril SWC coverage

### Risk Scoring Engine
Normalised 0-100 score based on:
- Severity-weighted findings with diminishing returns
- Contract profile flags (proxy, minting, ownership)
- AI confidence boosting

| Score | Level |
|-------|-------|
| 0-14 | Low |
| 15-39 | Medium |
| 40-69 | High |
| 70-100 | Critical |

### AI Classification
- Random Forest classifier trained on synthetic heuristic-labelled data
- Auto-bootstraps on first run (no pre-trained model required)
- Categories: Reentrancy, Integer Overflow, Access Control, Rug-pull Risk, Unchecked Return Value, Other

### Contract Profiling
- Proxy / upgradeability detection
- Minting rights detection
- Ownership / access control patterns
- Flash loan capability
- Self-destruct presence

### Wallet Intelligence
- Transaction history analysis
- Deployed contract tracking
- Large outflow detection
- Flash loan activity
- Rug-pull behavioural scoring

---

## 🧪 Running Tests

```bash
pip install pytest pytest-asyncio pytest-cov
pytest tests/ -v --cov=app
```

---

## 🔧 Configuration

All settings are controlled via environment variables (see `.env.example`):

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL async connection string |
| `ETH_RPC_URL` | Ethereum RPC endpoint (Infura / Alchemy) |
| `ETHERSCAN_API_KEY` | For fetching verified source + wallet data |
| `SLITHER_TIMEOUT` | Max seconds for Slither analysis (default 120) |
| `MYTHRIL_TIMEOUT` | Max seconds for Mythril analysis (default 300) |
| `AI_MODEL_PATH` | Path to persisted sklearn model (auto-created) |

---

## 🗺️ Roadmap

- [x] Celery async task queue for long-running scans
- [x] WebSocket scan progress streaming
- [x] Multi-chain support (BSC, Polygon, Arbitrum)
- [ ] Graph-based rug-pull network analysis (Neo4j backend)
- [x] Fine-tuned LLM vulnerability explanation layer
- [x] CI/CD pipeline with audit gate

---

## ⚡ Async Scans (Celery)

Submit a scan to the background queue and poll for progress:

```bash
# Submit
curl -X POST http://localhost:8000/api/v1/scanner/scan/async \
  -H 'Content-Type: application/json' \
  -d '{"source_code": "pragma solidity ^0.8.0; contract Foo {}"}'
# → {"task_id": "abc123…", "status": "queued", "status_url": "/api/v1/scanner/task/abc123…"}

# Poll
curl http://localhost:8000/api/v1/scanner/task/abc123…
# → {"task_id": "abc123…", "state": "PROGRESS", "progress": 10, "step": "running_static_analysis"}

# Or stream progress via WebSocket
wscat -c ws://localhost:8000/api/v1/realtime/scan/abc123…
```

Start the Celery worker:

```bash
celery -A app.worker worker --loglevel=info --concurrency=2
```

---

## 🌐 Multi-Chain Support

Pass `chain` in the request body to scan contracts on other networks:

```bash
curl -X POST http://localhost:8000/api/v1/scanner/scan \
  -H 'Content-Type: application/json' \
  -d '{"address": "0x…", "chain": "bsc"}'
```

Supported chains: `ethereum` (default), `bsc`, `polygon`, `arbitrum`.

Configure RPC endpoints and block explorer API keys in `.env` (see `.env.example`).

---

## 🤖 LLM Vulnerability Explanations

Enable AI-generated explanations by setting in `.env`:

```env
LLM_EXPLANATION_ENABLED=true
OPENAI_API_KEY=sk-…
OPENAI_MODEL=gpt-4o-mini   # or gpt-4o
```

Each vulnerability finding in scan responses will include an `explanation` field
with a human-readable description of the risk and suggested mitigation.
A rule-based fallback is used automatically when the LLM is not configured.
