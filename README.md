# Second Look

**Put your football opinions on the pitch.**

Second Look makes a bounded football argument, such as *"Should the right-back have pressed earlier?"*, inspectable. It uses synthetic match evidence and transparent scenario assumptions.

> **Status: early build (Stage 2 of 8).** What works today:
> - a seeded synthetic sequence with a validated tracking and event fixture;
> - an analyst-workstation replay UI;
> - typed facts, each labelled **observed** or **estimated**, with method versions, coverage and limitations;
> - eight supported question types: type a question or pick one, and get answer sentences that cite clickable evidence. Clicking seeks the replay and draws the measurement on the pitch.
>
> In offline mode, questions are routed by keyword rules, labelled as such. The scenario simulator ("what if he had pressed earlier?") and the Microsoft Agent Framework integration have **not** been built yet. See [docs/BUILD_STATUS.md](docs/BUILD_STATUS.md).

All data is synthetic. Cedar FC and Harbor FC and their players are fictional. Nothing here is recorded from a real match.

**Live demo:** https://second-look-dusky.vercel.app (offline mode, synthetic data).

## Run it locally

Requirements: Python 3.12 and Node.js 20.19+ or 22.12+ (tested with Python 3.12.10 and Node 24.11.1 on Windows 11).

**Backend** (terminal 1):

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.lock
.\.venv\Scripts\python.exe -m pip install -e . --no-deps
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

On macOS/Linux, use `python3.12 -m venv .venv` and `.venv/bin/python` instead.

**Frontend** (terminal 2):

```powershell
cd frontend
npm ci
npm run dev
```

| What | URL |
|---|---|
| App | http://127.0.0.1:5173 |
| API health | http://127.0.0.1:8000/api/health |
| API docs (OpenAPI) | http://127.0.0.1:8000/docs |

The Vite dev server proxies `/api` to the backend.

## Tests

```powershell
cd backend;  .\.venv\Scripts\python.exe -m pytest -q   # data validity, determinism, API
cd frontend; npm test                                  # replay interpolation / clock
cd frontend; npm run e2e                               # real browser: play, pause, scrub, reset, seek, keyboard, narrow layout
```

The browser tests start both servers themselves and use the installed Microsoft Edge. To use another browser, set `PLAYWRIGHT_CHANNEL=chrome`, or set it to an empty string after running `npx playwright install chromium`.

## How the data is made

`scripts/generate_fixtures.py` runs a seeded, rule-based kinematic simulation at 10 Hz. Players steer under speed and acceleration limits. The ball is held, travels as a ground pass, or is shot. Events (passes, receptions, carries, pressure, the shot) come from state changes inside the simulation, so the tracking and events agree by construction. A validator checks every fixture on load: pitch bounds, speed and acceleration, monotonic timestamps, ball at the possessor, and every possession change explained by an event. See [docs/DATA_CARD.md](docs/DATA_CARD.md).

## Repository layout

```text
backend/    FastAPI app (fixtures in backend/fixtures): schemas, fixture generator/loader/validator, metrics + facts, question routing, API
frontend/   React + TypeScript + Vite + Mantine: canvas pitch with telestration, transport, query, evidence tables
scripts/    Fixture generation
docs/       Build status, data card, model card (more docs arrive with later stages)
```
