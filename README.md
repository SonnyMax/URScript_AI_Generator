# URScript AI Generator

Generates URScript from natural language via Qwen3.5-4B (LM Studio), validates it, and executes it on URSim via RTDE.

## Prerequisites

- Python 3.11+
- [LM Studio](https://lmstudio.ai/) with `qwen3.5-4b` loaded and server running on `localhost:1234`
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (Windows — enable WSL2 backend)

---

## 1. Start URSim

```bash
cd docker
docker compose up -d
```

Wait ~60 seconds for URSim to boot. Access the PolyscopeX web UI at **http://localhost:8080**.

**One-time setup in PolyscopeX UI:**
1. Open the UI → accept EULA
2. Power on the robot (click the power icon)
3. Release brakes
4. The robot is now ready to receive scripts

---

## 2. Start LM Studio

1. Open LM Studio → load `qwen3.5-4b`
2. Go to **Local Server** tab → Start server on port `1234`
3. Verify: `curl http://localhost:1234/api/v1/models`

---

## 3. Install and run the app

```bash
# Create venv
python -m venv .venv
.venv\Scripts\activate   # Windows

# Install dependencies
pip install -e ".[dev]"

# Copy config
copy .env.example .env   # Windows
# Edit .env if your setup differs

# Run
uvicorn urscript_app.main:app --reload --host 0.0.0.0 --port 8000
```

Open **http://localhost:8000** in your browser.

---

## 4. Run tests

```bash
pytest                        # unit + integration (no URSim needed)
pytest -m e2e                 # requires URSim + LM Studio running
```

---

## Usage

1. **Type** a natural-language instruction in the prompt box
2. Click **Generate** — Qwen3.5-4B generates URScript
3. Review the code in the center panel (editable)
4. Click **Validate** to check syntax and safety bounds
5. If valid, click **Execute** to send to URSim
6. Click **STOP** (or press **Esc × 2**) to halt execution at any time

---

## Safety

- All code is **re-validated server-side** before execution — the client cannot bypass this
- Motion bounds enforced: `a ≤ 1.4 rad/s²`, `v ≤ 1.05 rad/s`, workspace radius `≤ 1.5 m`
- Banned functions: `socket_open`, `exec`, `eval`, and all network/file I/O
- Stop sends both RTDE `stopJ` and raw `stopj(2.0)` over port 30002 simultaneously
- Safety watchdog runs in background; automatically sets stop flag if safety mode changes

---

## Architecture

```
LM Studio (Qwen3.5-4B)
        │  OpenAI-compatible API
        ▼
  llm/generator.py  ─── prompt engineering ──► code string
        │
        ▼
  validator/validate.py
    ├── lexer.py      (tokenize)
    ├── parser.py     (block balance)
    └── semantics.py  (bounds, banned funcs)
        │
        ▼ (valid only)
  robot/session.py
    ├── rtde_client.py   (state polling, RTDE control)
    ├── script_sender.py (port 30002 script upload)
    └── safety.py        (stop supervisor + watchdog)
        │
        ▼
   URSim PolyscopeX (Docker)
```

## Environment variables

See `.env.example` for all configurable values.
