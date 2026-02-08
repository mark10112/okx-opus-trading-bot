# System Design Update — v1.2 Patch Notes

> **Changes:** Secret Management — ไม่เก็บ secrets บน VPS โดยตรง
> Applies to: `AI_Trading_Bot_System_Design.md` v1.0 + v1.1 Patch

---

## Summary of Changes

| Section | Change |
|---|---|
| **NEW** 11. Secret Management | Section ใหม่ทั้งหมด |
| 9. Deployment | อัพเดท docker-compose ให้ใช้ external secrets |
| Configuration (.env) | เปลี่ยนจาก .env file → secret injection |

---

## 11. Secret Management (NEW SECTION)

### 11.1 ปัญหา

Trading bot มี secrets หลายตัวที่ sensitive มาก:

```
# ❌ ไม่ควรเก็บบน VPS แบบ plaintext
ANTHROPIC_API_KEY=sk-ant-xxxxx
OKX_API_KEY=xxxxx
OKX_SECRET_KEY=xxxxx
OKX_PASSPHRASE=xxxxx
PERPLEXITY_API_KEY=pplx-xxxxx
POSTGRES_PASSWORD=xxxxx
TELEGRAM_BOT_TOKEN=xxxxx
GRAFANA_ADMIN_PASSWORD=xxxxx
```

ถ้า VPS ถูก compromise → ทุก key หลุดหมด

---

### 11.2 ตัวเลือก

| วิธี | ความยาก | ราคา | เหมาะกับ | ข้อดี | ข้อเสีย |
|---|---|---|---|---|---|
| **A. Doppler** (Cloud) | ง่ายมาก | ฟรี (5 users, 3 projects) | ✅ แนะนำ | UI ดี, inject ผ่าน CLI, ไม่ต้อง self-host | Secrets อยู่บน cloud ของ Doppler |
| **B. Infisical** (Cloud) | ง่าย | ฟรี (25 secrets/env) | ทางเลือก | Open source, self-host ได้ | Free tier จำกัด |
| **C. Infisical** (Self-hosted) | ปานกลาง | ฟรี | ต้องการ full control | Data อยู่กับเราหมด | ใช้ RAM เพิ่ม ~500MB บน VPS |
| **D. SOPS + Age** | ง่าย | ฟรี | minimalist | ไม่มี dependency, encrypt ใน Git ได้ | ไม่มี UI, manual rotate |
| **E. Docker Secrets** | ง่าย | ฟรี | Docker Swarm only | Built-in Docker | ต้อง Swarm mode |
| **F. HashiCorp Vault** | ยาก | ฟรี (self-host) | Enterprise | Feature ครบสุด | Overkill สำหรับ project นี้ |

---

### 11.3 แนะนำ: Doppler (Primary) + SOPS (Backup)

#### ทำไม Doppler?

- **ฟรี** สำหรับ 5 users, 3 projects (เราใช้แค่ 1 project)
- **Secrets ไม่อยู่บน VPS เลย** — inject เข้า process ตอน runtime
- CLI ง่ายมาก: `doppler run -- docker compose up`
- มี audit log, versioning, rollback
- รองรับ environments (dev / staging / production)
- ไม่ต้อง self-host อะไร

#### ทำไม SOPS เป็น backup?

- กรณี Doppler ล่ม หรือไม่อยากพึ่ง third-party
- Encrypt secrets ลง Git repo ได้ (encrypted at rest)
- ใช้ Age key (เก็บบนเครื่อง local เท่านั้น)

---

### 11.4 Setup: Doppler

#### 11.4.1 สร้าง Project

```bash
# ติดตั้ง Doppler CLI บน VPS
curl -sLf --retry 3 --tlsv1.2 \
  --proto "=https" \
  "https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key" | \
  gpg --dearmor -o /usr/share/keyrings/doppler-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/doppler-archive-keyring.gpg] \
  https://packages.doppler.com/public/cli/deb/debian any-version main" | \
  tee /etc/apt/sources.list.d/doppler-cli.list
apt update && apt install -y doppler

# Login (ทำครั้งเดียว — ใช้ Service Token สำหรับ production)
doppler login

# สร้าง project
doppler projects create trading-bot

# ตั้ง secrets
doppler secrets set \
  ANTHROPIC_API_KEY="sk-ant-xxxxx" \
  OKX_API_KEY="xxxxx" \
  OKX_SECRET_KEY="xxxxx" \
  OKX_PASSPHRASE="xxxxx" \
  PERPLEXITY_API_KEY="pplx-xxxxx" \
  POSTGRES_PASSWORD="xxxxx" \
  TELEGRAM_BOT_TOKEN="xxxxx" \
  GRAFANA_ADMIN_PASSWORD="xxxxx"
```

#### 11.4.2 Docker Compose Integration

```yaml
# docker-compose.yml — ไม่มี .env file ไหนบน VPS

services:
  orchestrator:
    build: ./orchestrator
    # Secrets inject ผ่าน Doppler
    environment:
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - OKX_API_KEY=${OKX_API_KEY}
      - OKX_SECRET_KEY=${OKX_SECRET_KEY}
      - OKX_PASSPHRASE=${OKX_PASSPHRASE}
      - PERPLEXITY_API_KEY=${PERPLEXITY_API_KEY}
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
    depends_on:
      - postgres
      - redis

  postgres:
    image: timescale/timescaledb:latest-pg16
    environment:
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=trading_bot

  grafana:
    image: grafana/grafana:latest
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=${GRAFANA_ADMIN_PASSWORD}
```

#### 11.4.3 Run with Doppler

```bash
# ✅ Secrets inject at runtime — ไม่มี .env file บน VPS
doppler run --project trading-bot --config prd -- docker compose up -d

# หรือใช้ Service Token (สำหรับ automation / systemd)
export DOPPLER_TOKEN="dp.st.prd.xxxxx"
doppler run -- docker compose up -d
```

#### 11.4.4 Systemd Service

```ini
# /etc/systemd/system/trading-bot.service
[Unit]
Description=AI Trading Bot
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
# Service Token เก็บใน systemd credential store
Environment=DOPPLER_TOKEN=dp.st.prd.xxxxx
ExecStart=/usr/bin/doppler run -- /usr/bin/docker compose -f /opt/trading-bot/docker-compose.yml up -d
ExecStop=/usr/bin/docker compose -f /opt/trading-bot/docker-compose.yml down
WorkingDirectory=/opt/trading-bot

[Install]
WantedBy=multi-user.target
```

> ⚠️ Doppler Service Token ยังอยู่บน VPS เป็น 1 token — แต่ token นี้ revoke ได้ทันทีจาก Doppler dashboard ถ้า VPS ถูก compromise ต่างจาก .env ที่มี secrets ทุกตัว

---

### 11.5 Setup: SOPS + Age (Backup / Offline)

#### 11.5.1 Install

```bash
# บนเครื่อง local (ไม่ใช่ VPS)
brew install sops age       # macOS
# หรือ
apt install -y age && \
  curl -Lo sops https://github.com/getsops/sops/releases/latest/download/sops-linux-amd64 && \
  chmod +x sops && mv sops /usr/local/bin/
```

#### 11.5.2 สร้าง Key Pair

```bash
# สร้าง key (เก็บบนเครื่อง local เท่านั้น!)
age-keygen -o ~/.config/sops/age/keys.txt

# จะได้ public key เช่น:
# age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

#### 11.5.3 Encrypt Secrets

```bash
# สร้าง .sops.yaml ใน project root
cat > .sops.yaml << 'EOF'
creation_rules:
  - path_regex: \.enc\.env$
    age: >-
      age1xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
EOF

# สร้าง secrets file
cat > secrets.env << 'EOF'
ANTHROPIC_API_KEY=sk-ant-xxxxx
OKX_API_KEY=xxxxx
OKX_SECRET_KEY=xxxxx
OKX_PASSPHRASE=xxxxx
PERPLEXITY_API_KEY=pplx-xxxxx
POSTGRES_PASSWORD=xxxxx
TELEGRAM_BOT_TOKEN=xxxxx
GRAFANA_ADMIN_PASSWORD=xxxxx
EOF

# Encrypt
sops -e secrets.env > secrets.enc.env

# ลบ plaintext ทิ้ง
rm secrets.env

# ✅ secrets.enc.env สามารถ commit ลง Git ได้ (encrypted)
```

#### 11.5.4 ใช้งาน (Decrypt → Docker)

```bash
# บน VPS — ต้องมี Age private key
export SOPS_AGE_KEY_FILE=~/.config/sops/age/keys.txt

# Decrypt แล้ว inject เข้า docker compose
sops -d secrets.enc.env | \
  xargs -d '\n' env docker compose up -d

# หรือ decrypt เป็น temp file (ลบทันทีหลังใช้)
sops -d secrets.enc.env > /tmp/.env
docker compose --env-file /tmp/.env up -d
rm -f /tmp/.env
```

---

### 11.6 Security Comparison

| | .env on VPS (เดิม) | Doppler (แนะนำ) | SOPS + Age |
|---|---|---|---|
| Secrets บน VPS disk | ✅ Plaintext | ❌ ไม่มี (runtime only) | ❌ Encrypted only |
| ถ้า VPS ถูก hack | หลุดหมด | หลุดแค่ Service Token (revoke ได้) | ต้องมี Age key ถึง decrypt ได้ |
| Audit log | ❌ | ✅ ดูได้ว่าใครเข้าถึง secrets เมื่อไหร่ | ❌ |
| Secret rotation | Manual | ✅ เปลี่ยนจาก Dashboard | Manual |
| Version history | ❌ | ✅ Rollback ได้ | ✅ Git history |
| Offline access | ✅ | ❌ ต้องต่อ internet | ✅ |
| เก็บใน Git | ❌ ห้าม | ❌ ไม่จำเป็น | ✅ (encrypted) |
| ค่าใช้จ่าย | ฟรี | ฟรี (≤5 users) | ฟรี |

---

### 11.7 Secret Rotation Policy

| Secret | Rotate ทุก | วิธี |
|---|---|---|
| `ANTHROPIC_API_KEY` | 90 วัน | สร้างใหม่บน console.anthropic.com → update Doppler |
| `OKX_API_KEY` + `SECRET` + `PASSPHRASE` | 90 วัน | สร้าง sub-account key ใหม่ → update Doppler |
| `PERPLEXITY_API_KEY` | 90 วัน | Regenerate บน dashboard |
| `POSTGRES_PASSWORD` | 180 วัน | ALTER USER → update Doppler → restart |
| `TELEGRAM_BOT_TOKEN` | ไม่ต้อง rotate | เปลี่ยนเมื่อ compromised เท่านั้น |
| `DOPPLER_TOKEN` (Service Token) | 90 วัน | Regenerate บน Doppler dashboard |

---

### 11.8 .gitignore Updates

```gitignore
# ❌ NEVER commit these
.env
*.env
!*.enc.env          # ✅ encrypted env OK to commit
secrets/
.doppler/
*.pem
*.key

# Age private key — NEVER on VPS or Git
keys.txt
```

---

### 11.9 Emergency: VPS Compromised

```
1. Doppler Dashboard → Revoke Service Token (ทันที)
2. OKX → Disable API key (ทันที)
3. Anthropic Console → Revoke API key
4. Perplexity → Regenerate API key
5. Telegram → /revoke bot token via BotFather
6. Generate new secrets ทุกตัว
7. สร้าง VPS ใหม่ (ไม่ restore จาก compromised snapshot)
8. ตั้ง Doppler Service Token ใหม่
9. Deploy ใหม่ด้วย `doppler run -- docker compose up -d`
```

ขั้นตอน 1-2 ทำได้ภายใน **30 วินาที** จาก mobile เพราะไม่ต้อง SSH เข้า VPS

---

## 9. Deployment Updates

### docker-compose.yml (REPLACE)

เปลี่ยนจาก:
```yaml
env_file:
  - .env    # ❌ ไม่ใช้แล้ว
```

เป็น:
```yaml
environment:    # ✅ inject จาก Doppler at runtime
  - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
```

### Deploy Command (REPLACE)

เปลี่ยนจาก:
```bash
docker compose up -d
```

เป็น:
```bash
doppler run --project trading-bot --config prd -- docker compose up -d
```

---

## Configuration Updates

เพิ่มใน project root:

```
trading-bot/
├── .sops.yaml              # NEW: SOPS encryption rules
├── secrets.enc.env         # NEW: encrypted backup of secrets
├── .gitignore              # UPDATED: exclude plaintext secrets
├── docker-compose.yml      # UPDATED: no .env, use env vars
└── ... (existing files)
```

ลบออก:
```
├── .env                    # ❌ REMOVED: ไม่เก็บ plaintext secrets บน VPS
```
