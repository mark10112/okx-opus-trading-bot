# OKX Opus Trading Bot

Self-learning AI crypto trading bot powered by Claude Opus 4.6, Haiku 4.5 screener, and Perplexity research. Trades BTC-USDT perpetual swaps on OKX with automated risk management, playbook evolution, and Telegram alerts.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Indicator +    │     │   Orchestrator   │     │     UI      │
│  Trade Server   │◄───►│   (AI Brain)     │◄───►│ Telegram +  │
│  (OKX Data +    │     │  Claude Opus 4.6 │     │  Grafana    │
│   Execution)    │     │  Haiku Screener  │     │             │
└────────┬────────┘     └────────┬─────────┘     └──────┬──────┘
         │                       │                       │
         └───────────┬───────────┘───────────────────────┘
                     │
         ┌───────────┴───────────┐
         │   Redis Streams       │
         │   PostgreSQL + TS     │
         └───────────────────────┘
```

### Repositories

| Repo | Purpose |
|------|---------|
| `orchestrator/` | AI brain: decision cycle, risk gate, playbook, reflection |
| `indicator-trade-server/` | OKX market data pipeline + order execution |
| `ui/` | Telegram bot + Grafana dashboards |

### Communication

- **Redis Streams** with consumer groups (`orchestrator`, `indicator_trade`, `ui`)
- **PostgreSQL 16 + TimescaleDB** for trades, playbook versions, reflections, performance snapshots
- **Pydantic message protocol** shared across all 3 repos

## Quick Start

### Prerequisites

- Python 3.12+
- Docker & Docker Compose
- OKX API keys (demo trading)
- Anthropic API key (Claude Opus + Haiku)
- Perplexity API key
- Telegram bot token

### 1. Start Infrastructure

```bash
docker compose up -d postgres redis grafana
```

### 2. Run Migrations

```bash
cd orchestrator
alembic upgrade head
```

### 3. Configure Secrets

Secrets are managed via [Doppler](https://www.doppler.com/). See `docs/setup-env.md` for details.

Required environment variables:
- `ANTHROPIC_API_KEY`
- `PERPLEXITY_API_KEY`
- `OKX_API_KEY`, `OKX_SECRET_KEY`, `OKX_PASSPHRASE`
- `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
- `DATABASE_URL`, `REDIS_URL`

### 4. Start Services

```bash
# Terminal 1: Orchestrator
cd orchestrator && python -m orchestrator.main

# Terminal 2: Indicator + Trade Server
cd indicator-trade-server && python -m indicator_trade.main

# Terminal 3: Telegram Bot
cd ui && python -m ui.main
```

### Docker Compose (all services)

```bash
docker compose up
```

## Development

### Install Dependencies

```bash
# Each repo
cd orchestrator && pip install -e ".[dev]"
cd indicator-trade-server && pip install -e ".[dev]"
cd ui && pip install -e ".[dev]"
```

### Run Tests

```bash
# Unit tests (each repo)
cd orchestrator && python -m pytest tests/unit/ -v
cd indicator-trade-server && python -m pytest tests/unit/ -v
cd ui && python -m pytest tests/unit/ -v

# Integration tests (requires Docker infra on ports 5433/6380)
docker compose -f docker-compose.test.yml up -d
cd orchestrator && python -m pytest tests/integration/ -v
cd indicator-trade-server && python -m pytest tests/integration/ -v
cd ui && python -m pytest tests/integration/ -v
```

### Pre-commit Hooks

```bash
pip install pre-commit
pre-commit install
# Runs ruff lint + format on every commit
```

## Decision Cycle

```
IDLE → COLLECTING → SCREENING → RESEARCHING → ANALYZING → RISK_CHECK → EXECUTING → CONFIRMING → JOURNALING → REFLECTING
```

1. **Collect** market snapshots (candles, indicators, regime) from Redis
2. **Screen** with Haiku 4.5 (fast, cheap pre-filter)
3. **Research** via Perplexity if news/anomaly detected
4. **Analyze** with Opus 4.6 (full decision with playbook context)
5. **Risk check** against 11 circuit breaker rules
6. **Execute** via OKX REST API
7. **Journal** trade to PostgreSQL
8. **Reflect** post-trade + periodic deep reflection (updates playbook)

## Key Features

- **Self-learning playbook** that evolves via deep reflection every 20 trades
- **11 risk gate rules** with circuit breakers (daily loss, drawdown, position limits)
- **Haiku pre-screener** to reduce Opus API costs
- **Perplexity research** with 1-hour cache for market context
- **Performance snapshots** (hourly/daily/weekly) for Grafana dashboards
- **Telegram alerts** with severity routing and cooldown
- **Retry with exponential backoff** on all external API calls
- **Connection pooling** tuned for production (pool_recycle, LIFO, timeouts)

## Documentation

- `docs/design/` — System design documents
- `docs/requirement/` — Full system requirements
- `docs/implementation-plan.md` — Phase-by-phase implementation plan
- `docs/setup-env.md` — Environment setup guide
