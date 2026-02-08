ฉันได้สร้างเนื้อหาบทที่ 5 ถึง 9 ของเอกสาร "AI\_Trading\_Bot\_System\_Design\_v1.0.docx" ให้อยู่ในรูปแบบ Markdown เรียบร้อยแล้ว โดยข้อมูลทั้งหมดถูกรวมไว้ด้านล่างนี้:

```` 
## 5. Database Schema (PostgreSQL + TimescaleDB)

### 5.1 Core Tables

**trades (Trade Journal)**

```sql
CREATE TABLE trades (
    id                  SERIAL PRIMARY KEY,
    trade_id            UUID DEFAULT gen_random_uuid(),
    -- Timing
    opened_at           TIMESTAMPTZ NOT NULL,
    closed_at           TIMESTAMPTZ,
    duration_seconds    INTEGER,
    -- Instrument
    symbol              VARCHAR(30) NOT NULL,
    direction           VARCHAR(5) NOT NULL,      -- LONG/SHORT
    -- Prices
    entry_price         DECIMAL(20,8) NOT NULL,
    exit_price          DECIMAL(20,8),
    stop_loss           DECIMAL(20,8),
    take_profit         DECIMAL(20,8),
    -- Size
    size                DECIMAL(20,8) NOT NULL,
    size_pct            DECIMAL(5,4),             -- % of portfolio
    leverage            DECIMAL(5,2),
    -- P&L
    pnl_usd             DECIMAL(20,4),
    pnl_pct             DECIMAL(10,6),
    fees_usd             DECIMAL(20,4),
    -- AI Decision Context
    strategy_used       VARCHAR(50),
    confidence_at_entry DECIMAL(4,3),
    market_regime       VARCHAR(20),
    opus_reasoning      TEXT,                     -- Full reasoning
    -- Indicators at entry (JSON blob)
    indicators_entry    JSONB,
    indicators_exit     JSONB,
    -- Research context (if any)
    research_context    JSONB,
    -- Self-review (written by Opus post-trade)
    self_review         JSONB,
    -- Exit reason
    exit_reason         VARCHAR(30),
    -- Metadata
    status              VARCHAR(10) DEFAULT 'open',
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

````

**playbook\_versions**

``` sql
CREATE TABLE playbook_versions (
    id              SERIAL PRIMARY KEY,
    version         INTEGER NOT NULL,
    playbook_json   JSONB NOT NULL,
    change_summary  TEXT,
    triggered_by    VARCHAR(30),  -- reflection/manual/init
    performance_at_update JSONB,  -- metrics snapshot
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

```

**reflection\_logs**

``` sql
CREATE TABLE reflection_logs (
    id              SERIAL PRIMARY KEY,
    reflection_type VARCHAR(20) NOT NULL, -- post_trade/periodic
    trade_ids       INTEGER[],           -- trades analyzed
    input_prompt    TEXT,                -- full prompt sent
    output_json     JSONB,              -- Opus response
    playbook_changes JSONB,             -- diff of changes
    old_version     INTEGER,
    new_version     INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

```

**candles (TimescaleDB Hypertable)**

``` sql
CREATE TABLE candles (
    time        TIMESTAMPTZ NOT NULL,
    symbol      VARCHAR(30) NOT NULL,
    timeframe   VARCHAR(5) NOT NULL,  -- 15m/1H/4H/1D
    open        DECIMAL(20,8),
    high        DECIMAL(20,8),
    low         DECIMAL(20,8),
    close       DECIMAL(20,8),
    volume      DECIMAL(30,8),
    indicators  JSONB
);
SELECT create_hypertable('candles', 'time');

```

**research\_cache**

``` sql
CREATE TABLE research_cache (
    id              SERIAL PRIMARY KEY,
    query           TEXT NOT NULL,
    response_json   JSONB NOT NULL,
    source          VARCHAR(20) DEFAULT 'perplexity',
    ttl_seconds     INTEGER DEFAULT 3600,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

```

**performance\_snapshots**

``` sql
CREATE TABLE performance_snapshots (
    id              SERIAL PRIMARY KEY,
    snapshot_type   VARCHAR(20),  -- hourly/daily/weekly
    equity          DECIMAL(20,4),
    total_pnl       DECIMAL(20,4),
    win_rate        DECIMAL(5,4),
    profit_factor   DECIMAL(8,4),
    sharpe_ratio    DECIMAL(8,4),
    max_drawdown    DECIMAL(10,4),
    total_trades    INTEGER,
    metrics_json    JSONB,     -- detailed breakdown
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

```

-----

## 6\. Risk Management System

Risk Management แบ่งเป็น 2 ระดับ: Hardcoded Rules (Opus แก้ไม่ได้) และ Soft Rules (Opus เสนอปรับได้ผ่าน reflection)

### 6.1 Hardcoded Circuit Breakers (Orchestrator Level)

Rules เหล่านี้ enforce ที่ Orchestrator ก่อนส่งคำสั่งไป Trade Server เสมอ ไม่ว่า Opus จะบอกอะไรก็ตาม:

| **Rule**                  | **Threshold** | **Action**                        |
| :-----------------------: | :-----------: | :-------------------------------: |
| Max Daily Loss            | \-3% equity   | HALT all trading for rest of day  |
| Max Single Trade Size     | 5% of equity  | REJECT order, log violation       |
| Max Total Exposure        | 15% of equity | REJECT new positions              |
| Max Concurrent Positions  | 3             | REJECT new positions              |
| Max Drawdown from Peak    | \-10% equity  | EMERGENCY HALT + alert human      |
| Consecutive Loss Cooldown | 3 losses      | 30 min cooldown period            |
| Max Leverage              | 3x            | Cap leverage regardless of signal |
| Required Stop Loss        | always        | REJECT any trade without SL       |
| Max SL Distance           | 3% from entry | REJECT trades with SL too far     |
| Min R:R Ratio             | 1.5:1         | REJECT trades with poor R:R       |
| Correlated Position Check | r \> 0.8      | WARN + reduce combined size       |

### 6.2 Risk Gate Implementation

``` python
class RiskGate:
    def validate(self, decision, account, positions) -> RiskResult:
        checks = [
            self.check_daily_loss(account),
            self.check_max_drawdown(account),
            self.check_position_count(positions),
            self.check_total_exposure(positions, account),
            self.check_trade_size(decision, account),
            self.check_leverage(decision),
            self.check_stop_loss(decision),
            self.check_rr_ratio(decision),
            self.check_correlation(decision, positions),
            self.check_cooldown(),
        ]
        
        failures = [c for c in checks if not c.passed]
        if failures:
            for f in failures:
                log.warning(f'Risk check FAILED: {f.rule}: {f.reason}')
                await db.log_risk_rejection(decision, f)
            return RiskResult(approved=False, failures=failures)
        
        return RiskResult(approved=True)

```

### 6.3 Soft Rules (Opus-Adjustable via Reflection)

Rules เหล่านี้อยู่ใน Playbook และ Opus สามารถปรับได้ผ่าน Reflection Cycle:

  * Position size per strategy (เช่น momentum ใช้ 2% แต่ mean\_reversion ใช้ 1.5%)
  * Time-of-day preferences (Asian session ลด size)
  * Strategy-specific max positions
  * Confidence threshold per strategy (เช่น momentum ต้อง \> 0.7 ถึงจะเทรด)
  * Market regime-specific rules

-----

## 7\. Inter-Component Communication

### 7.1 Redis Streams Architecture

ใช้ Redis Streams เป็น message broker ระหว่าง components เพื่อ decouple และ enable async processing:

| **Stream Name**  | **Producer**        | **Consumer(s)**          |
| :--------------: | :-----------------: | :----------------------: |
| market:snapshots | Indicator Server    | Orchestrator             |
| market:alerts    | Indicator Server    | Orchestrator, Telegram   |
| research:results | Perplexity Agent    | Orchestrator             |
| opus:decisions   | Orchestrator (Opus) | Trade Server, DB Writer  |
| trade:orders     | Orchestrator        | Trade Server             |
| trade:fills      | Trade Server        | Orchestrator, DB Writer  |
| trade:positions  | Trade Server        | Orchestrator, Monitoring |
| system:alerts    | All components      | Telegram Bot, Monitoring |

### 7.2 Message Format (Standardized)

``` json
{
  "msg_id": "uuid",
  "timestamp": "2026-02-07T10:30:00Z",
  "source": "indicator_server",
  "type": "market_snapshot",
  "payload": { "...": "..." },
  "metadata": {
    "latency_ms": 45,
    "version": "1.0"
  }
}

```

-----

## 8\. Monitoring, Alerting & Human Oversight

### 8.1 Grafana Dashboard Panels

| **Panel**            | **Metrics**                                                 |
| :------------------: | :---------------------------------------------------------: |
| Portfolio Overview   | Equity curve, daily PnL, drawdown, Sharpe ratio             |
| Active Positions     | Open trades, unrealized PnL, distance to SL/TP              |
| Strategy Performance | Win rate, avg RR, PnL per strategy                          |
| Opus Activity        | Decisions/hr, avg confidence, API latency, cost/day         |
| Risk Monitor         | Daily loss, max drawdown, exposure, consecutive losses      |
| System Health        | API uptime, WebSocket status, Redis lag, DB latency         |
| Playbook Evolution   | Version history, lesson count, confidence calibration chart |

### 8.2 Telegram Bot Commands

| **Command**             | **Description**                           |
| :---------------------: | :---------------------------------------: |
| /status                 | Current equity, open positions, daily PnL |
| /positions              | Detailed open positions with PnL          |
| /halt                   | Emergency halt all trading                |
| /resume                 | Resume trading after halt                 |
| /research \[query\]     | Manual Perplexity research trigger        |
| /reflect                | Force immediate reflection cycle          |
| /playbook               | View current playbook summary             |
| /trades \[n\]           | Last N trades summary                     |
| /performance            | Performance metrics dashboard             |
| /config \[key\] \[val\] | Update configuration parameter            |

### 8.3 Alert Conditions

| **Severity** | **Condition**           | **Action**                         |
| :----------: | :---------------------: | :--------------------------------: |
| ⚠️ INFO      | Trade executed          | Telegram notification with details |
| ⚠️ INFO      | Reflection completed    | Telegram with playbook changes     |
| ⚠️ WARN      | Consecutive losses (2+) | Telegram + Grafana highlight       |
| ⚠️ WARN      | Risk rule triggered     | Telegram + log rejection           |
| 🔴 CRITICAL   | Max drawdown reached    | HALT + Telegram + email            |
| 🔴 CRITICAL   | System error / API down | Close positions + alert            |
| 🔴 CRITICAL   | Daily loss limit hit    | HALT + notification                |

-----

## 9\. Deployment & Infrastructure

### 9.1 Docker Compose Architecture

``` yaml
services:
  orchestrator:
    build: ./orchestrator
    depends_on: [redis, postgres, indicator-server, trade-server]
    env_file: .env
    restart: always
  
  indicator-server:
    build: ./indicator-server
    depends_on: [redis, postgres]
    restart: always
  
  trade-server:
    build: ./trade-server
    depends_on: [redis, postgres]
    restart: always
  
  perplexity-agent:
    build: ./perplexity-agent
    depends_on: [redis]
    restart: always
  
  telegram-bot:
    build: ./telegram-bot
    depends_on: [redis, postgres]
    restart: always
  
  redis:
    image: redis:7-alpine
    volumes: [redis-data:/data]
  
  postgres:
    image: timescale/timescaledb:latest-pg16
    volumes: [pg-data:/var/lib/postgresql/data]
    environment:
      POSTGRES_DB: trading_bot
      POSTGRES_PASSWORD: ${DB_PASSWORD}
  
  grafana:
    image: grafana/grafana:latest
    ports: ['3000:3000']
    volumes: [grafana-data:/var/lib/grafana]
  
volumes:
  redis-data:
  pg-data:
  grafana-data:

```

### 9.2 Environment Variables

``` bash
# OKX Demo Trading API
OKX_API_KEY=your-demo-api-key
OKX_SECRET_KEY=your-demo-secret
OKX_PASSPHRASE=your-passphrase
OKX_FLAG=1

# Anthropic (Claude Opus 4.6)
ANTHROPIC_API_KEY=sk-ant-...
OPUS_MODEL=claude-opus-4-6
OPUS_MAX_TOKENS=4096

# Perplexity
PERPLEXITY_API_KEY=pplx-...
PERPLEXITY_MODEL=sonar-pro

# Database
DATABASE_URL=postgresql://user:pass@postgres:5432/trading_bot

# Redis
REDIS_URL=redis://redis:6379

# Telegram
TELEGRAM_BOT_TOKEN=...
TELEGRAM_CHAT_ID=...

# Trading Parameters
DECISION_CYCLE_SECONDS=300
INSTRUMENTS=BTC-USDT-SWAP,ETH-USDT-SWAP
MAX_LEVERAGE=3

```

### 9.3 Recommended Server Specs

| **Component** | **Minimum** | **Recommended**                      |
| :-----------: | :---------: | :----------------------------------: |
| CPU           | 4 cores     | 8 cores                              |
| RAM           | 8 GB        | 16 GB                                |
| Storage       | 50 GB SSD   | 100 GB NVMe                          |
| Network       | 100 Mbps    | 1 Gbps, low latency to OKX           |
| Location      | Any         | Singapore / Tokyo (near OKX servers) |

``` 
 
```
