# OKX Opus Trading Bot -- Implementation Plan

## Context

Build a self-learning AI crypto trading bot using Claude Opus 4.6 as the brain, with Haiku 4.5 as a cost-saving screener pre-filter. The system trades BTC-USDT perpetual swaps on OKX Demo Trading (paper trading only). It consists of 3 Python 3.12 + AsyncIO repos communicating via Redis Streams with a shared PostgreSQL + TimescaleDB database.

**Source docs**: `docs/design/01-orchestrator.md`, `docs/design/02-indicator-trade.md`, `docs/design/03-ui.md`, `docs/requirement/` (v1.0 parts 1-3, v1.1 Haiku patch, v1.2 secrets patch)

---

## Phase 0: Infrastructure & Repo Scaffolding

### 0.1 Docker Compose (`docker-compose.yml` at project root)
- PostgreSQL 16 + TimescaleDB container (port 5432)
- Redis 7 container (port 6379, appendonly)
- Grafana container (port 3000, with provisioning mounts)
- Service definitions for: `indicator-trade-server`, `orchestrator`, `ui`
- All services depend on postgres + redis healthchecks
- Environment variables from Doppler (`doppler run -- docker compose up`)

### 0.2 Scaffold 3 Repos (pyproject.toml + src/ layout)

**indicator-trade-server/**
```
Dockerfile | pyproject.toml
src/indicator_trade/
  __init__.py | main.py | config.py | redis_client.py
  indicator/  server.py, ws_public.py, candle_store.py, indicators.py,
              regime_detector.py, snapshot_builder.py
  trade/      server.py, okx_rest.py, ws_private.py, order_executor.py,
              position_manager.py, order_validator.py
  models/     candle.py, ticker.py, indicator_set.py, snapshot.py,
              order.py, position.py, messages.py
  db/         engine.py, candle_repository.py
tests/
```

**orchestrator/**
```
Dockerfile | pyproject.toml | alembic.ini
alembic/    env.py, versions/ (001_initial_schema, 002_screener_logs)
src/orchestrator/
  __init__.py | main.py | config.py | redis_client.py
  state_machine.py | haiku_screener.py | opus_client.py | prompt_builder.py
  risk_gate.py | reflection_engine.py | playbook_manager.py
  perplexity_client.py | news_scheduler.py
  models/     decision.py, snapshot.py, trade.py, playbook.py,
              screen_result.py, reflection.py, research.py, messages.py
  db/         engine.py, models.py, repository.py
tests/
```

**ui/**
```
Dockerfile | pyproject.toml
src/ui/
  __init__.py | main.py | config.py | redis_client.py
  telegram/   bot.py, commands.py, alerts.py, formatters.py
  models/     messages.py
  db/         engine.py, queries.py
grafana/
  provisioning/dashboards/dashboard.yml, datasources/datasource.yml
  dashboards/  (7 JSON files)
tests/
```

### 0.3 Shared Pydantic Message Protocol
Each repo has `models/messages.py` with identical Redis Stream message models:
- `StreamMessage` (base), `MarketSnapshotMessage`, `MarketAlertMessage`, `TradeFillMessage`, `PositionUpdateMessage`, `TradeOrderMessage`, `OpusDecisionMessage`, `SystemAlertMessage`

### 0.4 Redis Client (per-repo, same interface)
```python
class RedisClient:
    async def connect() / disconnect()
    async def publish(stream, message) -> str
    async def subscribe(streams, callback)
    async def create_consumer_group(stream)
    async def ack(stream, message_id)
```
Consumer groups: `orchestrator`, `indicator_trade`, `ui`
Uses `redis.asyncio` with `xreadgroup`, `xadd`, `xack`, connection pooling.

### 0.5 Database Schema (Alembic in orchestrator)
**Migration 001**: trades, playbook_versions, reflection_logs, research_cache, performance_snapshots, risk_rejections, candles (TimescaleDB hypertable)
**Migration 002**: screener_logs

### 0.6 Shared Config Pattern
All repos use `pydantic_settings.BaseSettings` loading from env vars.

### 0.7 Structured Logging (structlog)
```python
structlog.configure(processors=[
    structlog.contextvars.merge_contextvars,
    structlog.processors.add_log_level,
    structlog.processors.TimeStamper(fmt="iso", utc=True),
    structlog.processors.JSONRenderer()  # or ConsoleRenderer for dev
])
```

### Verify
- `docker compose up postgres redis` passes healthchecks
- `alembic upgrade head` creates all tables + hypertable
- Each repo installs cleanly with `pip install -e .`

---

## Phase 1: Indicator Server -- Market Data Pipeline

### 1.1 Pydantic Models
- `Candle` (time, symbol, timeframe, OHLCV)
- `Ticker` (last, bid, ask, volume_24h, change_24h)
- `IndicatorSet` (RSI, MACD, BB, EMA, ATR, VWAP, ADX, StochRSI, OBV, Ichimoku, S/R, derived signals)
- `MarketSnapshot` (ticker, candles, indicators per TF, orderbook, funding, OI, regime, etc.)

### 1.2 Candle Store (in-memory + DB)
- `dict[symbol][timeframe]` -> `deque[Candle]` (max 200)
- `get_as_dataframe()` for indicator computation
- `backfill()` from OKX REST API on startup

### 1.3 DB Candle Repository
- `upsert()`, `bulk_insert()`, `get_recent()` using async SQLAlchemy + asyncpg

### 1.4 Technical Indicators (`indicators.py`)
Use `pandas_ta.Strategy` to compute all 12 indicators in one pass:
RSI(14), MACD(12,26,9), BB(20,2.0), EMA(20,50,200), ATR(14), VWAP, ADX(14), StochRSI(14,14,3,3), OBV, Ichimoku(9,26,52), Support/Resistance (pivot + fractal), Volume Profile
- Derive: `bb_position`, `ema_alignment`, `macd_signal`
- Handle insufficient data gracefully

### 1.5 Regime Detector
ADX > 25 + EMA20 slope > 0 -> trending_up/down, ATR ratio > 1.5 -> volatile, else -> ranging

### 1.6 Snapshot Builder
Every 300s: aggregate candles, compute indicators (3 TFs), detect regime, fetch orderbook/funding/OI via REST, build `MarketSnapshot`, publish to `market:snapshots`

### 1.7 OKX Public WebSocket (`ws_public.py`)
- `WsPublicAsync` from python-okx SDK
- Channels: candle15m, candle1H, candle4H, tickers, books5, funding-rate
- Demo URL: `wss://wspap.okx.com:8443/ws/v5/public`
- Auto-reconnect with exponential backoff

### 1.8 Indicator Server Main Loop
1. Backfill 200 candles per TF via REST
2. Subscribe all WS channels
3. Start snapshot loop (300s interval)
4. Detect anomalies -> publish `market:alerts`

### Verify
- Unit: indicators compute correctly on sample DataFrames
- Unit: regime detector classifies known scenarios
- Integration: connects to OKX demo WS, receives candle updates
- After 5 min: MarketSnapshot appears in Redis `market:snapshots`
- DB: `SELECT COUNT(*) FROM candles` > 0

---

## Phase 2: Trade Server -- Order Execution

### 2.1 OKX REST Client Wrapper (`okx_rest.py`)
Wraps `python-okx` SDK (synchronous) with `asyncio.to_thread()`:
- `place_order()`, `place_algo_order()` (TP/SL), `cancel_order()`, `close_position()`
- `get_balance()`, `get_positions()`, `set_leverage()`
- `get_candles()`, `get_ticker()`, `get_funding_rate()`, `get_open_interest()`
- Demo flag = "1"

### 2.2 Order/Position Models
- `OrderRequest` (action, symbol, side, order_type, size, SL/TP, leverage, strategy, confidence, decision_id)
- `OrderResult` (success, ord_id, status, fill_price, error)
- `Position` (instId, posSide, pos, avgPx, upl, lever, liqPx, margin)
- `AccountState` (equity, available_balance, daily_pnl, max_drawdown_today)

### 2.3 Order Validator
Pre-execution checks: required fields, size > 0, SL/TP logical correctness

### 2.4 Order Executor
1. Validate via OrderValidator
2. OPEN: set leverage -> place main order -> place TP/SL algo order
3. CLOSE: close_position()
4. Publish result to `trade:fills`

### 2.5 OKX Private WebSocket (`ws_private.py`)
- `WsPrivateAsync` from python-okx SDK
- Channels: orders (SWAP), positions (SWAP), account
- Demo URL: `wss://wspap.okx.com:8443/ws/v5/private`

### 2.6 Position Manager
- Track positions in `dict[instId:posSide -> Position]`
- Detect position close when `pos == "0"`
- Publish updates to `trade:positions`

### 2.7 Trade Server Main Loop
1. Initialize OKX REST client
2. Connect private WebSocket, subscribe channels
3. Subscribe Redis `trade:orders` stream
4. On order message: validate -> execute -> publish fill
5. On WS updates: update position manager -> publish position updates

### 2.8 Combined Entry Point (`main.py`)
```python
asyncio.gather(indicator_server.start(), trade_server.start())
```

### Verify
- Unit: order validator catches invalid orders
- Unit: order executor flow with mocked OKX API
- Integration: publish `trade:orders` to Redis -> trade server places order on OKX Demo -> `trade:fills` appears
- OKX Demo web UI shows the placed order

---

## Phase 3: Orchestrator Core -- State Machine, Risk Gate, DB

### 3.1 SQLAlchemy ORM Models (`db/models.py`)
TradeORM, PlaybookVersionORM, ReflectionLogORM, ResearchCacheORM, PerformanceSnapshotORM, ScreenerLogORM, RiskRejectionORM

### 3.2 DB Repositories (`db/repository.py`)
- `TradeRepository`: create, update, get_open, get_recent_closed, get_trades_since
- `PlaybookRepository`: get_latest, save_version, get_history
- `ReflectionRepository`: save, get_last_time, get_trades_since_last
- `ScreenerLogRepository`: log, update_opus_agreement
- `ResearchCacheRepository`: get_cached (1h TTL), save
- `RiskRejectionRepository`: log
- `PerformanceSnapshotRepository`: save (hourly/daily/weekly)

### 3.3 Risk Gate (`risk_gate.py`) -- CRITICAL SAFETY
Hardcoded, non-overridable circuit breakers:
| Rule | Threshold | Action |
|------|-----------|--------|
| Max Daily Loss | -3% equity | HALT |
| Max Drawdown | -10% from peak | EMERGENCY HALT |
| Max Concurrent Positions | 3 | Reject |
| Max Total Exposure | 15% equity | Reject |
| Max Single Trade | 5% equity | Reject |
| Max Leverage | 3x | Reject |
| Required Stop Loss | Always | Reject |
| Max SL Distance | 3% from entry | Reject |
| Min R:R Ratio | 1.5:1 | Reject |
| Consecutive Loss Cooldown | 3 losses -> 30 min | COOLDOWN |
| Correlated Position Check | r > 0.8 | Reject |

### 3.4 Playbook Manager
- Load/create default playbook v1 (regime rules, strategies, empty lessons)
- Version management with change tracking

### 3.5 News Scheduler
- FOMC/CPI/NFP dates for 2026
- `is_news_window(minutes_before=30)` for screener bypass

### 3.6 State Machine Skeleton
States: IDLE -> COLLECTING -> SCREENING -> RESEARCHING -> ANALYZING -> RISK_CHECK -> EXECUTING -> CONFIRMING -> JOURNALING -> REFLECTING -> HALTED -> COOLDOWN
- Stub AI calls with placeholders (replaced in Phase 4)
- Full state transition logic

### Verify
- Unit: every risk gate rule with boundary values (-3.0% vs -2.9% vs -3.1%)
- Unit: state transitions in correct order
- Unit: playbook CRUD operations
- DB: repositories create/read correctly
- Alembic: upgrade + downgrade works cleanly

---

## Phase 4: Orchestrator AI Integration

### 4.1 Haiku Screener (`haiku_screener.py`)
- `AsyncAnthropic` client, model: `claude-haiku-4-5-20251001`
- Compact ~500 token prompt: price, RSI, MACD signal, regime, ADX, volume, funding, BB position, EMA alignment
- Response: `{"signal": bool, "reason": str}`
- Default to signal=True on parse error
- Bypass conditions: open position, news window, market anomaly (>3% 1H), funding spike (>0.05%), manual trigger

### 4.2 Prompt Builder (`prompt_builder.py`)
- `build_analysis_prompt()`: XML-structured, ~3000 tokens with all data sections
- `build_post_trade_prompt()`: ~2000 tokens
- `build_deep_reflection_prompt()`: ~8000 tokens with full performance data
- `build_research_query()`: contextual query for Perplexity

### 4.3 Opus Client (`opus_client.py`)
- `AsyncAnthropic` client, model: `claude-opus-4-6`
- `analyze()`: full trading decision -> `OpusDecision`
- `reflect_trade()`: post-trade review -> `TradeReview`
- `deep_reflect()`: periodic deep reflection -> `DeepReflectionResult`
- 30s timeout via `asyncio.wait_for()`, default HOLD on timeout
- Temperature: 0.2 for analysis, 0.3 for reflection

### 4.4 Perplexity Client (`perplexity_client.py`)
- `httpx.AsyncClient` POST to `https://api.perplexity.ai/chat/completions`
- Model: `sonar-pro`
- 1-hour cache in `research_cache` table
- Triggers: scheduled news, market anomaly, funding spike, OI change

### 4.5 Reflection Engine (`reflection_engine.py`)
- Post-trade: after every position close, Opus reviews the trade
- Periodic deep: every 20 trades OR 6 hours
- Deep reflection updates playbook (new version), adjusts strategies/lessons/confidence
- Performance metrics: win_rate, profit_factor, sharpe, breakdowns by strategy/regime/time

### 4.6 Complete State Machine (replace stubs)
Full decision cycle per instrument:
1. COLLECTING: read MarketSnapshot from Redis, fetch positions/account from trade server
2. SCREENING: Haiku screens (unless bypass). Log result. Skip if no signal.
3. RESEARCHING: conditional Perplexity call if anomaly/news
4. ANALYZING: Opus full analysis with playbook + recent trades context
5. RISK_CHECK: risk gate validates. Log rejection if failed.
6. EXECUTING: publish TradeOrder to `trade:orders`, publish OpusDecision to `opus:decisions`
7. CONFIRMING: wait for fill from `trade:fills` (30s timeout)
8. JOURNALING: save trade record to DB
9. REFLECTING: check if periodic reflection needed

Background task: monitor `trade:positions` for closes -> post-trade reflection -> update risk gate

### 4.7 Screener Accuracy Tracking
After each Opus call triggered by Haiku pass, update screener_log with Opus agreement

### Verify
- Unit: Haiku prompt construction and response parsing (mock API)
- Unit: prompt builder XML structure
- Integration (mock AI): full cycle with recorded API responses
- Live test: single cycle with real APIs against OKX Demo
- Check screener_logs, opus:decisions stream, risk rejection if applicable
- Verify Anthropic usage matches cost estimates

---

## Phase 5: Telegram Bot (can parallel with Phase 3-4)

### 5.1 DB Queries (read-only, `db/queries.py`)
`get_equity_and_pnl()`, `get_open_positions()`, `get_recent_trades()`, `get_latest_playbook()`, `get_performance_metrics()`, `get_screener_pass_rate()`, `get_latest_decision()`, `get_daily_trade_summary()`

### 5.2 Message Formatters (`formatters.py`)
MarkdownV2 formatting for: status, positions, trades list, performance, playbook, alerts, fills

### 5.3 Command Handlers (`commands.py`)
10 commands: `/status`, `/positions`, `/trades [n]`, `/performance`, `/playbook`, `/halt [reason]` (admin), `/resume` (admin), `/research [query]`, `/reflect`, `/config [key] [value]` (admin)

### 5.4 Alert Sender (`alerts.py`)
- Subscribe: trade:fills, trade:positions, opus:decisions, system:alerts, market:alerts
- Severity routing: INFO, WARN, CRITICAL
- Cooldown: 60s between same-type alerts
- Silent hours (configurable UTC)
- CRITICAL always sends immediately

### 5.5 Bot Application (`bot.py`)
- `python-telegram-bot` Application with CommandHandlers
- Authorization check: chat_id matches config
- Alert listener as background asyncio task

### Verify
- Unit: formatters produce valid Markdown
- Unit: alert cooldown logic
- Integration: `/status` returns data from DB
- Integration: publish `trade:fills` to Redis -> Telegram alert received
- Admin: `/halt` publishes system:alerts

---

## Phase 6: Grafana Dashboards (can parallel with Phase 3-4)

### 6.1 PostgreSQL Datasource
- Read-only `grafana_reader` user
- Provisioned via `datasource.yml`

### 6.2 Seven Dashboard JSON Files
1. **Portfolio Overview**: equity curve, daily PnL, drawdown, Sharpe, win rate
2. **Active Positions**: open trades table, unrealized PnL, SL/TP distances
3. **Strategy Performance**: win rate/PnL/R:R by strategy, trade distribution
4. **Opus Activity**: decisions/hour, confidence, screener pass rate, API latency, cost
5. **Risk Monitor**: daily loss gauge, drawdown gauge, exposure, consecutive losses, rejections
6. **System Health**: bot state, heartbeat, screener throughput, DB size, candle count
7. **Playbook Evolution**: version timeline, lessons, change log, confidence calibration

### 6.3 Auto-provisioning via Docker volume mounts

### Verify
- All 7 dashboards appear in Grafana "Trading Bot" folder
- Datasource connects to PostgreSQL
- Panels render with seeded test data

---

## Phase 7: Integration Testing & End-to-End

### Full stack tests:
1. **Startup**: `docker compose up` all containers healthy
2. **Data flow**: indicator server -> Redis snapshots -> orchestrator receives
3. **Decision cycle**: Haiku screen -> Opus analyze -> risk check -> order -> fill -> journal
4. **Position lifecycle**: open -> monitor -> close -> post-trade reflection
5. **Safety**: risk gate rejection, `/halt` + `/resume`, consecutive loss cooldown, max drawdown halt
6. **Error handling**: Redis disconnect/reconnect, Postgres disconnect, WS reconnect, API timeout -> HOLD
7. **Monitoring**: Grafana shows real data, Telegram alerts flow, screener rate 15-25%

### Success criteria:
- All containers running 24h+ without crashes
- At least 1 complete trade cycle
- Post-trade reflection saved
- Risk gate exercised
- All Telegram commands work
- All Grafana dashboards render

---

## Phase 8: Polish & Production Readiness

- Connection pooling tuning (Redis, PostgreSQL)
- Query optimization with `EXPLAIN ANALYZE`
- Retry + exponential backoff on all external APIs
- Graceful shutdown handlers (SIGTERM/SIGINT)
- Performance snapshot scheduler (hourly/daily/weekly)
- Default playbook v1 initialization
- READMEs and operational runbook
- Doppler setup + SOPS backup procedure

---

## Key Library Versions (from Context7)

| Library | Usage | Key Pattern |
|---------|-------|-------------|
| `python-okx` | OKX REST + WebSocket | `Trade.TradeAPI(key, secret, pass, False, "1")`, `WsPublicAsync`, `WsPrivateAsync` |
| `anthropic` | Claude Opus/Haiku | `AsyncAnthropic()`, `client.messages.create()`, `client.messages.parse()` with Pydantic |
| `python-telegram-bot` | Telegram bot | `Application.builder().token().build()`, `CommandHandler`, `run_polling()` |
| `redis` (redis-py) | Redis Streams | `redis.asyncio`, `xadd`, `xreadgroup`, `xack`, `xgroup_create(mkstream=True)` |
| `sqlalchemy` | PostgreSQL ORM | `create_async_engine("postgresql+asyncpg://...")`, `async_sessionmaker`, Mapped columns |
| `pandas-ta` | Technical indicators | `ta.Strategy([...])`, `df.ta.strategy(strategy)` |
| `structlog` | Structured logging | `merge_contextvars`, `JSONRenderer`, `TimeStamper(fmt="iso", utc=True)` |
| `pydantic` / `pydantic-settings` | Models + config | `BaseModel`, `BaseSettings` |
| `httpx` | Perplexity API | `httpx.AsyncClient()` POST |
| `alembic` | DB migrations | Async env with asyncpg |

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| python-okx is synchronous | Wrap all calls in `asyncio.to_thread()` |
| Opus response parse failures | Default to HOLD, log raw response |
| WebSocket disconnections | Auto-reconnect with exponential backoff (max 60s) |
| TimescaleDB extension | `CREATE EXTENSION IF NOT EXISTS timescaledb` before migrations |
| Haiku too aggressive filtering | Monitor pass rate, alert if <10% for 24h |
| API cost overrun | Daily budget tracking, alert at 80% |
