# URScript AI Generator

FastAPI webová aplikace, která převádí přirozený jazyk na URScript pomocí Qwen3.5-4B přes LM Studio, validuje kód a odesílá ho na UR robot (URSim nebo reálný) přes RTDE/port 30002.

## Předpoklady

- Python 3.11+
- [LM Studio](https://lmstudio.ai/) s načteným modelem `qwen3.5-4b`, server na `localhost:1234`
- [Docker Desktop](https://www.docker.com/products/docker-desktop/) s WSL2 backendem (pro URSim)
- UR robot v síti (volitelně — místo URSim)

---

## 1. Spuštění URSim (simulátor)

```bash
cd docker
docker compose up -d
```

Počkej ~60 s. PolyscopeX UI dostupné na **http://localhost:8080**.

**Jednorázové nastavení v PolyscopeX:**
1. Otevři UI → přijmi EULA
2. Zapni robota (ikona napájení)
3. Uvolni brzdy

---

## 2. Spuštění LM Studio

1. Otevři LM Studio → načti `qwen3.5-4b`
2. Záložka **Local Server** → spusť server na portu `1234`
3. Ověř: `curl http://localhost:1234/api/v1/models`

---

## 3. Instalace a spuštění

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows

pip install -e ".[dev]"

copy .env.example .env        # Windows
# upravte .env dle potřeby

uvicorn urscript_app.main:app --reload --host 0.0.0.0 --port 8000
```

UI dostupné na **http://localhost:8000**.

---

## 4. Testy

```bash
pytest                        # unit + integration (bez URSim/LM Studio)
pytest -m e2e                 # vyžaduje běžící URSim + LM Studio
pytest --cov=src --cov-report=term-missing
```

---

## Použití

1. Zadej instrukci v přirozeném jazyce do textového pole
2. Klikni **Generate** — Qwen3.5-4B vygeneruje URScript
3. Zkontroluj/uprav kód ve středním panelu (editovatelný)
4. Klikni **Validate** — zkontroluje syntaxi a bezpečnostní limity
5. Klikni **Execute** — odešle kód na robota
6. **STOP** (nebo **Esc × 2**) — okamžité zastavení

### Přepínání cíle (URSim / reálný robot)

V UI nebo přes API lze přepnout mezi nakonfigurovanými cíli:

| Název     | IP adresa      |
|-----------|----------------|
| localhost | 127.0.0.1      |
| Pepa      | 192.168.0.94   |
| Tom       | 192.168.0.96   |
| Olda      | 192.168.0.98   |

```bash
# přepnutí přes API
curl -X POST http://localhost:8000/api/robot-target \
  -H "Content-Type: application/json" \
  -d '{"target": "Pepa"}'

# zdravotní stav aktuálního cíle (porty 30002 + 30004)
curl http://localhost:8000/api/robot-target/health
```

---

## Bezpečnost

- Kód je **re-validován na serveru** před každým odesláním — klient ho nemůže obejít
- Limity pohybu: `a ≤ 1.4 rad/s²`, `v ≤ 1.05 rad/s`, pracovní rádius `≤ 1.5 m`
- Zakázané funkce: `socket_open`, `exec`, `eval` a veškeré síťové/souborové I/O
- Stop posílá `stopJ` přes RTDE a `stopj(2.0)` přes port 30002 současně
- Safety watchdog (vlákno na pozadí) automaticky nastaví stop flag při změně bezpečnostního módu

---

## Architektura

```
LM Studio (Qwen3.5-4B)
        │  OpenAI-kompatibilní API
        ▼
  llm/generator.py  ─── prompt engineering ──► kódový řetězec
        │
        ▼
  validator/validate.py
    ├── lexer.py      (tokenizace)
    ├── parser.py     (balance bloků)
    └── semantics.py  (limity, zakázané funkce)
        │
        ▼ (pouze validní kód)
  robot/session.py
    ├── rtde_client.py     (polling stavu, RTDE řízení)
    ├── script_sender.py   (port 30002 — odeslání skriptu)
    └── safety.py          (stop supervisor + watchdog)
        │
        ▼
   URSim / reálný UR robot
```

### API endpointy

| Metoda | Cesta | Popis |
|--------|-------|-------|
| POST | `/api/generate` | Generuj URScript z textu |
| POST | `/api/validate` | Validuj URScript kód |
| POST | `/api/execute` | Odešli kód na robota |
| POST | `/api/stop` | Okamžitě zastav robota |
| GET | `/api/status` | Stav RTDE připojení a robota |
| GET/POST | `/api/robot-target` | Čti/nastav aktivní cíl |
| GET | `/api/robot-target/health` | Dostupnost portů aktivního cíle |
| GET | `/healthz` | Health check aplikace |

---

## Proměnné prostředí

Viz `.env.example`. Klíčové hodnoty:

```env
LM_STUDIO_BASE_URL=http://localhost:1234/v1
LM_STUDIO_MODEL=qwen3.5-4b
URSIM_HOST=127.0.0.1
EXECUTION_TIMEOUT_S=60.0
```

---

## Struktura projektu

```
src/urscript_app/
├── api/          # FastAPI routery (generate, validate, execute, status, robot-target)
├── llm/          # LM Studio klient, prompt engineering, generátor
├── validator/    # Lexer, parser, sémantická kontrola
├── robot/        # RTDE klient, script sender, safety supervisor, session orchestrátor
├── web/          # Šablony a statické soubory (Jinja2)
├── config.py     # Nastavení (pydantic-settings), ROBOT_TARGETS, přepínání cíle
└── main.py       # FastAPI app factory

tests/
├── unit/         # Testy validátoru, safety supervisoru, script senderu
├── integration/  # Testy API endpointů
└── e2e/          # End-to-end (vyžaduje běžící URSim + LM Studio)

qwen3.5-4b_qlora_dataset_urscript.yaml         # QLoRA dataset — URScript generace
qwen3.5-4b_qlora_dataset_pattern_matching.yaml # QLoRA dataset — pattern matching
```
