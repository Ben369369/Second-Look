# Instructions for coding agents

Read `PROJECT_SPEC.md` in full before changing anything; it is the source of truth for scope, stage order, and acceptance gates. Read `docs/BUILD_STATUS.md` to find the current milestone and the next concrete task, and update it at the end of every working session.

## Product invariants (do not break)

- All data is synthetic. Teams and players are fictional. The UI always shows the synthetic-match badge.
- The language model never owns numbers. Every number shown comes from a typed fact or a simulation result produced by code.
- Every displayed finding is labelled **observed**, **estimated**, or **simulated**.
- Observed retrieval never reads past the replay cursor; forecasts never read recorded future outcomes.
- Provider mode is always visible: `offline` (no model), `foundry` (real Microsoft model calls), `fallback` (provider failed; template text, labelled).
- Never mark a stage complete without verifying its acceptance gate. Never report skipped checks as passed.
- Do not create paid cloud resources, publish the repository, or submit the hackathon entry without Benedict's explicit authorization.

## Commands (run from the repo root unless noted)

| Task | Windows | macOS/Linux |
|---|---|---|
| Backend setup | `cd backend; py -3.12 -m venv .venv; .\.venv\Scripts\python.exe -m pip install -r requirements.lock; .\.venv\Scripts\python.exe -m pip install -e . --no-deps` | same with `python3.12` and `.venv/bin/python` |
| Backend server | `cd backend; .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000` | `.venv/bin/python -m uvicorn ...` |
| Backend tests | `cd backend; .\.venv\Scripts\python.exe -m pytest -q` | `.venv/bin/python -m pytest -q` |
| Regenerate fixtures | `backend\.venv\Scripts\python.exe scripts\generate_fixtures.py` | `backend/.venv/bin/python scripts/generate_fixtures.py` |
| Frontend setup | `cd frontend; npm ci` | same |
| Frontend dev | `cd frontend; npm run dev` (http://127.0.0.1:5173, proxies `/api` to :8000) | same |
| Type-check + build | `cd frontend; npm run build` | same |
| Unit tests | `cd frontend; npm test` | same |
| Browser tests | `cd frontend; npm run e2e` (starts both servers; uses installed Edge — set `PLAYWRIGHT_CHANNEL=chrome` or `""` otherwise) | same |

Deploy (only with Benedict's go-ahead): `npx vercel@65.2.0 deploy --prod --yes` from the repo root, then `E2E_BASE_URL=<url> npm run e2e` in frontend/.

After editing `backend/app/data/generator.py`, regenerate fixtures; `test_committed_fixture_matches_generator` fails otherwise.

## Conventions

- Backend contracts live in `backend/app/schemas.py`; mirror changes in `frontend/src/api/types.ts`.
- API errors use `{code, message}` with stable codes (`app/errors.py`).
- Scenario IDs match `^[a-z0-9_]{1,64}$` and resolve only through the registry, never as raw paths.
- Keep tests focused on risks that could invalidate the demo (see spec §16), not trivial coverage.
