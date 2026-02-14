---
trigger: always_on
---

# Git Workflow — OKX Opus Trading Bot

โปรเจกต์นี้เป็น monorepo ที่มี 3 sub-repos (`indicator-trade-server/`, `orchestrator/`, `ui/`) สื่อสารผ่าน Redis Streams + PostgreSQL ใช้ Git workflow ตามนี้เสมอ

---

## 1. Branch Strategy

```
main          ← stable, deploy-ready, ผ่าน test ทั้งหมด, ห้าม push ตรง
  └── dev     ← integration branch, รวม feature ก่อน merge เข้า main
       ├── feat/<phase>-<description>     ← feature branch
       ├── fix/<description>              ← bugfix branch
       └── refactor/<description>         ← refactor branch
```

### Branch Naming

| Type | Format | ตัวอย่าง |
|------|--------|----------|
| Feature | `feat/p<N>-<short-desc>` | `feat/p1-candle-store`, `feat/p2-order-executor`, `feat/p4-haiku-screener` |
| Cross-phase | `feat/<scope>-<desc>` | `feat/redis-stream-protocol`, `feat/infra-docker-compose` |
| Bugfix | `fix/<desc>` | `fix/ws-reconnect-loop`, `fix/risk-gate-threshold` |
| Refactor | `refactor/<desc>` | `refactor/indicator-pipeline` |
| Docs | `docs/<desc>` | `docs/api-runbook` |
| CI/Infra | `chore/<desc>` | `chore/github-actions`, `chore/doppler-setup` |

### Phase ↔ Branch Mapping

แต่ละ Phase จาก implementation plan ควรแตก feature branch ย่อยตาม sub-task:

| Phase | ตัวอย่าง branches |
|-------|-------------------|
| **P0** Infrastructure | `feat/p0-docker-compose`, `feat/p0-repo-scaffold`, `feat/p0-message-protocol`, `feat/p0-redis-client`, `feat/p0-db-schema` |
| **P1** Indicator Server | `feat/p1-pydantic-models`, `feat/p1-candle-store`, `feat/p1-candle-repo`, `feat/p1-indicators`, `feat/p1-regime-detector`, `feat/p1-snapshot-builder`, `feat/p1-ws-public`, `feat/p1-indicator-main` |
| **P2** Trade Server | `feat/p2-okx-rest`, `feat/p2-order-models`, `feat/p2-order-validator`, `feat/p2-order-executor`, `feat/p2-ws-private`, `feat/p2-position-manager`, `feat/p2-trade-main` |
| **P3** Orchestrator Core | `feat/p3-orm-models`, `feat/p3-repositories`, `feat/p3-risk-gate`, `feat/p3-playbook-manager`, `feat/p3-news-scheduler`, `feat/p3-state-machine` |
| **P4** AI Integration | `feat/p4-haiku-screener`, `feat/p4-prompt-builder`, `feat/p4-opus-client`, `feat/p4-perplexity-client`, `feat/p4-reflection-engine`, `feat/p4-state-machine-full` |
| **P5** Telegram Bot | `feat/p5-db-queries`, `feat/p5-formatters`, `feat/p5-commands`, `feat/p5-alerts`, `feat/p5-bot-app` |
| **P6** Grafana | `feat/p6-datasource`, `feat/p6-dashboards` |
| **P7** Integration Test | `feat/p7-e2e-tests` |
| **P8** Polish | `feat/p8-connection-pooling`, `feat/p8-graceful-shutdown`, `feat/p8-default-playbook` |

---

## 2. Commit Convention

ใช้ [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]
```

### Types

| Type | ใช้เมื่อ |
|------|---------|
| `feat` | เพิ่ม feature ใหม่ |
| `fix` | แก้ bug |
| `test` | เพิ่ม/แก้ test (ไม่แก้ production code) |
| `refactor` | ปรับ code โดยไม่เปลี่ยน behavior |
| `docs` | แก้ documentation |
| `chore` | งาน maintenance (deps, config, CI) |
| `ci` | CI/CD pipeline changes |

### Scopes

| Scope | ครอบคลุม |
|-------|---------|
| `indicator` | indicator-trade-server/src/indicator_trade/indicator/ |
| `trade` | indicator-trade-server/src/indicator_trade/trade/ |
| `orchestrator` | orchestrator/src/orchestrator/ |
| `ui` | ui/src/ui/ |
| `infra` | docker-compose.yml, Dockerfiles, CI configs |
| `db` | alembic migrations, DB models, repositories |
| `redis` | Redis client, stream protocol, messages |
| `grafana` | ui/grafana/ dashboards & provisioning |

### ตัวอย่าง Commits

```bash
# Phase 0
chore(infra): add docker-compose with postgres, redis, grafana
feat(redis): implement shared RedisClient with consumer groups
feat(db): add initial alembic migration with all tables

# Phase 1
test(indicator): add candle store unit tests
feat(indicator): implement candle store with in-memory deque
feat(indicator): add pandas-ta indicator computation
test(indicator): add regime detector boundary tests
feat(indicator): implement regime detector

# Phase 2
test(trade): add order validator tests for all edge cases
feat(trade): implement order validator with pre-execution checks
feat(trade): implement order executor with OKX REST wrapper

# Phase 3
test(orchestrator): add risk gate boundary value tests for all 11 rules
feat(orchestrator): implement risk gate with circuit breakers
feat(db): add ORM models and repositories

# Phase 4
feat(orchestrator): implement haiku screener with bypass conditions
feat(orchestrator): implement opus client with timeout handling
feat(orchestrator): complete state machine with full decision cycle

# Phase 5
feat(ui): implement telegram command handlers
feat(ui): implement alert sender with cooldown and severity routing

# Phase 6
feat(grafana): add 7 dashboard JSON files with provisioning
```

---

## 3. Commit Discipline

1. **Commit บ่อย** — ทุก Red-Green-Refactor cycle ควร commit อย่างน้อย 1 ครั้ง
2. **Commit ที่ test ผ่าน** — ทุก commit บน `dev` และ `main` ต้อง test ผ่านทั้งหมด
3. **Atomic commits** — แต่ละ commit ทำเรื่องเดียว ไม่ปนกัน ไม่ปน scope
4. **ห้าม commit ไฟล์ที่ไม่เกี่ยว** — ใช้ `git add` เฉพาะไฟล์ที่เกี่ยวข้อง
5. **ห้าม commit secrets** — API keys, passwords ต้องอยู่ใน Doppler เท่านั้น

---

## 4. Branch Lifecycle

### สร้าง Feature Branch

```bash
git checkout dev
git pull origin dev
git checkout -b feat/p<N>-<description>
```

### ทำงานบน Feature Branch (TDD cycle)

```bash
# RED: เขียน test ที่ fail
git add tests/
git commit -m "test(<scope>): add <description> tests"

# GREEN: implement ให้ test ผ่าน
git add src/
git commit -m "feat(<scope>): implement <description>"

# REFACTOR: ปรับปรุง code
git add .
git commit -m "refactor(<scope>): <description>"
```

### Merge เข้า dev

```bash
# อัพเดท dev ก่อน merge
git checkout dev
git pull origin dev
git checkout feat/p<N>-<description>
git rebase dev                          # rebase ให้ history สะอาด

# รัน full test suite ก่อน merge
cd <affected-repo>/ && python -m pytest tests/ -v

# merge เข้า dev
git checkout dev
git merge --no-ff feat/p<N>-<description>
git push origin dev

# ลบ feature branch
git branch -d feat/p<N>-<description>
git push origin --delete feat/p<N>-<description>
```

### Merge dev เข้า main (Phase milestone)

```bash
# ทำเมื่อจบ Phase หรือ feature set ที่ stable
git checkout main
git pull origin main
git merge --no-ff dev
git tag -a v0.<phase>.0 -m "Phase <N>: <description>"
git push origin main --tags
```

---

## 5. Tag & Version Strategy

ใช้ semantic versioning ตาม Phase milestone:

| Tag | เมื่อไหร่ |
|-----|----------|
| `v0.0.x` | Phase 0 — Infrastructure & scaffolding |
| `v0.1.x` | Phase 1 — Indicator server complete |
| `v0.2.x` | Phase 2 — Trade server complete |
| `v0.3.x` | Phase 3 — Orchestrator core complete |
| `v0.4.x` | Phase 4 — AI integration complete |
| `v0.5.x` | Phase 5 — Telegram bot complete |
| `v0.6.x` | Phase 6 — Grafana dashboards complete |
| `v0.7.x` | Phase 7 — Integration testing pass |
| `v1.0.0` | Phase 8 — Production ready |

Patch version (`x`) เพิ่มเมื่อ fix bug หลัง phase merge

---

## 6. Parallel Development Rules

Phase 5 (Telegram) และ Phase 6 (Grafana) สามารถทำ **parallel** กับ Phase 3-4 ได้:

```
dev ─────────────────────────────────────────────────►
 ├── feat/p3-*  ──► merge ──► feat/p4-* ──► merge
 ├── feat/p5-*  ──────────────────────────► merge    (parallel)
 └── feat/p6-*  ──────────────────────────► merge    (parallel)
```

**กฎ:**
- P5/P6 branch จาก `dev` หลัง P0 merge เสร็จ (ต้องมี shared protocol + DB schema)
- ถ้า P5/P6 ต้องใช้ code จาก P3/P4 ให้ rebase จาก `dev` เป็นระยะ
- Merge P5/P6 เข้า `dev` หลัง P4 merge แล้ว เพื่อหลีกเลี่ยง conflict

---

## 7. Conflict Resolution

1. **Rebase ก่อน merge เสมอ** — `git rebase dev` บน feature branch
2. **ถ้า conflict ใน shared files** (messages.py, redis_client.py) — ให้ทั้งสอง branch ตกลงกันก่อน
3. **ห้าม force push บน `dev` หรือ `main`** — force push ได้เฉพาะ feature branch ของตัวเอง
4. **ถ้า rebase ซับซ้อน** — ใช้ `git rebase --abort` แล้วใช้ merge แทน

---

## 8. คำสั่ง Git ที่ใช้บ่อย

```bash
# ดู status
git status
git log --oneline --graph -20

# สร้าง feature branch
git checkout dev && git pull && git checkout -b feat/p1-candle-store

# Commit ตาม TDD
git add tests/unit/test_candle_store.py
git commit -m "test(indicator): add candle store unit tests"

git add src/indicator_trade/indicator/candle_store.py
git commit -m "feat(indicator): implement candle store with deque"

# Rebase ก่อน merge
git fetch origin
git rebase origin/dev

# Merge with no-ff
git checkout dev && git merge --no-ff feat/p1-candle-store

# Tag phase milestone
git tag -a v0.1.0 -m "Phase 1: Indicator server complete"
git push origin dev --tags

# ดู branch ทั้งหมด
git branch -a

# ลบ branch ที่ merge แล้ว
git branch -d feat/p1-candle-store
git push origin --delete feat/p1-candle-store
```

---

## 9. กฎสำหรับ AI Assistant (Cascade)

1. **ต้องสร้าง feature branch จาก `dev` ก่อนเริ่มงานเสมอ** — ห้ามทำงานบน `dev` หรือ `main` ตรง
2. **Commit message ต้องตาม Conventional Commits** — `<type>(<scope>): <description>`
3. **ต้อง rebase จาก `dev` ก่อน merge** — ให้ history สะอาด
4. **ใช้ `--no-ff` เมื่อ merge เข้า `dev`** — เพื่อเก็บ merge commit ให้เห็น feature boundary
5. **รัน test ให้ผ่านก่อน commit** — ห้าม commit code ที่ test fail
6. **ห้าม force push บน `dev` หรือ `main`**
7. **ลบ feature branch หลัง merge เสร็จ**
8. **Tag เมื่อจบ Phase** — ตาม version strategy ในหัวข้อ 5
9. **Commit บ่อย atomic commits** — แยก test, feat, refactor เป็นคนละ commit
10. **เมื่อทำ parallel branches** — rebase จาก `dev` เป็นระยะเพื่อลด conflict
