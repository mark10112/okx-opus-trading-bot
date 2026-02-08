ฉันได้สร้างเนื้อหาบทที่ 1 ถึง 4 ของเอกสาร "AI\_Trading\_Bot\_System\_Design\_v1.0.docx" ให้อยู่ในรูปแบบ Markdown เรียบร้อยแล้ว โดยข้อมูลทั้งหมดถูกรวมไว้ด้านล่างนี้:

``` markdown
# SYSTEM DESIGN DOCUMENT: AI-Powered Trading Bot with Self-Learning Capabilities

OKX Demo Trading · Claude Opus 4.6 · Perplexity Research

Version 1.0
February 2026
*Classification: Confidential*

---

## 1. Executive Summary

เอกสารนี้เป็น System Design ฉบับเต็มสำหรับระบบ AI Trading Bot ที่ใช้ Claude Opus 4.6 เป็นสมองหลักในการตัดสินใจเทรด โดยทำงานร่วมกับ Perplexity AI เป็นนักวิจัย (Research Analyst) และ Indicator/Trade Server ที่เชื่อมต่อกับ OKX Exchange ผ่าน Demo Trading API (Paper Trade)

### 1.1 Core Objectives

*   สร้างระบบ Paper Trading อัตโนมัติบน OKX Demo Environment
*   ใช้ Claude Opus 4.6 วิเคราะห์ข้อมูล Technical + Fundamental + Sentiment แบบ multi-dimensional
*   ใช้ Perplexity AI ค้นหาข่าว macro events และข้อมูลเชิงลึกแบบ real-time
*   ระบบ Self-Learning: วิเคราะห์ผลเทรดตัวเอง สร้าง Playbook และปรับปรุงอย่างต่อเนื่อง
*   มี Risk Management แบบ hardcoded ที่ AI แก้ไม่ได้

### 1.2 Target Trading Profile

| **Parameter** | **Value** |
| :---: | :---: |
| Exchange | OKX (Demo Trading / Paper Trade) |
| Instruments | BTC-USDT-SWAP, ETH-USDT-SWAP (Perpetual Futures) |
| Timeframe | 15m / 1H / 4H (Multi-timeframe analysis) |
| Trading Mode | Cross Margin, Long/Short Mode |
| Max Leverage | 3x (conservative for paper trade learning phase) |
| Decision Cycle | Every 5 minutes (configurable) |
| Initial Capital | $100,000 USDT (OKX Demo default) |

---

## 2. High-Level Architecture

ระบบประกอบด้วย 5 components หลักที่สื่อสารกันผ่าน Redis Message Queue:

### 2.1 Architecture Diagram (Textual)

```

┌─────────────────────────────────────────────────────────────┐
│              ORCHESTRATOR (Python AsyncIO)                │
│      Main Loop · State Machine · Scheduling · Risk Gate     │
└────────┬────────────┬────────────┬─────────────┬────────────┘
│            │            │             │
┌────┴────┐  ┌────┴────┐  ┌────┴────┐  ┌─────┴─────┐
│ Opus 4.6 │  │Perplexity│  │ Indicator│  │  Trade     │
│ (Brain)  │  │(Research)│  │ Server   │  │  Server    │
└─────────┘  └─────────┘  └─────────┘  └───────────┘
│                        │             │
│              ┌────────┴─────────┴────────┐
│              │  OKX Demo Trading API  │
│              │  (Paper Trade / flag=1)│
│              └───────────────────────┘
┌────┴──────────────────────────────────────────┐
│  PostgreSQL + TimescaleDB                       │
│  Trade Journal · Playbook · Performance Metrics  │
└───────────────────────────────────────────────┘

```` 

### 2.2 Component Summary

| **Component** | **Technology** | **Responsibility** |
| :---: | :---: | :---: |
| Orchestrator | Python 3.12 + AsyncIO | Main loop, state management, scheduling, risk gate |
| Brain (Opus 4.6) | Anthropic API | Multi-dimensional analysis, signal generation, self-reflection |
| Research | Perplexity API (sonar-pro) | News research, macro analysis, sentiment gathering |
| Indicator Server | Python + pandas-ta | Price feeds, technical indicators, market regime detection |
| Trade Server | Python + python-okx SDK | Order execution, position management, trade confirmation |
| Database | PostgreSQL + TimescaleDB | Trade journal, playbook, performance metrics, candle storage |
| Message Queue | Redis Streams | Inter-component async communication |
| Monitoring | Grafana + Telegram Bot | Dashboard, alerting, human notification |

---

## 3. OKX Demo Trading Integration

OKX provides a full-featured Demo Trading environment that mirrors the production exchange. The system uses OKX API v5 with the demo flag (flag=1) to ensure zero financial risk during the learning phase.

### 3.1 API Configuration

**Demo Trading Setup**

OKX Demo Trading ให้ทุน virtual $100,000 USDT ฟรี รองรับ Spot, Margin, Futures, Options เหมือน production ทุกประการ

```python
# OKX API v5 Demo Trading Configuration
OKX_API_KEY      = "demo-api-key"
OKX_SECRET_KEY   = "demo-secret-key"
OKX_PASSPHRASE   = "demo-passphrase"
OKX_FLAG         = "1"              # 0=Production, 1=Demo

# REST API Base URLs
REST_BASE        = "[https://www.okx.com](https://www.okx.com)"
# Demo Trading uses same base URL, differentiated by flag

# WebSocket URLs
WS_PUBLIC        = "wss://[wspap.okx.com:8443/ws/v5/public](https://wspap.okx.com:8443/ws/v5/public)"
WS_PRIVATE       = "wss://[wspap.okx.com:8443/ws/v5/private](https://wspap.okx.com:8443/ws/v5/private)"
WS_BUSINESS      = "wss://[wspap.okx.com:8443/ws/v5/business](https://wspap.okx.com:8443/ws/v5/business)"

````

### 3.2 OKX API Endpoints Used

ระบบใช้ OKX API v5 endpoints ดังต่อไปนี้:

**Market Data (Public - No Auth Required)**

| **Method** | **Endpoint**                                          | **Purpose**                                   |
| :--------: | :---------------------------------------------------: | :-------------------------------------------: |
| GET        | /api/v5/market/candles                                | ดึงข้อมูล OHLCV candles (max 300 per request) |
| GET        | /api/v5/market/ticker                                 | ราคาปัจจุบัน, 24h volume, bid/ask             |
| GET        | /api/v5/market/books                                  | Order book depth (bids/asks)                  |
| GET        | /api/v5/market/trades                                 | Recent trades list                            |
| GET        | /api/v5/market/history-candles                        | Historical candles (older data)               |
| GET        | /api/v5/public/funding-rate                           | Current & predicted funding rate              |
| GET        | /api/v5/public/open-interest                          | Open interest data                            |
| GET        | /api/v5/rubik/stat/taker-volume                       | Taker buy/sell volume ratio                   |
| GET        | /api/v5/rubik/stat/contracts/long-short-account-ratio | Long/Short account ratio                      |

**Account & Position (Private - Auth Required)**

| **Method** | **Endpoint**                 | **Purpose**                                |
| :--------: | :--------------------------: | :----------------------------------------: |
| GET        | /api/v5/account/balance      | Account balance (equity, available margin) |
| GET        | /api/v5/account/positions    | Current open positions                     |
| POST       | /api/v5/account/set-leverage | Set leverage per instrument                |
| GET        | /api/v5/account/config       | Account configuration (mode, pos mode)     |

**Order Management (Private - Auth Required)**

| **Method** | **Endpoint**                 | **Purpose**             |
| :--------: | :--------------------------: | :---------------------: |
| POST       | /api/v5/trade/order          | Place single order      |
| POST       | /api/v5/trade/cancel-order   | Cancel pending order    |
| POST       | /api/v5/trade/amend-order    | Amend order price/size  |
| POST       | /api/v5/trade/close-position | Close position (market) |
| POST       | /api/v5/trade/order-algo     | Place TP/SL algo orders |
| GET        | /api/v5/trade/orders-pending | List pending orders     |
| GET        | /api/v5/trade/orders-history | Order history (7 days)  |
| GET        | /api/v5/trade/fills          | Trade fill details      |

**WebSocket Channels (Real-time Streaming)**

| **Type** | **Channel**        | **Purpose**                                       |
| :------: | :----------------: | :-----------------------------------------------: |
| Public   | `candle{period}`   | Real-time candle updates (`candle5m`, `candle1H`) |
| Public   | `tickers`          | Real-time ticker (last, bid, ask, vol)            |
| Public   | `books5` / `books` | Order book snapshots/updates                      |
| Public   | `funding-rate`     | Funding rate updates                              |
| Private  | `orders`           | Order status changes (filled, canceled)           |
| Private  | `positions`        | Position updates (PnL, liquidation price)         |
| Private  | `account`          | Account balance changes                           |

### 3.3 Authentication Flow

``` python
# OKX API v5 Authentication (HMAC-SHA256)
import hmac, hashlib, base64, datetime

def sign_request(timestamp, method, path, body, secret_key):
    message = f"{timestamp}{method}{path}{body}"
    mac = hmac.new(
        secret_key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    )
    return base64.b64encode(mac.digest()).decode()

# Headers for every private request:
headers = {
    'OK-ACCESS-KEY': api_key,
    'OK-ACCESS-SIGN': signature,
    'OK-ACCESS-TIMESTAMP': iso_timestamp,
    'OK-ACCESS-PASSPHRASE': passphrase,
    'x-simulated-trading': '1',  # Demo trading header
}

```

-----

## 4\. Component Detailed Design

### 4.1 Orchestrator (Main Controller)

Orchestrator เป็นหัวใจของระบบ ทำหน้าที่ควบคุม flow ทั้งหมด ใช้ Python AsyncIO เพื่อ handle concurrent tasks

**State Machine**

Orchestrator ทำงานเป็น state machine ที่วนรอบทุก `decision_cycle` (default 5 นาที):

States:

  * `IDLE` -\> รอ cycle ถัดไป
  * `COLLECTING` -\> กำลังรวบรวมข้อมูลจาก Indicator Server
  * `RESEARCHING` -\> (optional) กำลังเรียก Perplexity research
  * `ANALYZING` -\> ส่งข้อมูลให้ Opus วิเคราะห์
  * `RISK_CHECK` -\> ตรวจ risk rules (hardcoded)
  * `EXECUTING` -\> ส่งคำสั่งไป Trade Server
  * `CONFIRMING` -\> รอ order confirmation
  * `JOURNALING` -\> บันทึกลง Trade Journal DB
  * `REFLECTING` -\> (periodic) ทำ self-reflection cycle

**Core Loop Pseudocode**

``` python
async def main_loop():
    while running:
        # 1. Collect market data
        snapshot = await indicator_server.get_snapshot()
        positions = await trade_server.get_positions()
        account = await trade_server.get_account_balance()

        # 2. Check if research needed
        if should_research(snapshot):
            research = await perplexity.research(build_query(snapshot))
        else:
            research = None

        # 3. Load current playbook
        playbook = await db.get_latest_playbook()
        recent_trades = await db.get_recent_trades(limit=20)

        # 4. Build prompt & call Opus
        prompt = build_analysis_prompt(
            snapshot, positions, account,
            research, playbook, recent_trades
        )
        decision = await opus.analyze(prompt)

        # 5. Risk gate (HARDCODED - Opus cannot override)
        approved = risk_gate.validate(decision, account, positions)

        # 6. Execute if approved
        if approved:
            result = await trade_server.execute(decision)
            await db.record_trade(decision, result)

        # 7. Periodic reflection
        if should_reflect():
            await run_reflection_cycle()

        await asyncio.sleep(DECISION_CYCLE_SECONDS)

```

**Orchestrator Configuration**

| **Parameter**                | **Default**         | **Description**                            |
| :--------------------------: | :-----------------: | :----------------------------------------: |
| `DECISION_CYCLE_SECONDS`     | 300                 | Main loop interval (5 min)                 |
| `REFLECTION_INTERVAL_TRADES` | 20                  | Run reflection every N trades              |
| `REFLECTION_INTERVAL_HOURS`  | 6                   | Or every N hours (whichever first)         |
| `RESEARCH_BEFORE_NEWS`       | True                | Auto-research before scheduled news        |
| `MAX_OPUS_TIMEOUT_SECONDS`   | 30                  | Timeout for Opus API call                  |
| `INSTRUMENTS`                | \["BTC-USDT-SWAP"\] | Instruments to trade                       |
| `COOLDOWN_AFTER_LOSS_STREAK` | 1800                | 30 min cooldown after 3 consecutive losses |

### 4.2 Claude Opus 4.6 — The Brain

Opus ทำหน้าที่เป็นสมองหลัก 4 บทบาท: Decision Engine, Strategy Manager, Self-Reflection Engine, และ Risk Advisor

#### 4.2.1 Decision Engine — Analysis Prompt Structure

ทุก cycle Orchestrator จะสร้าง prompt ที่มีโครงสร้างชัดเจนส่งให้ Opus:

``` xml
<system>
You are an expert crypto derivatives trader operating on OKX.
Analyze the data provided and output a JSON decision.
Follow your playbook strictly. Be disciplined.
</system>

<market_snapshot>
  instrument: BTC-USDT-SWAP
  current_price: 98,450.2
  24h_change: +2.3%
  funding_rate: 0.0015 (positive = longs pay shorts)
  open_interest_change_24h: +5.2%
  long_short_ratio: 1.42
  taker_buy_sell_ratio: 0.87
</market_snapshot>

<technical_indicators timeframe="15m">
  RSI(14): 72.3 (overbought zone)
  MACD: line=125.3, signal=98.7, histogram=26.6 (bullish)
  Bollinger: upper=99100, mid=97800, lower=96500
  EMA(20): 97950, EMA(50): 96800, EMA(200): 94200
  ATR(14): 850.5
  Volume: 1.2x average
  Support levels: [97200, 96500, 95000]
  Resistance levels: [99000, 100000, 101500]
</technical_indicators>

<technical_indicators timeframe="1H">
  ... (same structure)
</technical_indicators>

<technical_indicators timeframe="4H">
  ... (same structure)
</technical_indicators>

<current_positions>
  BTC-USDT-SWAP: LONG 0.5 BTC @ 97200, unrealized_pnl: +$625
</current_positions>

<account_state>
  equity: $102,500, available_margin: $89,200
  daily_pnl: +$1,200, max_drawdown_today: -$300
</account_state>

<research_context>
  [Perplexity summary if available]
</research_context>

<playbook version="47">
  [Current playbook JSON]
</playbook>

<recent_trades count="10">
  [Last 10 trades with outcomes]
</recent_trades>

<output_format>
Respond ONLY with valid JSON:
{
  "analysis": {
    "market_regime": "trending_up|trending_down|ranging|volatile",
    "bias": "bullish|bearish|neutral",
    "key_observations": ["..."],
    "risk_factors": ["..."]
  },
  "decision": {

    "action": "OPEN_LONG|OPEN_SHORT|CLOSE|ADD|REDUCE|HOLD",
    "symbol": "BTC-USDT-SWAP",
    "size_pct": 0.02,
    "entry_price": null,
    "stop_loss": 96500,
    "take_profit": 101000,
    "order_type": "market|limit",
    "limit_price": null
  },
  "confidence": 0.75,
  "strategy_used": "momentum_breakout",
  "reasoning": "Detailed explanation..."
}
</output_format>

```

#### 4.2.2 Strategy Manager

Opus ทำหน้าที่จัดการ Playbook ซึ่งเป็น persistent memory ของระบบ โดย Playbook จะถูก serialize เป็น JSON เก็บใน database และถูกโหลดมาใส่ใน prompt ทุกครั้ง

**Playbook Schema**

``` json
{
  "version": 47,
  "last_updated": "2026-02-07T10:00:00Z",
  "market_regime_rules": {
    "trending_up": {
      "preferred_strategies": ["momentum_breakout", "pullback_entry"],
      "avoid_strategies": ["mean_reversion"],
      "max_position_pct": 0.05,
      "preferred_timeframe": "1H"
    },
    "trending_down": {
      "preferred_strategies": ["short_momentum", "breakdown"],
      "avoid_strategies": ["buy_dip"],
      "max_position_pct": 0.03,
      "preferred_timeframe": "1H"
    },
    "ranging": {
      "preferred_strategies": ["mean_reversion", "range_fade"],
      "avoid_strategies": ["momentum_breakout"],
      "max_position_pct": 0.02,
      "preferred_timeframe": "15m"
    },
    "volatile": {
      "preferred_strategies": ["wait", "reduced_size_scalp"],
      "avoid_strategies": ["any_large_position"],
      "max_position_pct": 0.01,
      "preferred_timeframe": "4H"
    }
  },
  "strategy_definitions": {
    "momentum_breakout": {
      "entry": "Price breaks above resistance with volume > 1.5x avg",
      "exit": "Trailing stop 1.5 ATR or target 2.5R",
      "filters": ["RSI < 80", "MACD histogram positive"],
      "historical_winrate": 0.62,
      "avg_rr": 1.8
    }
  },
  "lessons_learned": [
    {
      "id": "L001",
      "date": "2026-01-15",
      "lesson": "Do not trade momentum breakout during Asian session",
      "evidence": "Win rate 23% vs 67% in London/US session",
      "impact": "high"
    }
  ],
  "confidence_calibration": {
    "0.9+":   { "actual_winrate": 0.72, "adjustment": -0.12 },
    "0.7-0.9": { "actual_winrate": 0.65, "adjustment": -0.08 },
    "0.5-0.7": { "actual_winrate": 0.51, "adjustment": -0.02 }
  },
  "time_filters": {
    "avoid_hours_utc": [0, 1, 2, 3],
    "preferred_hours_utc": [8, 9, 13, 14, 15, 16]
  }
}

```

#### 4.2.3 Self-Reflection Engine (Core Learning Mechanism)

นี่คือหัวใจสำคัญที่สุดของระบบ ที่ทำให้ bot “ยิ่งเทรดยิ่งเก่ง” โดย Reflection Engine จะทำงาน 2 แบบ:

  * **Post-Trade Reflection:** หลังจบทุกเทรด Opus จะเขียน “self-review” สั้นๆ ว่าเทรดนี้ทำอะไรถูก ทำอะไรผิด
  * **Periodic Deep Reflection:** ทุก 20 เทรด หรือทุก 6 ชม. Opus จะทำการวิเคราะห์เชิงลึกและ update Playbook

**Post-Trade Reflection Prompt**

``` xml
<system>
You just completed a trade. Analyze it honestly.
</system>

<completed_trade>
  symbol: BTC-USDT-SWAP
  direction: LONG
  entry: 97,200 | exit: 98,100 | PnL: +$450
  duration: 2h 15m
  strategy_used: pullback_entry
  confidence_at_entry: 0.78
  market_regime_at_entry: trending_up
  stop_loss_was: 96,500 | take_profit_was: 99,000
  indicators_at_entry: [RSI=55, MACD=bullish, ...]
  indicators_at_exit: [RSI=71, MACD=weakening, ...]
</completed_trade>

<output_format>
{
  "outcome": "win|loss|breakeven",
  "execution_quality": "excellent|good|fair|poor",
  "entry_timing": "early|on_time|late",
  "exit_timing": "early|on_time|late|stopped_out",
  "what_went_right": ["..."],
  "what_went_wrong": ["..."],
  "lesson": "Concise lesson from this trade",
  "should_update_playbook": true|false,
  "playbook_suggestion": "If true, what to change"
}
</output_format>

```

**Periodic Deep Reflection Prompt**

``` xml
<system>
You are reviewing your last {N} trades for patterns.
Be brutally honest about your performance.
</system>

<performance_summary>
  period: last 20 trades (2026-02-01 to 2026-02-07)
  total_trades: 20
  wins: 12 | losses: 7 | breakeven: 1
  win_rate: 60%
  avg_win: +$380 | avg_loss: -$290
  profit_factor: 1.88
  max_consecutive_wins: 4 | max_consecutive_losses: 2
  sharpe_ratio_period: 1.42
  total_pnl: +$2,230
</performance_summary>

<breakdown_by_strategy>
  momentum_breakout: 8 trades, 62% win, avg RR 1.9
  pullback_entry: 7 trades, 57% win, avg RR 1.5
  mean_reversion: 5 trades, 60% win, avg RR 1.2
</breakdown_by_strategy>

<breakdown_by_regime>
  trending_up: 10 trades, 70% win
  ranging: 8 trades, 50% win
  volatile: 2 trades, 0% win
</breakdown_by_regime>

<breakdown_by_time>
  Asian (00-08 UTC): 4 trades, 25% win
  London (08-16 UTC): 10 trades, 80% win
  US (13-21 UTC): 6 trades, 67% win
</breakdown_by_time>

<confidence_calibration>
  Stated 0.8+: 6 trades, actual win 67% (overcalibrated)
  Stated 0.6-0.8: 10 trades, actual win 60% (good)
  Stated <0.6: 4 trades, actual win 50% (good)
</confidence_calibration>

<individual_trade_reviews>
  [All 20 post-trade reviews]
</individual_trade_reviews>

<current_playbook>
  [Current playbook JSON]
</current_playbook>

<tasks>
1. Identify recurring patterns of success and failure
2. Find systematic biases (overtrading, wrong timing, etc.)
3. Update confidence_calibration based on actual data
4. Propose specific playbook changes with evidence
5. Rate overall discipline (1-10)

Output updated playbook JSON with version incremented.
</tasks>

```

### 4.3 Perplexity Research Agent

Perplexity ทำหน้าที่เป็น Research Analyst ถูกเรียกใช้เฉพาะเมื่อจำเป็น ไม่ใช่ทุก cycle เพื่อประหยัด cost

**Trigger Conditions (เมื่อไหร่จะเรียก Perplexity)**

1.  Scheduled News Events: ก่อน FOMC, CPI, NFP, GDP releases 30 นาที
2.  Market Anomaly: เมื่อราคาเปลี่ยนแปลง \> 3% ใน 1 ชม. โดยไม่มี known catalyst
3.  Funding Rate Spike: เมื่อ funding rate \> 0.05% หรือ \< -0.03%
4.  Open Interest Anomaly: OI เปลี่ยน \> 10% ใน 4 ชม.
5.  Manual Trigger: Human operator สั่งผ่าน Telegram
6.  Pre-Trade Research: เมื่อ Opus request ข้อมูลเพิ่มก่อนตัดสินใจ

**Perplexity API Call Structure**

``` python
# Using Perplexity sonar-pro model
async def research(query: str) -> dict:
    response = await perplexity_client.chat.completions.create(
        model="sonar-pro",
        messages=[
            {"role": "system", "content": RESEARCH_SYSTEM_PROMPT},
            {"role": "user", "content": query}
        ],
        temperature=0.1,  # Low temp for factual accuracy
    )
    return parse_research_response(response)

RESEARCH_SYSTEM_PROMPT = """
You are a crypto market research analyst.
Provide concise, factual analysis. Include:
1. Key facts & data points
2. Market sentiment assessment (bullish/bearish/neutral)
3. Potential impact on BTC/ETH price (high/medium/low)
4. Time horizon of impact (immediate/short/medium term)
5. Sources cited
Respond in structured JSON format.
"""

```

**Research Output Schema**

``` json
{
  "query": "Impact of today's FOMC meeting on BTC",
  "summary": "Fed expected to hold rates...",
  "sentiment": "slightly_bearish",
  "impact_level": "high",
  "time_horizon": "immediate",
  "key_points": [
    "Market pricing in 85% chance of hold",
    "Dot plot may signal fewer cuts in 2026"
  ],
  "trading_implication": "Consider reducing long exposure before announcement",
  "confidence": 0.8,
  "sources": ["Reuters", "CME FedWatch"],
  "timestamp": "2026-02-07T14:00:00Z"
}

```

### 4.4 Indicator Server

Indicator Server ทำหน้าที่ดึงข้อมูลราคาจาก OKX, คำนวณ Technical Indicators, และตรวจจับ Market Regime

**Data Collection Pipeline**

``` python
class IndicatorServer:
    def __init__(self):
        self.ws_client = OKXWebSocket()
        self.candle_store = {}  # In-memory + DB backup
        self.indicators = {}

    async def get_snapshot(self, instrument) -> MarketSnapshot:
        return MarketSnapshot(
            ticker=self.get_latest_ticker(instrument),
            candles={
                '15m': self.get_candles(instrument, '15m', limit=100),
                '1H':  self.get_candles(instrument, '1H',  limit=100),
                '4H':  self.get_candles(instrument, '4H',  limit=100),
            },
            indicators={
                '15m': self.compute_indicators('15m'),
                '1H':  self.compute_indicators('1H'),
                '4H':  self.compute_indicators('4H'),
            },
            orderbook=self.get_orderbook(instrument, depth=20),
            funding_rate=self.get_funding_rate(instrument),
            open_interest=self.get_open_interest(instrument),
            long_short_ratio=self.get_ls_ratio(instrument),
            taker_volume=self.get_taker_volume(instrument),
            market_regime=self.detect_regime(instrument),
        )

```

**Technical Indicators Computed**

| **Indicator**      | **Parameters**   | **Purpose**                                  |
| :----------------: | :--------------: | :------------------------------------------: |
| RSI                | period=14        | Overbought/Oversold detection                |
| MACD               | 12, 26, 9        | Trend momentum & crossover signals           |
| Bollinger Bands    | 20, 2.0          | Volatility & mean reversion zones            |
| EMA                | 20, 50, 200      | Trend direction & dynamic support/resistance |
| ATR                | period=14        | Volatility for stop-loss sizing              |
| VWAP               | session          | Institutional fair value reference           |
| ADX                | period=14        | Trend strength (\>25 = trending)             |
| Stochastic RSI     | 14, 14, 3, 3     | Fine-grained momentum oscillator             |
| Volume Profile     | 24h bins         | High volume nodes = support/resistance       |
| OBV                | cumulative       | Volume-price divergence                      |
| Ichimoku Cloud     | 9, 26, 52        | Multi-factor trend + S/R system              |
| Support/Resistance | pivot + fractals | Key price levels from price action           |

**Market Regime Detection Algorithm**

``` python
def detect_regime(candles_4h) -> str:
    adx = compute_adx(candles_4h, 14)
    atr_ratio = current_atr / avg_atr_20  # volatility vs normal
    ema_slope = (ema20[-1] - ema20[-5]) / ema20[-5]
    
    if adx > 25 and ema_slope > 0.002:
        return 'trending_up'
    elif adx > 25 and ema_slope < -0.002:
        return 'trending_down'
    elif atr_ratio > 1.5:
        return 'volatile'
    else:
        return 'ranging'

```

### 4.5 Trade Server (OKX Execution Layer)

Trade Server รับคำสั่งจาก Orchestrator แล้ว execute บน OKX Demo Trading API ใช้ `python-okx SDK` เป็นหลัก

**Order Execution Flow**

``` python
class TradeServer:
    def __init__(self):
        self.trade_api = Trade.TradeAPI(
            api_key, secret_key, passphrase,
            False, flag='1'  # Demo trading
        )
        self.account_api = Account.AccountAPI(...)
    
    async def execute(self, decision: Decision) -> TradeResult:
        # 1. Validate order params
        validated = self.validate_order(decision)
        
        # 2. Place main order
        order_result = self.trade_api.place_order(
            instId=decision.symbol,
            tdMode='cross',
            side=decision.side,           # buy / sell
            posSide=decision.pos_side,     # long / short
            ordType=decision.order_type,   # market / limit
            sz=str(decision.size),
            px=str(decision.limit_price) if decision.limit_price else None,
        )
        
        # 3. Place TP/SL algo orders
        if decision.stop_loss:
            self.trade_api.place_algo_order(
                instId=decision.symbol,
                tdMode='cross',
                side='sell' if decision.side == 'buy' else 'buy',
                posSide=decision.pos_side,
                ordType='conditional',
                sz=str(decision.size),
                slTriggerPx=str(decision.stop_loss),
                slOrdPx='-1',  # Market price on trigger
                tpTriggerPx=str(decision.take_profit),
                tpOrdPx='-1',
            )
        
        # 4. Monitor fill via WebSocket orders channel
        fill = await self.wait_for_fill(order_result['ordId'])
        return TradeResult(order_result, fill)

```

**Position Management**

``` python
# Position monitoring runs continuously via WebSocket
async def monitor_positions():
    async for update in ws_private.subscribe('positions'):
        position = parse_position(update)
        
        # Update DB
        await db.update_position(position)
        
        # Check if position closed
        if position.pos == '0':
            await handle_position_closed(position)
        
        # Publish to Redis for Orchestrator
        await redis.publish('position_updates', position.to_json())

```

``` 
 
```
