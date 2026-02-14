---
trigger: always_on
---

# Implementation Guide — TDD + Git Workflow

ทุกการ implement ในโปรเจกต์นี้ **ต้อง** ทำตาม TDD (Test-Driven Development) และใช้ Git อย่างเป็นระบบเสมอ

---

## 1. Git Workflow

### Branch Strategy
- **`main`** — stable, ผ่าน test ทั้งหมดแล้วเท่านั้น ห้าม push ตรง
- **`dev`** — integration branch สำหรับรวม feature ก่อน merge เข้า main
- **Feature branch** — สร้างจาก `dev` เสมอ ใช้ format: `feat/<phase>-<short-description>` เช่น `feat/p1-candle-store`, `feat/p3-risk-gate`
- **Bugfix branch** — `fix/<short-description>`
- **Refactor branch** — `refactor/<short-description>`

### Commit Convention
ใช้ [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]
```

**Types:** `feat`, `fix`, `test`, `refactor`, `docs`, `chore`, `ci`
**Scopes:** `indicator`, `trade`, `orchestrator`, `ui`, `infra`, `db`, `redis`

ตัวอย่าง:
```
test(orchestrator): add risk gate boundary value tests
feat(orchestrator): implement risk gate with all circuit breakers
fix(indicator): handle insufficient candle data in EMA calculation
```

### Commit Discipline
- **Commit บ่อย** — ทุก Red-Green-Refactor cycle ควร commit อย่างน้อย 1 ครั้ง
- **Commit ที่ test ผ่าน** — ทุก commit บน `dev` และ `main` ต้อง test ผ่านทั้งหมด
- **Atomic commits** — แต่ละ commit ทำเรื่องเดียว ไม่ปนกัน
- **ห้าม commit ไฟล์ที่ไม่เกี่ยว** — ใช้ `git add` เฉพาะไฟล์ที่เกี่ยวข้อง

### Branch Lifecycle
```
1. git checkout dev && git pull
2. git checkout -b feat/<phase>-<description>
3. ทำงานตาม TDD cycle (ดูหัวข้อ 2)
4. git push -u origin feat/<phase>-<description>
5. เมื่อ feature เสร็จ + test ผ่านหมด → merge เข้า dev
6. ลบ feature branch หลัง merge
```

---

## 2. TDD Workflow (Red → Green → Refactor)

### ทุก feature ต้องเริ่มจาก test ก่อนเสมอ

#### Step 1: RED — เขียน test ที่ fail ก่อน
```
1. สร้าง/แก้ test file ใน tests/
2. เขียน test case สำหรับ behavior ที่ต้องการ
3. รัน test → ต้อง FAIL (ถ้าไม่ fail แสดงว่า test ไม่ถูกต้อง)
4. git add + commit: "test(<scope>): add <description> tests"
```

#### Step 2: GREEN — เขียน code น้อยที่สุดให้ test ผ่าน
```
1. implement เฉพาะที่จำเป็นให้ test ผ่าน
2. ห้ามเขียน code เกินกว่าที่ test ต้องการ
3. รัน test → ต้อง PASS ทั้งหมด
4. git add + commit: "feat(<scope>): implement <description>"
```

#### Step 3: REFACTOR — ปรับปรุง code โดย test ยังผ่าน
```
1. ปรับ code ให้สะอาด อ่านง่าย ลด duplication
2. รัน test → ต้อง PASS ทั้งหมด (ถ้า fail ต้อง revert)
3. git add + commit: "refactor(<scope>): <description>"
```

### Test Pyramid
```
        /  E2E  \          ← น้อย, ช้า, ครอบคลุม full flow
       /----------\
      / Integration \      ← ปานกลาง, test ข้าม module/service
     /----------------\
    /    Unit Tests     \  ← มากที่สุด, เร็ว, isolate แต่ละ function
   /____________________\
```

- **Unit tests** — mock external dependencies (OKX API, Redis, DB, AI APIs)
- **Integration tests** — ใช้ real Redis/DB (Docker) แต่ mock external APIs
- **E2E tests** — full stack ผ่าน Docker Compose

---

## 3. Test File Structure

แต่ละ repo ใช้ `pytest` + `pytest-asyncio`:

```
tests/
  conftest.py              ← shared fixtures (mock redis, mock db session, etc.)
  unit/
    test_<module>.py       ← unit tests, mock ทุก dependency
  integration/
    test_<feature>.py      ← integration tests, ใช้ real infra
    conftest.py            ← fixtures สำหรับ real DB/Redis connections
```

### Naming Convention
- Test file: `test_<module_name>.py`
- Test class: `Test<ClassName>` (optional, group related tests)
- Test function: `test_<method>_<scenario>_<expected>` เช่น:
  ```python
  test_risk_gate_daily_loss_at_threshold_rejects()
  test_risk_gate_daily_loss_below_threshold_passes()
  test_candle_store_backfill_fills_200_candles()
  ```

### Fixtures & Mocking
- ใช้ `pytest.fixture` สำหรับ setup ที่ใช้ซ้ำ
- ใช้ `unittest.mock.AsyncMock` สำหรับ async dependencies
- ใช้ `pytest.mark.asyncio` สำหรับ async test functions
- ใช้ `pytest.mark.parametrize` สำหรับ boundary value tests

---

## 4. Implementation Checklist (ใช้ทุกครั้งก่อนเริ่ม feature)

```
□ สร้าง feature branch จาก dev
□ เขียน test cases ก่อน (RED)
□ Commit test ที่ fail
□ Implement code ให้ test ผ่าน (GREEN)
□ Commit code ที่ทำให้ test ผ่าน
□ Refactor ถ้าจำเป็น + test ยังผ่าน (REFACTOR)
□ Commit refactor
□ รัน full test suite ของ repo นั้น
□ Merge เข้า dev
□ ลบ feature branch
```

---

## 5. คำสั่งที่ใช้บ่อย

```bash
# รัน test ทั้งหมดของ repo
cd <repo>/ && python -m pytest tests/ -v

# รัน เฉพาะ unit tests
python -m pytest tests/unit/ -v

# รัน เฉพาะ test file เดียว
python -m pytest tests/unit/test_risk_gate.py -v

# รัน เฉพาะ test function เดียว
python -m pytest tests/unit/test_risk_gate.py::test_daily_loss_at_threshold_rejects -v

# รัน พร้อม coverage
python -m pytest tests/ --cov=src/ --cov-report=term-missing

# ดู test ที่ fail ล่าสุด
python -m pytest tests/ --lf -v
```

---

## 6. กฎสำคัญสำหรับ AI Assistant (Cascade)

1. **ห้าม implement code โดยไม่มี test** — ทุก feature ต้องมี test ก่อนหรือพร้อมกัน
2. **ห้าม commit code ที่ test fail** — ต้องรัน test ให้ผ่านก่อน commit
3. **ต้องใช้ Git ทุกขั้นตอน** — สร้าง branch, commit ตาม convention, merge อย่างเป็นระบบ
4. **Test ก่อน implement เสมอ** — เขียน test file ก่อน แล้วค่อย implement
5. **Commit message ต้องตาม convention** — `<type>(<scope>): <description>`
6. **ห้ามลบหรือแก้ test ให้อ่อนลง** โดยไม่ได้รับอนุญาตจาก user
7. **เมื่อ fix bug** — เขียน regression test ก่อน แล้วค่อย fix
8. **Boundary value testing** — ทุก threshold/limit ต้อง test ค่าขอบ (at, below, above)
9. **Mock external services** — OKX API, Anthropic API, Perplexity API, Redis, DB ต้อง mock ใน unit tests
10. **รัน full test suite** ก่อน merge เข้า dev เสมอ
