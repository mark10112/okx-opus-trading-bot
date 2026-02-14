# Environment Setup Guide

## 1. Create `.env` file

```bash
cp .env.example .env
```

Edit `.env` and fill in your real values:

| Variable | Where to get |
|----------|-------------|
| `POSTGRES_PASSWORD` | Choose any password for local PostgreSQL |
| `OKX_API_KEY` / `OKX_SECRET_KEY` / `OKX_PASSPHRASE` | OKX Demo Trading → API Management |
| `ANTHROPIC_API_KEY` | https://console.anthropic.com/settings/keys |
| `PERPLEXITY_API_KEY` | https://www.perplexity.ai/settings/api |
| `TELEGRAM_BOT_TOKEN` | @BotFather → `/newbot` |
| `TELEGRAM_CHAT_ID` | `https://api.telegram.org/bot<TOKEN>/getUpdates` after sending `/start` |
| `TELEGRAM_ADMIN_IDS` | Same as CHAT_ID (JSON array format: `[123456789]`) |
| `GRAFANA_ADMIN_PASSWORD` | Choose any password for Grafana admin |
| `GRAFANA_DB_PASSWORD` | Password for read-only `grafana_reader` DB user |

## 2. Run Integration Tests

Start test infrastructure (isolated ports — won't conflict with dev):

```bash
docker compose -f docker-compose.test.yml up -d
```

Wait for healthy containers, then run tests:

```bash
# Orchestrator integration tests (real Redis + PostgreSQL, mock AI)
cd orchestrator
python -m pytest tests/integration/ -v -m integration

# UI integration tests (real Redis + PostgreSQL, mock Telegram)
cd ui
python -m pytest tests/integration/ -v -m integration

# OKX live tests (requires real OKX Demo API keys in .env)
cd indicator-trade-server
python -m pytest tests/integration/ -v -m okx_live
```

Stop test infrastructure:

```bash
docker compose -f docker-compose.test.yml down
```

## 3. Run Full Stack (All Services)

```bash
docker compose up --build -d
```

Verify all containers are healthy:

```bash
docker compose ps
```

Expected: 6 containers running (postgres, redis, grafana, indicator-trade-server, orchestrator, ui).

## 4. Verify Services

| Check | Command / URL |
|-------|--------------|
| PostgreSQL | `docker compose exec postgres psql -U postgres -d trading_bot -c "SELECT 1"` |
| Redis | `docker compose exec redis redis-cli PING` |
| Grafana | http://localhost:3000 (admin / `GRAFANA_ADMIN_PASSWORD`) |
| Candles in DB | `docker compose exec postgres psql -U postgres -d trading_bot -c "SELECT COUNT(*) FROM candles"` |
| Redis streams | `docker compose exec redis redis-cli XLEN market:snapshots` |
| Orchestrator logs | `docker compose logs -f orchestrator` |
| Telegram | Send `/status` to your bot |
