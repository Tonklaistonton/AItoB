# AItoB: Enterprise Local AI & LINE Assistant Platform

> **Language / ภาษา:** **English** | [ภาษาไทย](README_TH.md)

An enterprise-grade local AI prototype focused on strict security, data privacy, and per-user authentication. It seamlessly connects local and cloud LLMs (Ollama / Anthropic / OpenAI) with Open WebUI, internal document retrieval, Gmail, and LINE Official Account under a strict **Human-in-the-Loop (HITL)** governance model.

---

## Key Features & Architecture

### 1. Security Gateway & Role-Based RAG (`project/gateway`)
- **Per-User Token Authentication:** Validates identity via Bearer Tokens in a fail-closed design.
- **Permission Boundary Search:** Filters company documents by organizational unit (HR, Finance) and role *before* passing context to the LLM.
- **Prompt Injection Defense:** Neutralizes hostile instructions embedded in retrieved documents or emails, requiring exact source citation tags like `[hr-leave]` or `[finance-budget]`.

### 2. Expense Document Validation & Cleaner (`project/mcp-lab`)
- **Memory-Bounded Processing:** Parses and cleans uploaded CSV and Excel (`.xlsx`) files strictly in memory without overwriting production datasets.
- **Formula Injection Defense:** Detects and rejects spreadsheet cells starting with `=`, `+`, `-`, `@`, or ASCII control characters.
- **High-Precision Decimal Arithmetic:** Performs all financial calculations using `decimal.Decimal` quantized to 2 decimal places, preventing floating-point drift.

### 3. Bounded Gmail Integration (`project/gmail-lab`)
- **Owner Scope Boundary:** Restricts email reading strictly to the authenticated mailbox owner.
- **Safe Truncation:** Truncates message bodies beyond safety limits to avoid context window flooding while explicitly flagging truncated status.

### 4. LINE Official Account & Human-in-the-Loop Inbox (`project/line-bot`)
- **HMAC-SHA256 Webhook Verification:** Verifies incoming `X-Line-Signature` headers with constant-time equality checks.
- **AI Draft Generation:** Pulls customer questions and invokes the local AI assistant to draft suggested responses.
- **Direct SQLite Sync:** Integrates live conversations directly into Open WebUI's database (`webui.db`) under a dedicated folder (`💬 แชทลูกค้า LINE`).
- **HITL Outbound Push:** Allows administrators to inspect, edit, or approve AI-generated drafts from Open WebUI and push them directly to customers via the LINE Messaging API.

### 5. CIS Docker Benchmark Hardening (`compose.yaml`)
- **Non-Root Execution:** All microservices run under unprivileged UID `10001:10001`.
- **Principle of Least Privilege:** Enforces `no-new-privileges: true` and `cap_drop: ALL`.
- **Filesystem Immutability:** Sets root filesystems to `read_only: true` with explicitly sized `tmpfs` mounts tagged `noexec,nosuid`.
- **Network Isolation:** All backend services communicate through an internal bridge network (`aitob-net`) with zero external host port exposure for backend APIs.

---

## Service Map

| Service | Directory | Internal Port | Host Port | Runtime / Framework | Responsibility |
| :--- | :--- | :---: | :---: | :--- | :--- |
| **webui** | `project/open-webui` | `8080` | `3000` | Open WebUI (Node/Python) | Main Chat Interface, Custom CSS & JS Loader |
| **gateway** | `project/gateway` | `8000` | `8000` | Python 3.12 (Base HTTP) | Token Auth, RAG Search, Policy Enforcement |
| **assistant** | `project/mcp-lab` | `8002` | `8002` | Python 3.12 (Threading HTTP) | Unified Agent, MCP Tools, Finance Upload |
| **gmail** | `project/gmail-lab` | `8001` | `8001` | Python 3.12 (Base HTTP) | Gmail OAuth & Read Boundary API |
| **line-bot** | `project/line-bot` | `8003` | `8003` | Python 3.12 (Threading HTTP) | LINE Webhook Receiver, SQLite Sync, Push API |

---

## Repository Layout

```
AItoB/
├── .github/workflows/       # CI/CD: Gitleaks Secret Scan & Automated Tests
├── compose.yaml             # Universal Docker Compose (CIS Hardened)
├── docs/                    # Project Reports, Kanit PDFs, and ADRs
│   ├── adr/                 # Architecture Decision Records (e.g. LINE Webhook HITL)
│   └── fonts/               # Kanit Font Family (OFL License)
├── evidence/                # Security audit and browser verification evidence
├── fixtures/                # Synthetic test fixtures (Excel, CSV)
├── project/
│   ├── gateway/             # Auth, Search, RAG, Workflow
│   ├── gmail-lab/           # Gmail Integration
│   ├── line-bot/            # LINE Official Account Service
│   ├── mcp-lab/             # Assistant Service & Finance Validation
│   └── webui/               # Open WebUI Pipe, CSS & JS
├── tests/                   # Isolated Unit Tests & Self-checks
├── tools/                   # Stack management scripts & asset deployer
│   └── archive/             # Historical / reference scripts
├── .env.example             # Environment template
├── READMEfix.md             # Thai Documentation
└── README_EN.md             # English Documentation (This file)
```

---

## Quick Start Guide

### Prerequisites
- Docker Desktop or WSL Container CLI (`wslc.exe`)
- Python 3.12+
- Local Ollama (`ollama run gemma4:12b`) or Cloud LLM API Keys (OpenAI / Anthropic)

### Step 1: Configure Environment (.env)
Copy `.env.example` to `.env`:
```sh
cp .env.example .env
```
Key configuration settings in `.env`:
```ini
OPENWEBUI_PORT=3000
GATEWAY_PORT=8000
GMAIL_PORT=8001
ASSISTANT_PORT=8002
LINE_BOT_PORT=8003

# LLM Provider
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=gemma4:12b

# Security (32 URL-safe base64-encoded bytes)
WEBUI_SECRET_KEY=your_generated_random_secret_key
WEBUI_AUTH=true

# LINE Official Account Integration (Optional)
LINE_CHANNEL_ACCESS_TOKEN=your_line_channel_access_token
LINE_CHANNEL_SECRET=your_line_channel_secret
```

### Step 2: Launch the Stack

#### Option A: Docker Compose (Standard)
```sh
# Start all containers in detached mode
docker compose up -d

# Check status
docker compose ps

# Inspect logs
docker compose logs -f gateway
docker compose logs -f line-bot
```

#### Option B: WSLC on Windows 11
```powershell
# Start stack and automatically deploy WebUI custom assets
.\tools\wslc-stack.ps1 start

# Check service status
.\tools\wslc-stack.ps1 status

# View WebUI logs
.\tools\wslc-stack.ps1 logs webui

# Stop the stack
.\tools\wslc-stack.ps1 stop
```

### Step 3: Access
- **Open WebUI:** [http://localhost:3000](http://localhost:3000)
- **LINE Webhook URL:** Point your LINE Developers Console Webhook URL to `https://<your-domain>/webhook` (forwarded to port 8003).

---

## Testing & Security Verification

Run the isolated test suites to verify role-based permissions, upload parsing boundaries, and webhook security:

```sh
# Run all unit tests
python -m unittest discover tests -v

# Run LINE Bot Webhook Signature & Admin Auth Self-Check
python tests/test_line_service.py
```

### Security Standards
1. **Secrets Management:** Never commit API keys, tokens, or `.key` files into Git (enforced via Gitleaks in GitHub CI).
2. **Fail-Closed Principle:** Any signature mismatch or missing Bearer token immediately denies access (HTTP 401/403).
3. **Spreadsheet Sanitization:** All user-supplied tabular data is strictly validated against injection attacks prior to parsing.

---

## Documentation & References

- [Full Installation Manual (PDF, Thai)](docs/AItoB_คู่มือติดตั้งและใช้งาน.pdf)
- [Project Report & Business Plan (PDF, Thai)](docs/AItoB_รายงานโครงการและแผนบริษัท.pdf)
- [ADR 0001: LINE Webhook Integration via Direct SQLite & HITL](docs/adr/0001-line-webui-human-in-the-loop.md)
- [Architecture Glossary](GLOSSARY.md)
- [Developer Guidelines & Routine Commands](CLAUDE.md)
