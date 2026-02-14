---
trigger: always_on
---

# Implementation Guide — TDD

ทุกการ implement ในโปรเจกต์นี้ **ต้อง** ทำตาม TDD (Test-Driven Development) และ **ใช้ Git เสมอ** เพื่อทำ version control

> **Git workflow** → ดูที่ [.windsurf/rules/git-workflow.md](.windsurf/rules/git-workflow.md)

---

## 1. TDD Workflow (Red → Green → Refactor)

ทุก feature ต้องเริ่มจาก test ก่อนเสมอ:

1. **RED** — เขียน test ที่ fail → commit `test(<scope>): ...`
2. **GREEN** — เขียน code น้อยที่สุดให้ test ผ่าน → commit `feat(<scope>): ...`
3. **REFACTOR** — ปรับ code ให้สะอาด, test ยังผ่าน → commit `refactor(<scope>): ...`

---

## 2. Test Pyramid

- **Unit tests** — mock external dependencies (OKX API, Redis, DB, AI APIs)
- **Integration tests** — ใช้ real Redis/DB (Docker) แต่ mock external APIs
- **E2E tests** — full stack ผ่าน Docker Compose

---

## 3. Test Structure & Conventions

แต่ละ repo ใช้ `pytest` + `pytest-asyncio`:

```
tests/
  conftest.py              ← shared fixtures
  unit/
    test_<module>.py       ← unit tests, mock ทุก dependency
  integration/
    test_<feature>.py      ← integration tests, ใช้ real infra
    conftest.py            ← fixtures สำหรับ real DB/Redis
```

- **Test function naming:** `test_<method>_<scenario>_<expected>`
- ใช้ `pytest.fixture`, `AsyncMock`, `pytest.mark.asyncio`, `pytest.mark.parametrize`

---

## 4. คำสั่งที่ใช้บ่อย

```bash
python -m pytest tests/ -v                    # ทั้งหมด
python -m pytest tests/unit/ -v               # เฉพาะ unit
python -m pytest tests/unit/test_foo.py -v    # เฉพาะไฟล์
python -m pytest tests/ --cov=src/ --cov-report=term-missing  # coverage
python -m pytest tests/ --lf -v              # เฉพาะที่ fail ล่าสุด
```

---

## 5. Pre-commit Hooks (Ruff Linting)

ทุกครั้งที่ commit จะต้องผ่าน ruff linting และ formatting อัตโนมัติ:

```bash
# Install pre-commit (ครั้งแรก)
pip install pre-commit
pre-commit install

# หลังจากนี้ทุก commit จะรัน ruff อัตโนมัติ
git commit -m "feat(indicator): ..."
```

**Ruff hooks:**
- `ruff --fix` — แก้ lint errors อัตโนมัติ (F, E, W, I, N, UP, B, C4, SIM)
- `ruff-format` — format code ตาม ruff style

**ถ้า ruff fail:**
- ดู error แล้วแก้ code
- หรือใช้ `ruff check --fix .` แล้ว commit ใหม่

---

## 6. กฎสำหรับ AI Assistant (Cascade)

1. **ห้าม implement code โดยไม่มี test** — ทุก feature ต้องมี test ก่อนหรือพร้อมกัน
2. **Test ก่อน implement เสมอ** — เขียน test file ก่อน แล้วค่อย implement
3. **ห้ามลบหรือแก้ test ให้อ่อนลง** โดยไม่ได้รับอนุญาตจาก user
4. **เมื่อ fix bug** — เขียน regression test ก่อน แล้วค่อย fix
5. **Boundary value testing** — ทุก threshold/limit ต้อง test ค่าขอบ (at, below, above)
6. **Mock external services** — OKX API, Anthropic API, Perplexity API, Redis, DB ต้อง mock ใน unit tests
7. **รัน full test suite** ก่อน merge เข้า dev เสมอ
8. **Code ต้องผ่าน ruff linting** — pre-commit hook จะ check ทุก commit
