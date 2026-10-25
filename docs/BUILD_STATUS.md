# Build status

_Last updated: 2026-10-25_

## Current milestone

**Stage 2 complete; UI rebuilt as a light Chui Labs dashboard.** Acceptance gate verified: independently checked facts seek to the correct frames, both in pytest and in a real browser. Stage 3 (responsive short simulation, three interventions) has not started.

## Implemented and verified

**Stage 0–1** (see git history once a repository exists): scaffold, seeded `rb_press_hero` fixture (21.9 s, 220 frames, 26 events), validator, replay API.

**Stage 2: metrics, facts, evidence**
- `backend/app/metrics/view.py`: a cutoff view.
  - Drops frames after the cutoff.
  - Removes outcomes and end positions of passes, shots and carries that finish after it.
  - Decides by time, so it also works for event-only data.
- `backend/app/metrics/core.py`: pure metric functions. Pass distance, completion (unknown outcomes excluded), possession spells, tracked running (gaps not bridged, bad timestamps rejected), lane-access heuristic, attacking-direction normalisation.
- `backend/app/metrics/facts.py`: typed `Fact` objects (observed/estimated) with method version, coverage, sources, frame range, limitations, and a statement rendered from the value in code. Event-only data refuses tracked metrics.
- `backend/app/investigations/questions.py`: an 8-intent catalogue and an offline keyword router.
  - Intents: pressing decision, passing options, pass lengths, completion, possession, distance/speed, pressure, final third.
  - Unsupported questions get the supported list. Ambiguous players ("#2") get a clarification request.
  - The pressing answer states explicitly that the counterfactual needs the simulator (not built).
- API: `GET /api/questions`, `GET /api/scenarios/{id}/facts?start_s=&end_s=&cursor_s=`, `POST /api/scenarios/{id}/ask` (`{question, cursor_s}`).
- UI rebuilt as an analyst workstation (Benedict chose this direction), using Mantine 9 and IBM Plex Sans/Mono:
  - Graphite panes, a 1 px rule grid, a status bar with seed and dataset hash.
  - Pitch with a 5 m grid, thirds and distance ticks.
  - Telestration: measurement lines, dashed passing lanes, a threat line to the lane, run paths. Short lines omit their label.
  - Transport with event lanes (PASS/PRESS/SHOT) and a cutoff marker.
  - Query pane with a cutoff mode ("whole sequence" / "up to replay"). Answer sentences carry `[n]` fact references.
  - Evidence / All facts / Events tables. Fact rows expand to show method, window, sources, coverage, limits and ID.
  - A stale-answer warning when the replay moves before an answer's cutoff.

**UI rebuild (Benedict's request, 2026-10-25):** light white + navy theme modelled on the Mantine Analytics admin dashboard, with Mantine's default font and the Chui Labs logo (an SVG recreation of the Chui letterhead mark).
- Full-height sidebar with five pages, hash-routed so back/forward works: Overview, Ask & evidence, Players, Events, Methods & data.
- The header search box asks questions and opens the Ask page.
- KPI stat cards, each backed by a real fact. Clicking one seeks the replay and draws the fact on the pitch.
- A pressure-distance line chart (each presser → pressed player, with the 3 m threshold and a playhead) and a per-player speed chart. Clicking a chart seeks the replay.
- Players table: team filter, sorting, and a click to trace the player's run on the pitch.
- Events table with type filters.
- Methods page drawn from the model card and the manifest.
- Shared studio state, so every page drives the same replay.

## Checks run and results

| Check | Command | Result |
|---|---|---|
| Backend tests | `backend: .venv/Scripts/python.exe -m pytest -q` | 51 passed |
| Type-check + build | `frontend: npm run build` | passed |
| Frontend unit tests | `frontend: npm test` | 5 passed |
| Browser E2E (Edge) | `frontend: npm run e2e` | 8 passed (adds: stat card seeks, chart click seeks, header search, players page, methods page) |
| Visual review | screenshots at 1440×900, 1280×720, 390×844 | reviewed; fixed line labels hidden under name tags, over-dimmed players, truncated ratio values |

The Stage 2 tests cover:
- **Hand-calculated values:** 3-4-5 pass distance; 1.0 m / 5.0 m/s running; gap not bridged; duplicate timestamp rejected; possession spells across a loose ball; lane margins.
- **Edge cases:** completion with unknown outcomes and a zero denominator; attacking-direction normalisation.
- **Event-only refusal.** This test caught a real bug: the cutoff view hid every pass end when no frames existed. Fixed.
- **Future leakage** across 4 cutoffs × 4 questions.
- **Fact frames:** facts point at the frames they were measured on, and one distance is recomputed from raw frames.
- **Text and numbers:** answer sentences cite only returned facts, and statement numbers match fact values.
- **Routing:** unsupported and clarify behavior.
- **Browser:** the hero question shows an observed 8.5 m card that seeks to 11.4 s / F114, and an estimated lane card at 13.7 s; unsupported/ambiguous questions; the stale-cutoff warning.

Not checked: real screen readers, contrast measurement, and browsers other than Edge.

## Known failures or limitations

- The lane heuristic is uncalibrated. The hero inside-lane margin is +0.03 s, effectively a toss-up (documented in MODEL_CARD).
- The offline router is keyword-based and will miss paraphrases. This is by design until the Stage 5 planner.
- The carrier's on-ball actions are scripted in the fixture (DATA_CARD).
- Mantine's CSS adds about 260 kB uncompressed (39 kB gzipped). Acceptable for now.
- Unchanged from earlier: the starlette `httpx2` deprecation warning; `.env` is not loaded automatically; the project sits in OneDrive; no git repository yet.

## Decisions and tested dependency versions

- UI direction: a light Mantine admin-dashboard look in Chui Labs navy (replaced the dark analyst workstation at Benedict's request).
- Mantine 9.7.4 (`@mantine/core`, `@mantine/hooks`, `@mantine/charts`), recharts 3.10.1, and `@tabler/icons-react`. IBM Plex was removed.
- Team colours changed to Cedar navy `#1e3a8a` and Harbor red `#e03131` (manifest only; the dataset hash is unchanged).
- Chart series are read directly from recorded frames (observed geometry, no smoothing). Recharts only registers a clicked point after a hover, so the browser test hovers first.
- The scrubber stays a native `<input type="range">`, styled. It is more accessible and testable than a custom slider.
- Fact statements are rendered by backend code from values. The answer is a list of `{text, fact_ids}`, ready for Stage 5 claim validation.
- Earlier versions are unchanged: Python 3.12.10, Node 24.11.1, React 19.3.1, Vite 8.3.5, TypeScript 7.0.2, FastAPI 0.162.0, Pydantic 2.14.1, NumPy 2.5.4.

## Configuration/deployment status

**Vercel (deployed 2026-10-25, at Benedict's request):** https://second-look-dusky.vercel.app. Project `ben369369s-projects/second-look`, deployed from the CLI with no Git integration.
- Setup: `vercel.json` defines two Vercel Services (beta): `web` (frontend/, Vite, `npm run build` → dist) and `api` (backend/, FastAPI `app.main:app`, Python 3.12). `/api/*` routes to `api`; everything else goes to `web`.
- Dependencies come from the pinned `backend/pyproject.toml`. Fixtures moved to `backend/fixtures/` so the API service bundle contains them. `.vercelignore` excludes `.venv`, `node_modules`, builds and `.env*`.
- Verified live: every API endpoint returns 200, the hero question is answered, unknown IDs return 404, and all 8 Playwright tests pass against the production URL (`E2E_BASE_URL=https://second-look-dusky.vercel.app npm run e2e`).
- The first deploy failed because `requires-python` allowed 3.11 while numpy 2.5.4 needs ≥3.12. The project now requires 3.12.
- Redeploy: `npx vercel@65.2.0 deploy --prod --yes` from the repo root.
- The deployment is public, offline mode, synthetic data only. When a model is connected (Stage 5), public model endpoints need rate limits or access control (spec §17) before redeploying.

Previously: 
Offline only. No Azure resources created and no credentials configured. Nothing is deployed or published. Hosting discussion: Vercel would suit only a replay-only build; the full app targets one container (Stage 8).

## Next concrete task

Stage 3:
1. `backend/app/simulation/`: kinematic step shared with the generator; rule-based responsive policies (attacker pass/carry/retain choice from local geometry; defender follow/cover/contain); bounded execution noise from a coupled seed schedule keyed by (rollout, player, step, event type).
2. Interventions `hold`, `press_earlier`, `press_with_cover`, branching from the earliest changed frame with no teleport.
3. Outcomes over 6–10 s: dangerous-zone entry, possession retained, time to regain.
4. `POST /api/scenarios/{id}/compare` with 100–200 seeded rollouts, a paired bootstrap for differences, and a cache.
5. Tests: reproducibility, no position jumps, an opponent responds differently to an intervention, rates from actual counts, a paired-interval sanity case.
