# Operational Runbook — OKX Opus Trading Bot

## 1. Service Overview

| Service | Port | Health Check |
|---------|------|-------------|
| PostgreSQL | 5432 | `pg_isready -h localhost -p 5432` |
| Redis | 6379 | `redis-cli ping` |
| Grafana | 3000 | `curl http://localhost:3000/api/health` |
| Orchestrator | — | Log: `orchestrator_started` |
| Indicator+Trade | — | Log: `indicator_server_started` |
| Telegram Bot | — | Log: `telegram_bot_started` |

## 2. Startup Sequence

```
1. docker compose up -d postgres redis grafana
2. cd orchestrator && alembic upgrade head
3. cd orchestrator && python -m orchestrator.main
4. cd indicator-trade-server && python -m indicator_trade.main
5. cd ui && python -m ui.main
```

**Or all at once:**
```
docker compose up
```

### First-time Setup

1. Run `alembic upgrade head` to create all tables
2. Orchestrator auto-creates default playbook v1 on first start
3. Verify Grafana datasource at `http://localhost:3000`

## 3. Shutdown Procedure

All services handle SIGINT/SIGTERM gracefully:

1. Signal received → `running = False`
2. Current decision cycle completes
3. Snapshot scheduler stops
4. Redis disconnects
5. DB engine disposes (connection pool drained)
6. Log: `shutdown_complete`

**Force stop:** `docker compose down` (sends SIGTERM, then SIGKILL after 10s)

## 4. Common Operations

### Halt Trading (Emergency)

Via Telegram:
```
/halt
```

Via Redis (manual):
```bash
redis-cli XADD system:alerts '*' type system_alert payload '{"reason":"manual halt","severity":"CRITICAL"}'
```

### Resume Trading

Via Telegram:
```
/resume
```

### View Current State

```
/status     — Bot state, equity, open positions
/positions  — Detailed open positions
/trades 10  — Last 10 trades
/performance — Win rate, profit factor, Sharpe
/playbook   — Current playbook version
```

### Force Reflection

```
/reflect
```

### Trigger Research

```
/research BTC macro outlook
```

## 5. Monitoring

### Grafana Dashboards

| Dashboard | Purpose |
|-----------|---------|
| Portfolio Overview | Equity curve, PnL, win rate, Sharpe |
| Active Positions | Open trades, unrealized PnL |
| Strategy Performance | Win rate by strategy/regime |
| Opus Activity | Decisions/hour, API latency, screener pass rate |
| Risk Monitor | Daily loss, drawdown, exposure, rejections |
| System Health | Bot state, candle count, DB size |
| Playbook Evolution | Version timeline, confidence calibration |

### Key Metrics to Watch

- **Daily loss** > 3% → auto-HALT
- **Max drawdown** > 10% → auto-HALT
- **Open positions** > 3 → risk gate blocks new trades
- **Consecutive losses** ≥ 3 → 30min cooldown
- **Opus API latency** > 30s → timeout, default HOLD

### Log Monitoring

```bash
# Follow orchestrator logs
docker compose logs -f orchestrator

# Search for errors
docker compose logs orchestrator | grep -i error

# Check risk rejections
docker compose logs orchestrator | grep risk_rejected
```

## 6. Troubleshooting

### Bot stuck in HALTED state

**Cause:** Daily loss > 3% or max drawdown > 10%
**Fix:** `/resume` via Telegram (admin only), or restart service

### No trades being placed

**Check:**
1. Screener pass rate (`/status`) — if 0%, market may be quiet
2. Risk gate rejections in Grafana Risk Monitor
3. Opus decisions — if all HOLD, confidence may be low
4. Connection to OKX — check indicator-trade logs

### Redis connection errors

**Cause:** Redis down or network issue
**Fix:**
```bash
docker compose restart redis
# Services auto-reconnect with retry_on_timeout=True
```

### DB connection pool exhausted

**Symptoms:** `pool_timeout` errors in logs
**Fix:**
- Increase `DB_POOL_SIZE` / `DB_MAX_OVERFLOW` in env
- Check for connection leaks (long-running queries)
- `pool_recycle=1800` prevents stale connections

### Stale WebSocket data

**Cause:** OKX WS disconnected without reconnect
**Fix:** Restart indicator-trade-server (has exponential backoff reconnect)

### Playbook not updating

**Check:**
1. Reflection engine running: `grep deep_reflection_complete` in logs
2. Trade count since last reflection: needs ≥ 20 trades or 6 hours
3. Opus API key valid and not rate-limited

## 7. Backup & Recovery

### Database Backup

```bash
docker compose exec postgres pg_dump -U postgres trading_bot > backup_$(date +%Y%m%d).sql
```

### Database Restore

```bash
docker compose exec -T postgres psql -U postgres trading_bot < backup_20260101.sql
```

### Redis (ephemeral)

Redis Streams are ephemeral. No backup needed — data flows through, not stored permanently.

## 8. Scaling Notes

### Connection Pool Defaults

| Service | pool_size | max_overflow | Total Max |
|---------|-----------|-------------|-----------|
| Orchestrator | 10 | 20 | 30 |
| Indicator+Trade | 5 | 10 | 15 |
| UI | 5 | 5 | 10 |

### Redis Timeouts

All services: `socket_timeout=30s`, `socket_connect_timeout=10s`, `retry_on_timeout=True`

### API Rate Limits

- **Anthropic (Opus):** Timeout at 30s, retry 3x with exponential backoff
- **Anthropic (Haiku):** Retry 3x, fail-open (signal=True on error)
- **Perplexity:** Retry 3x, 1-hour cache reduces calls
- **OKX REST:** Retry 3x on read-only calls, NO retry on trade mutations
