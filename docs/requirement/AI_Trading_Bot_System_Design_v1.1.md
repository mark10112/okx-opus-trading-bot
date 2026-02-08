# System Design Update — v1.1 Patch Notes

> **Changes:** Two-Tier Model (Haiku Screener + Opus Decision), Corrected Pricing, Updated Architecture
> Applies to: `AI_Trading_Bot_System_Design.md` v1.0

---

## Summary of Changes

| Section | Change |
|---|---|
| 2.1 Architecture Diagram | เพิ่ม Haiku Screener layer |
| 2.2 Component Summary | เพิ่ม Screener component |
| 4.1 Orchestrator Core Loop | เปลี่ยน flow เป็น Two-Tier |
| **NEW** 4.6 Haiku Screener | Section ใหม่ทั้งหมด |
| 10 Cost Analysis | แก้ pricing เป็น Opus 4.6 ($5/$25) + Haiku layer |

---

## 2.1 Architecture Diagram (REPLACE)

```
┌─────────────────────────────────────────────────────────────────┐
│                  ORCHESTRATOR (Python AsyncIO)                   │
│        Main Loop · State Machine · Scheduling · Risk Gate       │
└──┬──────────┬──────────────┬──────────────┬──────────────┬──────┘
   │          │              │              │              │
┌──▼───┐ ┌───▼─────┐  ┌─────▼─────┐  ┌────▼──────┐  ┌───▼────────┐
│Haiku │ │ Opus 4.6│  │ Perplexity│  │ Indicator │  │   Trade    │
│Screen│─▶│ (Brain) │  │ (Research)│  │  Server   │  │   Server   │
└──────┘ └────┬────┘  └───────────┘  └────┬──────┘  └───┬────────┘
   80-90%     │                            │              │
   SKIP       │              ┌─────────────┴──────────────┘
              │              │
              │         ┌────▼──────────────────────┐
              │         │   OKX Demo Trading API    │
              │         │   (Paper Trade / flag=1)  │
              │         └───────────────────────────┘
              │
         ┌────▼─────────────────────────────────────────┐
         │   PostgreSQL + TimescaleDB                    │
         └───────────────────────────────────────────────┘
```

### Flow: Two-Tier Decision

```
Every Cycle (5 min)
       │
       ▼
  Haiku 4.5 Screener ──"มี setup ไหม?"
       │
       ├── NO (80-90%) ──► SKIP cycle, cost ~$0.0007
       │
       └── YES (10-20%)
             │
             ▼
       Opus 4.6 ──► Full Analysis + Decision JSON
```

---

## 2.2 Component Summary (ADD ROW)

เพิ่มแถวนี้ใน table:

| Component | Technology | Responsibility |
|---|---|---|
| **Screener (Haiku 4.5)** | Anthropic API (haiku) | Quick market screening, filter 80-90% of cycles before calling Opus |

---

## 4.1 Orchestrator Core Loop (REPLACE)

```python
async def main_loop():
    while running:
        # 1. Collect market data
        snapshot = await indicator_server.get_snapshot()
        positions = await trade_server.get_positions()
        account = await trade_server.get_account_balance()

        # 2. TWO-TIER SCREENING
        # Always call Opus if we have open positions or near news events
        needs_opus = (
            len(positions) > 0           # มี position ต้อง manage
            or is_news_window()          # ใกล้ข่าวสำคัญ (30 min before)
            or snapshot.anomaly_detected # market anomaly (>3% move)
        )

        if not needs_opus:
            # Let Haiku screen first — cheap & fast
            screen_result = await haiku_screener.screen(snapshot)
            needs_opus = screen_result.signal

            if not needs_opus:
                logger.debug(f"Haiku: no setup — {screen_result.reason}")
                await asyncio.sleep(DECISION_CYCLE_SECONDS)
                continue  # Skip this cycle entirely

        # 3. Check if research needed
        if should_research(snapshot):
            research = await perplexity.research(build_query(snapshot))
        else:
            research = None

        # 4. Load playbook & recent trades
        playbook = await db.get_latest_playbook()
        recent_trades = await db.get_recent_trades(limit=20)

        # 5. Call Opus for full analysis
        prompt = build_analysis_prompt(
            snapshot, positions, account,
            research, playbook, recent_trades
        )
        decision = await opus.analyze(prompt)

        # 6. Risk gate (HARDCODED)
        approved = risk_gate.validate(decision, account, positions)

        # 7. Execute if approved
        if approved and decision.action != 'HOLD':
            result = await trade_server.execute(decision)
            await db.record_trade(decision, result)

        # 8. Periodic reflection
        if should_reflect():
            await run_reflection_cycle()

        await asyncio.sleep(DECISION_CYCLE_SECONDS)
```

---

## 4.6 Haiku Screener (NEW SECTION)

> เพิ่มเป็น section 4.6 ต่อจาก 4.5 Trade Server

Haiku 4.5 ทำหน้าที่เป็น **pre-filter ราคาถูก** ก่อนเรียก Opus ทุกครั้ง ลด Opus calls ได้ 80-85%

### 4.6.1 Screener Prompt

```python
SCREENER_SYSTEM = """You are a quick crypto market screener.
Given a market snapshot, determine if there's an actionable trading setup RIGHT NOW.
Signal = true ONLY if:
- Clear breakout/breakdown with volume
- RSI extreme (<30 or >70) in ranging market
- Strong trend pullback to EMA support
- Significant divergence between indicators
Signal = false if market is choppy, unclear, or already priced in.
Respond ONLY with JSON. No explanation."""

async def screen(self, snapshot: MarketSnapshot) -> ScreenResult:
    prompt = f"""<snapshot>
symbol: {snapshot.ticker.symbol}
price: {snapshot.ticker.last}
24h_change: {snapshot.ticker.change_24h}%
RSI_15m: {snapshot.indicators['15m'].rsi}
RSI_1H: {snapshot.indicators['1H'].rsi}
MACD_15m: {snapshot.indicators['15m'].macd_signal}
MACD_1H: {snapshot.indicators['1H'].macd_signal}
regime: {snapshot.market_regime}
ADX: {snapshot.indicators['1H'].adx}
volume_vs_avg: {snapshot.ticker.volume_ratio}x
funding: {snapshot.funding_rate}
OI_change_4h: {snapshot.oi_change_4h}%
BB_position_15m: {snapshot.indicators['15m'].bb_position}
EMA_alignment: {snapshot.indicators['1H'].ema_alignment}
</snapshot>"""

    response = await self.client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=100,
        system=SCREENER_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.0,
    )

    result = json.loads(response.content[0].text)
    return ScreenResult(
        signal=result["signal"],
        reason=result.get("reason", ""),
        tokens_used=response.usage.input_tokens + response.usage.output_tokens,
    )
```

### 4.6.2 Screener Output Schema

```json
{
  "signal": true,
  "reason": "RSI divergence + volume spike at resistance, potential breakout"
}
```

- Input: ~500 tokens
- Output: ~30 tokens
- Cost per call: **$0.00065** (Haiku: $1/$5 per MTok)
- Latency: ~200-500ms

### 4.6.3 Bypass Conditions (Skip Haiku, Go Direct to Opus)

| Condition | Reason |
|---|---|
| Open position exists | ต้อง manage (HOLD/ADD/REDUCE/CLOSE) |
| News window (30 min before FOMC/CPI/NFP) | ต้องวิเคราะห์ impact |
| Market anomaly (>3% move in 1H) | ต้องประเมินสถานการณ์ |
| Funding rate spike (>0.05% or <-0.03%) | Market positioning extreme |
| Manual trigger via Telegram | Human สั่งวิเคราะห์ |

### 4.6.4 Screener Bias Tuning

Haiku ถูก tune ให้ bias ฝั่ง **pass-through** มากกว่า **reject**:

- **False negative (miss a good setup)** = เสียโอกาส → แย่กว่า
- **False positive (send to Opus unnecessarily)** = เสียแค่ ~$0.02 → ยอมได้

Target pass-through rate: **15-25%** (ไม่ต่ำกว่า 10%)

ถ้า pass-through rate ต่ำกว่า 10% ติดต่อกัน 24 ชั่วโมง → alert ผ่าน Telegram เพราะอาจมีปัญหากับ prompt

### 4.6.5 Monitoring Screener Accuracy

เพิ่ม table `screener_logs` ใน database:

```sql
CREATE TABLE screener_logs (
    id              SERIAL PRIMARY KEY,
    symbol          VARCHAR(30) NOT NULL,
    signal          BOOLEAN NOT NULL,
    reason          TEXT,
    snapshot_json   JSONB,
    -- Track if Opus agreed with Haiku's signal=true
    opus_action     VARCHAR(20),          -- NULL if signal=false
    opus_agreed     BOOLEAN,              -- Did Opus also find a setup?
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Monitor pass-through rate
-- SELECT date_trunc('day', created_at) as day,
--        COUNT(*) FILTER (WHERE signal) * 100.0 / COUNT(*) as pass_rate
-- FROM screener_logs GROUP BY 1;
```

ทุก periodic reflection ให้ Opus วิเคราะห์ screener accuracy ด้วย:
- Pass-through rate trend
- False positive rate (Haiku said yes, Opus said HOLD)
- Missed opportunities (market moved >1% after Haiku said no)

---

## 10. Cost Analysis (REPLACE)

### Pricing Reference (Opus 4.6 — Updated)

| Model | Input | Output |
|---|---|---|
| **Opus 4.6** | $5 / 1M tokens | $25 / 1M tokens |
| **Haiku 4.5** | $1 / 1M tokens | $5 / 1M tokens |
| Perplexity sonar-pro | $5 / 1000 requests | — |

> ⚠️ Opus 4.6 ราคาเท่ากับ Opus 4.5 คือ $5/$25 (ไม่ใช่ $15/$75 แบบ Opus 4.1 เดิม)

### Token Estimates per Call

| Call Type | Input Tokens | Output Tokens |
|---|---|---|
| Haiku Screener | 500 | 30 |
| Opus Decision | 3,000 | 500 |
| Opus Post-Trade Reflection | 2,000 | 400 |
| Opus Deep Reflection | 8,000 | 2,000 |

### Monthly Cost: 15-min Timeframe (Decision Cycle = 5 min)

| Item | Calls/Month | Cost Calculation | Monthly Cost |
|---|---|---|---|
| **Haiku Screener** | 8,640 | (4.32M × $1 + 0.26M × $5) / 1M | **$5.62** |
| **Opus Decision** (15% pass-through) | 1,296 | (3.89M × $5 + 0.65M × $25) / 1M | **$35.67** |
| **Opus Post-Trade Reflection** | ~400 | (0.8M × $5 + 0.16M × $25) / 1M | **$8.00** |
| **Opus Deep Reflection** | ~20 | (0.16M × $5 + 0.04M × $25) / 1M | **$1.80** |
| **Perplexity sonar-pro** | ~300 | 300 × $0.005 | **$1.50** |
| **VPS (8GB)** | 1 | — | **$48.00** |
| **OKX Demo Trading** | — | — | **$0.00** |
| | | **Total** | **~$101/mo** |

### Monthly Cost: 1H Timeframe (Decision Cycle = 15 min)

| Item | Calls/Month | Monthly Cost |
|---|---|---|
| Haiku Screener | 2,880 | $1.87 |
| Opus Decision (15%) | 432 | $11.89 |
| Opus Reflection (post-trade) | ~200 | $4.00 |
| Opus Reflection (deep) | ~10 | $0.90 |
| Perplexity | ~240 | $1.20 |
| VPS | 1 | $48.00 |
| **Total** | | **~$68/mo** |

### Cost Comparison Table

| Setup | 15m TF | 1H TF |
|---|---|---|
| ~~Opus Only (old $15/$75)~~ | ~~$790~~ | ~~$300~~ |
| Opus Only (correct $5/$25) | $250 | $85 |
| **Haiku Screener + Opus (recommended)** | **$101** | **$68** |
| Savings vs Opus-only | **-60%** | **-20%** |

### Sensitivity: Haiku Pass-Through Rate

| Pass-Through Rate | 15m Total/mo | 1H Total/mo |
|---|---|---|
| 5% (quiet market) | $75 | $58 |
| 10% | $87 | $62 |
| **15% (baseline)** | **$101** | **$68** |
| 20% | $115 | $74 |
| 30% (very active) | $142 | $86 |

### Additional Cost Optimization (Optional)

| Optimization | Savings | Trade-off |
|---|---|---|
| **Prompt Caching** (playbook + system prompt) | -40% on Opus input | ต้อง manage cache TTL |
| **Batch API** for deep reflection | -50% on reflection | ไม่ real-time (24hr turnaround) |
| **Increase cycle to 10 min** | -50% on Haiku calls | ช้าลงเล็กน้อยแต่ยังทัน 15m candle |
| All optimizations combined | **~$60-70/mo for 15m TF** | — |

---

## Configuration Updates

เพิ่มใน `.env`:

```bash
# ─── Haiku Screener ───
HAIKU_MODEL=claude-haiku-4-5-20251001
HAIKU_MAX_TOKENS=100
SCREENER_PASS_THROUGH_ALERT_MIN=0.10    # Alert if < 10%
SCREENER_BYPASS_ON_POSITION=true
SCREENER_BYPASS_ON_NEWS=true
SCREENER_BYPASS_ON_ANOMALY=true
```

เพิ่มใน Orchestrator configuration:

| Parameter | Default | Description |
|---|---|---|
| `SCREENER_ENABLED` | `true` | Enable/disable Haiku pre-filter |
| `SCREENER_BYPASS_ON_POSITION` | `true` | Skip screener if open position |
| `SCREENER_BYPASS_ON_NEWS` | `true` | Skip screener near news events |
| `SCREENER_MIN_PASS_RATE` | `0.10` | Alert if pass rate drops below 10% |
| `SCREENER_LOG_ALL` | `true` | Log all screener decisions to DB |

---

## Project Structure Updates

เพิ่มไฟล์ใน `orchestrator/`:

```
orchestrator/
├── ... (existing files)
├── haiku_screener.py          # NEW: Haiku screening logic
└── models/
    ├── ... (existing files)
    └── screen_result.py       # NEW: ScreenResult pydantic model
```

เพิ่ม migration:

```
migrations/versions/
├── ... (existing migrations)
└── 002_add_screener_logs.py   # NEW: screener_logs table
```