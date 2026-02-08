ฉันเข้าใจว่าคุณต้องการให้แสดงเนื้อหาบทที่ 10 ถึง 14 อีกครั้ง โดยเน้นย้ำให้แน่ใจว่าส่วนของโครงสร้างไดเร็กทอรี (Directory Structure) ในบทที่ 12 ถูกใส่เป็นโค้ดบล็อก (snippet) อย่างชัดเจน เนื้อหาฉบับปรับปรุงพร้อมโค้ดบล็อกในส่วนที่ 12 อยู่ด้านล่างนี้:

``` 
## 10. Cost Analysis

ประมาณค่าใช้จ่ายรายเดือนสำหรับ Paper Trading Phase:

| **Item** | **Unit Cost** | **Est. Usage/Month** | **Monthly Cost** |
| :---: | :---: | :---: | :---: |
| Claude Opus 4.6 API | $15/M input, $75/M output | ~8,640 calls | $150-300 |
| Perplexity sonar-pro | $5/1000 requests | ~300 calls | $1.50 |
| VPS (DigitalOcean) | $48/mo (8GB) | 1 server | $48 |
| OKX Demo Trading | Free | - | $0 |
| Domain + SSL | ~$1/mo | 1 | $1 |
| | | | **$200-350/mo** |

*หมายเหตุ: ค่า Opus API เป็นส่วนที่แพงที่สุด สามารถลดได้โดยการเพิ่ม Decision Cycle เป็น 15 นาที ซึ่งจะลดค่าใช้จ่ายลงประมาณ 60%*

---

## 11. Development Roadmap

โรดแมปการพัฒนาระบบแบ่งออกเป็น 5 เฟส:

### Phase 1: Foundation (Week 1-2)
*   Setup project structure, Docker Compose, database schema
*   Implement OKX API wrapper (REST + WebSocket) with Demo Trading flag
*   Build Indicator Server with core indicators (RSI, MACD, BB, EMA, ATR)
*   Implement Trade Server with basic order execution
*   Setup Redis Streams communication

### Phase 2: Brain Integration (Week 3-4)
*   Build Orchestrator main loop with state machine
*   Implement Opus prompt builder and response parser
*   Create initial Playbook (version 1)
*   Integrate Perplexity research agent
*   Implement Risk Gate with all hardcoded rules

### Phase 3: Self-Learning (Week 5-6)
*   Implement Trade Journal recording
*   Build Post-Trade Reflection system
*   Build Periodic Deep Reflection system
*   Implement Playbook versioning and evolution
*   Create confidence calibration pipeline

### Phase 4: Monitoring & Polish (Week 7-8)
*   Setup Grafana dashboards
*   Build Telegram bot with all commands
*   Implement comprehensive logging and error handling
*   Performance optimization and stress testing
*   Write operational runbook

### Phase 5: Paper Trading Validation (Month 3-5)
*   Run system on OKX Demo Trading for 2-3 เดือนขั้นต่ำ
*   Monitor and validate self-learning effectiveness
*   Track Playbook evolution (จำนวนเวอร์ชัน, คุณภาพของบทเรียน)
*   Achieve target metrics ก่อนพิจารณา Live Trading

**Paper Trading Go-Live Criteria**

| **Metric** | **Target** | **Measurement Period** |
| :---: | :---: | :---: |
| Win Rate | > 55% | Last 100 trades |
| Profit Factor | > 1.5 | Last 100 trades |
| Sharpe Ratio (annualized) | > 1.0 | Rolling 30 days |
| Max Drawdown | < 10% | Entire paper period |
| Playbook Versions | > 10 | Shows active learning |
| Confidence Calibration Error | < 10% | Stated vs actual win rate |
| System Uptime | > 99% | Last 30 days |

**สำคัญมาก: ห้าม go live จนกว่าจะผ่านทุก criteria ข้างบน ไม่ว่าผล paper trade จะดีแค่ไหนก็ตาม ควรมี human review ทุก milestone**

---

## 12. Project Directory Structure

```

ai-trading-bot/  
├── docker-compose.yml  
├── .env.example  
├── README.md  
├── orchestrator/  
│   ├── Dockerfile  
│   ├── main.py                  \# Entry point, main loop  
│   ├── state\_machine.py         \# State management  
│   ├── opus\_client.py           \# Anthropic API wrapper  
│   ├── prompt\_builder.py        \# Build analysis prompts  
│   ├── risk\_gate.py             \# Hardcoded risk rules  
│   ├── reflection\_engine.py     \# Self-learning orchestration  
│   ├── playbook\_manager.py      \# Playbook CRUD & versioning  
│   ├── config.py                \# Configuration management  
│   └── models/                  \# Pydantic data models  
│       ├── decision.py  
│       ├── trade.py  
│       └── snapshot.py  
├── indicator-server/  
│   ├── Dockerfile  
│   ├── main.py                  \# WebSocket listener + REST poller  
│   ├── indicators.py            \# Technical indicator calculations  
│   ├── regime\_detector.py       \# Market regime classification  
│   ├── candle\_store.py          \# In-memory + DB candle storage  
│   └── okx\_ws\_client.py         \# OKX WebSocket wrapper  
├── trade-server/  
│   ├── Dockerfile  
│   ├── main.py                  \# Order execution engine  
│   ├── okx\_rest\_client.py       \# OKX REST API wrapper  
│   ├── okx\_ws\_private.py        \# Private WebSocket (orders, positions)  
│   ├── position\_manager.py      \# Position tracking  
│   └── order\_validator.py       \# Pre-execution validation  
├── perplexity-agent/  
│   ├── Dockerfile  
│   ├── main.py                  \# Research request handler  
│   ├── perplexity\_client.py     \# Perplexity API wrapper  
│   ├── news\_scheduler.py        \# Economic calendar integration  
│   └── cache.py                 \# Research result caching  
├── telegram-bot/  
│   ├── Dockerfile  
│   ├── main.py                  \# Bot handler  
│   ├── commands.py              \# Command implementations  
│   └── formatters.py            \# Message formatting  
├── shared/  
│   ├── database.py              \# SQLAlchemy models & connection  
│   ├── redis\_client.py          \# Redis Streams wrapper  
│   ├── schemas.py               \# Shared Pydantic schemas  
│   └── logger.py                \# Structured logging setup  
├── migrations/  
│   └── ...                      \# Alembic migrations  
├── grafana/  
│   ├── dashboards/              \# Pre-configured dashboards  
│   └── datasources/             \# PostgreSQL & Redis configs  
└── tests/  
├── test\_risk\_gate.py  
├── test\_indicators.py  
├── test\_prompt\_builder.py  
└── test\_trade\_server.py

``` 

---

## 13. Key Risks & Mitigations

| **Risk** | **Severity** | **Likelihood** | **Mitigation** |
| :---: | :---: | :---: | :---: |
| Opus Hallucination | HIGH | Medium | Hardcoded risk gate + confidence calibration + structured JSON output |
| API Latency (2-10s) | MEDIUM | High | ใช้ 15m+ timeframe, async execution, timeout handling |
| API Rate Limits | MEDIUM | Medium | Request queuing, exponential backoff, batch endpoints |
| OKX API Downtime | MEDIUM | Low | Health checks, auto-close on disconnect, alerting |
| Overfitting Playbook | HIGH | Medium | Minimum sample size for changes (>20 trades), decay old lessons |
| Runaway Losses | HIGH | Low | Multiple circuit breakers, mandatory SL, human override via Telegram |
| Cost Overrun (API) | LOW | Medium | Cost tracking ใน Grafana, daily budget limit, ใช้ Haiku สำหรับงานง่าย |
| No True Memory | MEDIUM | Certain | Playbook + Journal ถูก serialize ใน prompt ทุก cycle, version control |
| Prompt Injection | LOW | Low | All inputs sanitized, no user-facing prompts, structured output only |

---

## 14. Summary

ระบบนี้ออกแบบมาให้เป็น AI Trading Bot ที่สามารถเรียนรู้และพัฒนาตัวเองได้ โดยมีจุดเด่นคือ:

1.  **Multi-dimensional Analysis:** Claude Opus 4.6 วิเคราะห์ Technical + Fundamental + Sentiment + Market Microstructure พร้อมกัน ซึ่งบอทแบบดั้งเดิมทำไม่ได้
2.  **Self-Learning Loop:** การทบทวนหลังการเทรด (Post-trade reflection) และการวิเคราะห์เชิงลึกเป็นระยะ (Periodic deep analysis) พร้อมกับการพัฒนา Playbook ทำให้ระบบ "ยิ่งเทรดยิ่งเก่ง"
3.  **Defense in Depth:** กฎการจัดการความเสี่ยงแบบ Hardcoded + Soft rules + Human override ป้องกันความสูญเสียครั้งใหญ่
4.  **Zero Financial Risk:** ใช้ OKX Demo Trading ทั้งหมด ซึ่งมีเงิน virtual $100K ให้ทดสอบฟรี
5.  **Observable System:** Grafana + Telegram ช่วยให้มนุษย์สามารถตรวจสอบและติดตามได้ตลอดเวลา

**สิ่งสำคัญที่สุดคือ อย่ารีบ go live ควร paper trade อย่างน้อย 2-3 เดือน วิเคราะห์ผลอย่างละเอียด และให้ Playbook ผ่านการ evolve อย่างน้อย 10+ versions ก่อนพิจารณาใช้เงินจริง** 
```
