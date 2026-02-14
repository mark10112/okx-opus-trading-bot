# 04 — SignalGate: Indicator-Side Pre-Filter

## 1. Overview

SignalGate เป็น rule-based filter ที่ทำงานฝั่ง **indicator-trade-server** ทำหน้าที่ตัดสินใจว่า snapshot แต่ละรอบ **ควรส่งไป Orchestrator (LLM) หรือไม่** โดยใช้ rules ที่ LLM กำหนดไว้ใน Playbook

### ปัญหาที่แก้

ปัจจุบันระบบส่ง snapshot ไป Orchestrator **ทุก 5 นาที (288 cycles/day)** แม้ว่าส่วนใหญ่ LLM จะตอบ HOLD กลับมา ทำให้เสีย API cost โดยไม่จำเป็น

### แนวคิด

```
ก่อน:
  Snapshot → [ส่งทุก cycle] → Orchestrator → Haiku Screen → Opus Analyze → Trade

หลัง:
  Snapshot → SignalGate (rule-based) → PASS       → Orchestrator → LLM → Trade
                                     → BLOCK      → skip (ประหยัด 100%)
                                     → BORDERLINE → ส่งไป LLM ตัดสิน
                                     → FALLBACK   → ส่งทุก 30 นาที ไม่ว่า rules จะว่าอะไร
```

---

## 2. Architecture

```
┌──────────────────────────────────────────────────────────┐
│                  indicator-trade-server                    │
│                                                           │
│  SnapshotBuilder ──► SignalGate ──► Redis market:snapshots │
│                        │                                   │
│                        ├── evaluate(snapshot, rules)        │
│                        ├── _check_always_send()             │
│                        ├── _check_regime_rules()            │
│                        ├── _check_fallback_timer()          │
│                        ├── _compute_confidence()            │
│                        └── _track_metrics()                 │
│                                                           │
│  Redis config:signal_rules ◄── (read on change)           │
└──────────────────────────────────────────────────────────┘
                           ▲
                           │ publish rules
┌──────────────────────────────────────────────────────────┐
│                     orchestrator                          │
│                                                           │
│  PlaybookManager ──► SignalRuleExporter ──► Redis          │
│                                                           │
│  ReflectionEngine ──► self-tune rules ──► PlaybookManager  │
└──────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Orchestrator** อ่าน Playbook → แปลงเป็น SignalRules → publish ไป Redis `config:signal_rules`
2. **Indicator server** อ่าน `config:signal_rules` จาก Redis → เก็บใน memory
3. **ทุก snapshot cycle** → `SignalGate.evaluate(snapshot, rules)` → return GateDecision
4. ถ้า PASS / BORDERLINE / FALLBACK → publish snapshot ไป `market:snapshots`
5. ถ้า BLOCK → skip, เก็บ metrics
6. **ทุก deep reflection** → LLM วิเคราะห์ gate metrics → ปรับ rules → publish ใหม่

---

## 3. Models

### SignalRules (Orchestrator → Indicator Server via Redis)

| Field | Type | Default | คำอธิบาย |
|-------|------|---------|----------|
| `version` | int | 1 | Version ของ rules (sync กับ playbook version) |
| `regime_rules` | dict[str, RegimeSignalRule] | {} | Rules แยกตาม market regime |
| `always_send` | AlwaysSendRule | (see below) | เงื่อนไขที่ส่งเสมอ |
| `fallback_interval_seconds` | int | 1800 | ส่ง LLM ทุก N วินาที ไม่ว่า rules จะว่าอะไร |
| `borderline_threshold` | float | 0.6 | confidence ต่ำกว่านี้ = borderline → ส่งไป LLM |
| `updated_by` | str | "default" | ใครเป็นคน update ("default" / "deep_reflection" / "manual") |

### RegimeSignalRule (per-regime)

| Field | Type | Default | คำอธิบาย |
|-------|------|---------|----------|
| `rsi_min` | float? | None | RSI ต่ำสุดที่ trigger (None = ไม่ check) |
| `rsi_max` | float? | None | RSI สูงสุดที่ trigger |
| `adx_min` | float? | None | ADX ขั้นต่ำ |
| `adx_max` | float? | None | ADX ขั้นสูง |
| `ema_alignment` | list[str] | [] | เช่น ["bullish", "bearish"] |
| `macd_signal` | list[str] | [] | เช่น ["bullish", "bearish"] |
| `bb_position` | list[str] | [] | เช่น ["above", "below"] |
| `volume_ratio_min` | float? | None | volume vs 20-period avg |
| `atr_ratio_min` | float? | None | ATR vs 20-period avg |

### AlwaysSendRule (bypass ทุก regime)

| Field | Type | Default | คำอธิบาย |
|-------|------|---------|----------|
| `price_change_1h_abs_min` | float | 0.03 | >3% price change → ส่งเสมอ |
| `funding_rate_abs_min` | float | 0.0005 | >0.05% funding → ส่งเสมอ |
| `oi_change_4h_abs_min` | float | 0.10 | >10% OI change → ส่งเสมอ |

### GateDecision (ผลลัพธ์)

| Field | Type | คำอธิบาย |
|-------|------|----------|
| `action` | str | "PASS" / "BLOCK" / "BORDERLINE" / "FALLBACK" |
| `confidence` | float | 0.0–1.0 ความมั่นใจว่าควรส่ง |
| `matched_rules` | list[str] | rules ที่ match เช่น ["rsi_extreme", "always_send:price_change"] |
| `reason` | str | คำอธิบายสั้นๆ |

---

## 4. Evaluation Logic

### ลำดับการ evaluate

```
evaluate(snapshot, rules):
  1. always_send check
     - price_change_1h > threshold    → PASS (confidence=1.0)
     - funding_rate > threshold       → PASS (confidence=1.0)
     - oi_change_4h > threshold       → PASS (confidence=1.0)

  2. fallback timer check
     - เวลาตั้งแต่ส่งครั้งล่าสุด > fallback_interval → FALLBACK (confidence=0.5)

  3. regime-specific rules
     - ดู market_regime ปัจจุบัน (trending_up/down, volatile, ranging)
     - match indicators กับ regime_rules[regime]
     - คำนวณ confidence จากจำนวน rules ที่ match

  4. confidence evaluation
     - confidence >= borderline_threshold → PASS
     - confidence > 0 but < threshold    → BORDERLINE (ส่งไป LLM ตัดสิน)
     - confidence == 0                   → BLOCK

  5. track metrics
     - เก็บ passed/blocked/borderline/fallback counts
```

### Confidence Calculation

```
confidence = (จำนวน rules ที่ match) / (จำนวน rules ทั้งหมดใน regime)

ตัวอย่าง regime "trending_up" มี 5 rules:
  - rsi_range: [35, 70]     → RSI = 45  ✓ match
  - adx_min: 25             → ADX = 30  ✓ match
  - ema_alignment: bullish  → bullish   ✓ match
  - macd_signal: bullish    → neutral   ✗ no match
  - volume_ratio_min: 0.8   → 1.2      ✓ match

  confidence = 4/5 = 0.8 → PASS (> 0.6 threshold)
```

---

## 5. Default Signal Rules

Rules เริ่มต้นที่ map กับ default playbook v1:

### trending_up
- RSI: 35–70 (pullback zone, ไม่ overbought)
- ADX: > 25 (trend strength)
- EMA alignment: bullish
- MACD signal: bullish
- Volume ratio: > 0.8

### trending_down
- RSI: 30–65 (pullback zone, ไม่ oversold)
- ADX: > 25
- EMA alignment: bearish
- MACD signal: bearish
- Volume ratio: > 0.8

### ranging
- RSI: < 30 หรือ > 70 (extreme only)
- ADX: < 25
- BB position: above หรือ below (touch band)

### volatile
- ATR ratio: > 1.5
- Volume ratio: > 1.5

### always_send (ทุก regime)
- Price change 1H: > 3%
- Funding rate: > 0.05%
- OI change 4H: > 10%

---

## 6. LLM Self-Tune Mechanism

### เมื่อไหร่ที่ tune

ทุกครั้งที่ ReflectionEngine ทำ **deep reflection** (ทุก 20 trades หรือ 6 ชม.)

### ข้อมูลที่ LLM ได้รับ

- Gate metrics: passed/blocked/borderline/fallback counts ตั้งแต่ tune ครั้งก่อน
- Trade results: trades ที่เกิดขึ้นหลัง gate pass → win/loss
- Missed signals estimate: จำนวน BLOCK ที่ตามมาด้วย price move > 2% (อาจเป็น missed opportunity)

### สิ่งที่ LLM ปรับได้

- ปรับ threshold ของแต่ละ rule (เช่น RSI range กว้าง/แคบขึ้น)
- เพิ่ม/ลด rules ในแต่ละ regime
- ปรับ borderline_threshold (เข้ม/หลวมขึ้น)
- ปรับ fallback_interval_seconds

### สิ่งที่ LLM ปรับไม่ได้ (hardcoded safety)

- always_send rules ห้ามปิด (ป้องกัน miss black swan)
- fallback_interval_seconds ต่ำสุด 900 วินาที (15 นาที)
- fallback_interval_seconds สูงสุด 3600 วินาที (1 ชม.)

---

## 7. Redis Protocol

### Stream: `config:signal_rules`

Orchestrator publish เมื่อ:
- Bot startup (publish default rules)
- Playbook version เปลี่ยน
- Deep reflection tune rules

Payload:
```json
{
  "source": "orchestrator",
  "type": "SignalRulesMessage",
  "payload": {
    "version": 2,
    "regime_rules": { ... },
    "always_send": { ... },
    "fallback_interval_seconds": 1800,
    "borderline_threshold": 0.6,
    "updated_by": "deep_reflection"
  }
}
```

### Stream: `signal_gate:metrics`

Indicator server publish ทุก 30 นาที (หรือทุก fallback cycle):

```json
{
  "source": "indicator_trade",
  "type": "SignalGateMetrics",
  "payload": {
    "period_seconds": 1800,
    "total_evaluations": 6,
    "passed": 1,
    "blocked": 3,
    "borderline": 1,
    "fallback": 1,
    "rules_version": 2
  }
}
```

---

## 8. Metrics & Monitoring

### Gate Metrics (in-memory, publish ทุก fallback cycle)

| Metric | คำอธิบาย |
|--------|----------|
| `total_evaluations` | จำนวน snapshot ที่ evaluate ทั้งหมด |
| `passed` | จำนวนที่ PASS (match rules ชัดเจน) |
| `blocked` | จำนวนที่ BLOCK (ไม่ match) |
| `borderline` | จำนวนที่ BORDERLINE (ไม่แน่ใจ → ส่ง LLM) |
| `fallback` | จำนวนที่ FALLBACK (timer expired) |
| `avg_confidence` | ค่าเฉลี่ย confidence ของทุก evaluation |

### Grafana Dashboard (เพิ่มใน system_health)

- **Gate Pass Rate** — % ของ snapshot ที่ผ่าน gate
- **Gate Decision Distribution** — pie chart: PASS/BLOCK/BORDERLINE/FALLBACK
- **Rules Version** — current version ของ signal rules

---

## 9. Cost Impact

### ก่อน SignalGate

| Component | Calls/day | Cost/day (Haiku) | Cost/day (Opus) |
|-----------|-----------|-------------------|-----------------|
| Haiku Screener | 288 | $0.05 | $0.05 |
| Opus/Haiku Analysis | ~100 | $0.05 | $4.88 |
| Perplexity | ~20 | $0.10 | $0.10 |
| Reflection | ~5 | $0.01 | $0.45 |
| **Total** | **~413** | **$0.21** | **$5.48** |

### หลัง SignalGate

| Component | Calls/day | Cost/day (Haiku) | Cost/day (Opus) |
|-----------|-----------|-------------------|-----------------|
| Haiku Screener | ~60 | $0.01 | $0.01 |
| Opus/Haiku Analysis | ~25 | $0.01 | $1.22 |
| Perplexity | ~10 | $0.05 | $0.05 |
| Reflection | ~5 | $0.01 | $0.45 |
| **Total** | **~100** | **$0.08** | **$1.73** |

### สรุป

| Mode | Before | After | Savings |
|------|--------|-------|---------|
| **Haiku (demo)** | $0.21/day ($6.3/mo) | $0.08/day ($2.4/mo) | **-62%** |
| **Opus (production)** | $5.48/day ($164/mo) | $1.73/day ($52/mo) | **-68%** |

---

## 10. Trade-offs & Risks

| ความเสี่ยง | ระดับ | Mitigation |
|-----------|-------|------------|
| พลาด setup ที่ดี (subtle multi-factor) | 🟡 ปานกลาง | Fallback timer ทุก 30 นาที ส่ง snapshot ไป LLM เสมอ |
| Rules ล้าสมัย (ตลาดเปลี่ยน regime) | 🟡 ปานกลาง | LLM self-tune ทุก deep reflection + metrics tracking |
| Over-filtering (rules เข้มเกิน) | 🟡 ปานกลาง | Borderline threshold + fallback ป้องกัน bot หยุด trade |
| Under-filtering (rules หลวมเกิน) | 🟢 ต่ำ | แค่กลับไปเหมือนเดิม (ส่งทุก cycle) ไม่เสียหาย |
| Early black swan miss | 🟢 ต่ำ | always_send rules (price >3%, funding >0.05%) ห้ามปิด |

---

## 11. Implementation Plan

### Files ที่ต้องสร้าง/แก้ไข

**indicator-trade-server:**
- `src/indicator_trade/models/signal_rules.py` — SignalRules, RegimeSignalRule, AlwaysSendRule, GateDecision models
- `src/indicator_trade/indicator/signal_gate.py` — SignalGate class
- `tests/unit/test_signal_gate.py` — unit tests

**orchestrator:**
- `src/orchestrator/signal_rule_exporter.py` — แปลง Playbook → SignalRules → publish Redis
- `src/orchestrator/models/messages.py` — เพิ่ม SignalRulesMessage, SignalGateMetrics
- แก้ `reflection_engine.py` — เพิ่ม self-tune logic
- แก้ `state_machine.py` — เพิ่ม publish rules on startup + read gate metrics
- `tests/unit/test_signal_rule_exporter.py` — unit tests

### TDD Order

1. test_signal_gate.py (RED) → signal_gate.py (GREEN) → refactor
2. test_signal_rule_exporter.py (RED) → signal_rule_exporter.py (GREEN) → refactor
3. Integration: แก้ server.py + state_machine.py + reflection_engine.py
4. Full test suite → merge
