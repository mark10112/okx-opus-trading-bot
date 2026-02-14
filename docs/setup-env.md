# Environment Setup Guide

## Secret Management

This project supports two approaches for managing secrets:

### Option A: Doppler (Recommended for Production)

[Doppler](https://www.doppler.com/) is a secrets management platform that injects environment variables at runtime.

**Setup:**

```bash
# Install Doppler CLI
brew install dopplerhq/cli/doppler   # macOS
# or: curl -Ls https://cli.doppler.com/install.sh | sh

# Login
doppler login

# Setup project (run from repo root)
doppler setup
# Select project: okx-opus-trading-bot
# Select config: dev / staging / prod

# Run any service with Doppler-injected secrets
doppler run -- python -m orchestrator.main
doppler run -- python -m indicator_trade.main
doppler run -- python -m ui.main
```

**Doppler project structure:**

| Config | Purpose |
|--------|---------|
| `dev` | Local development (demo trading) |
| `staging` | Integration testing |
| `prod` | Production (real trading — future) |

**All secrets are stored in Doppler, never in `.env` files in production.**

### Option B: SOPS + age (Encrypted `.env` Files)

For teams that prefer file-based secrets, [SOPS](https://github.com/getsops/sops) encrypts `.env` files with [age](https://github.com/FiloSottile/age) keys.

**Setup:**

```bash
# Install
brew install sops age   # macOS
# or: go install github.com/getsops/sops/v3/cmd/sops@latest

# Generate age key (once per developer)
age-keygen -o ~/.config/sops/age/keys.txt
# Copy the public key (age1...) and update .sops.yaml

# Encrypt .env file
sops --encrypt .env > .enc.env

# Decrypt and use
sops --decrypt .enc.env > .env
```

**`.sops.yaml` configuration:**

The `.sops.yaml` file in the repo root defines which age public keys can decrypt. Add each team member's public key:

```yaml
creation_rules:
  - path_regex: \.enc\.env$
    age: >-
      age1abc...your_key_here,age1def...teammate_key_here
```

**Rules:**
- `.env` is in `.gitignore` — never committed
- `.enc.env` is safe to commit (encrypted)
- Each developer needs their age private key in `~/.config/sops/age/keys.txt`

### Option C: Plain `.env` (Local Dev Only)

```bash
cp .env.example .env
# Edit .env with your real values
```

**⚠️ Never commit `.env` to git. It is in `.gitignore`.**

## 1. Required Environment Variables

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

### Optional Tuning Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DB_POOL_SIZE` | 10 (orch), 5 (others) | SQLAlchemy connection pool size |
| `DB_MAX_OVERFLOW` | 20 (orch), 10/5 | Max overflow connections |
| `DB_POOL_RECYCLE` | 1800 | Recycle connections after N seconds |
| `DB_POOL_TIMEOUT` | 30 | Wait timeout for pool connection |
| `DECISION_CYCLE_SECONDS` | 300 | Orchestrator cycle interval |
| `MAX_OPUS_TIMEOUT_SECONDS` | 30 | Opus API call timeout |

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
