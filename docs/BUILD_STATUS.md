# Build status

_Last updated: 2026-10-25_

## Current milestone

**26 Oct: Stages 3 and 4 complete; Stage 5 built and tested against the real Agent Framework loop with scripted model replies.** The Stage 5 acceptance gate (real Foundry tool calls) is **not yet verified**: it needs Benedict's Foundry project endpoint, deployment name and `az login`. Held-out variants for the Stage 4 "held-out" gate are scheduled with the Stage 7 evaluation.

Earlier: 
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

**Stages 3–4 (26 Oct):**
- `backend/app/simulation/`: vectorised rule-based rollouts (`rules/1`), branching at the pass that triggered the press, three interventions, common random numbers, Wilson and paired-bootstrap intervals, the predeclared decision rule, a challenger grid with reuse of runs that don't depend on cover delay (about 10 s), and an LRU cache.
- `POST /api/scenarios/{id}/compare` (200 rollouts, about 3 s cold, about 20 ms cached) and `POST /api/scenarios/{id}/challenge`.
- The pressing answer now adds three SIMULATED facts plus the rule's verdict.
- What-if page: cover-delay slider and attacker-policy control with pending/stale state and aborted late requests; action cards with counts and 95% intervals; a recommendation card with the rule text; a simulated replay with a dashed SIMULATED frame and recorded "ghost" positions; the stress-test grid with a tally conclusion; an assumptions accordion.
- Tests (`tests/test_simulation.py`, 11): branch and roles; reproducibility; identical starting state; no teleporting; the carrier's choices change under a press; cover delay acts only through the cover player (a never-arriving cover reproduces press-earlier exactly); recorded future never read; rates equal counts; Wilson and bootstrap sanity; rule inconclusive below 64 rollouts; challenger bounds and a no-clear-winner case. Plus a browser test of the What-if page.

**Stage 5 (26 Oct, code complete, live model pending):**
- `backend/app/agents/`: four `agent_framework.Agent` roles (planner, evidence analyst, challenger, producer) with distinct tools and typed structured outputs.
- Deterministic claim validator with one repair round, and one repair for malformed output.
- 2 retries for transient errors, a 60 s budget, `FunctionInvocationConfiguration` caps, and an offline/fallback pipeline with labels.
- `POST /api/investigations` and `GET /api/investigations/{id}` (in-process registry; runs within the request on Vercel).
- UI: typed claim badges, a provider badge (Rule-matched / AI agents / Fallback), and a "How this answer was made" trace listing model calls, tool calls, validation, rejected claims and errors.
- Tests (`tests/test_agents.py`): 8 run against a scripted chat client built on the framework's `BaseChatClient` + `FunctionInvocationLayer`. One live Foundry test is **skipped** until credentials exist.
- `docs/ARCHITECTURE.md` added.

**Stage 6 (27 Oct, complete, verified locally and in production):**
- Every fact now has a code-rendered `plain` sentence built from the same value.
- Investigations take `audience: casual | analyst`. Casual mode gives one finding, the comparison, the trade-off, what happened, and a caveat, all from the same facts and through the same validator. The producer prompt gets the plain sentences in Foundry mode.
- `GET /api/investigations/{id}/export` returns `ExportBundle` (`overlay/1`): 2–4 insights, `OverlayCue`s with every spec field plus `timebase: sequence_s`, `branch`, a 0.5× playback rate and a 43.8 s recap.
- `validate_export` rejects timing outside the sequence, overlaps, recorded cues not on screen at their fact's moment, unknown facts/runs/players, simulated cues without a SIMULATION label, and any text that isn't approved claims.
- UI: a Fan/Analyst switch (re-asks the question), a casual layout with plain evidence labels, and a Recap & overlay page (cues overlaid on the replay, a cue timeline, half-speed play, JSON download).
- Tests: `tests/test_exports.py` (6) and `e2e/recap.spec.ts` (2). The recap e2e test checks that seeking into each exported cue's window shows exactly that cue.
- Known limit: on Vercel the in-memory investigation registry is per instance, so a follow-up request (poll or export) landing on another instance would get 404. Fine for a single-viewer demo; shared storage would be needed for real use.

**Stage 7 (27 Oct, complete):**
- 12 held-out fixtures with predeclared expectations. Event-only fixtures are supported by the validator and generator.
- `scripts/evaluate.py` writes `docs/EVALUATION.md` and `docs/evaluation_results.json`.
- Results: expectation met in 12/12 variants (including 2 correct abstentions with no press, and event-only refusing tracked and simulated claims); 48/48 investigations completed; 0/156 shown claims fail re-validation; 60/60 injected fabrications rejected.
- The challenger finds a baseline-changing setting on 1 of 9 press variants (ev04, 6/12 cells).
- Pipelines B and C-live were not run (no model deployment).
- This also covers the Stage 4 "held-out variant" gate: ev10/ev11 withhold the pressing finding, and ev12 withholds spatial and simulated claims.

**Stage 8 (27 Oct, docs done; video and submission are Benedict's):** README rewritten to match delivered functionality; `docs/DEMO_SCRIPT.md` (110 s) and `docs/SUBMISSION.md` (paste-ready description, honest Microsoft-technology table, checklist) added. The DATA_CARD now covers the evaluation fixtures.

## Checks run and results

| Check | Command | Result |
|---|---|---|
| Backend tests | `backend: .venv/Scripts/python.exe -m pytest -q` | 77 passed, 1 skipped (live Foundry test, no model deployment available) — 27 Oct |
| Type-check + build | `frontend: npm run build` | passed |
| Frontend unit tests | `frontend: npm test` | 5 passed |
| Browser E2E (Edge) | `frontend: npm run e2e` | 11 passed locally and 11 passed against production (adds the Fan/Analyst and recap-overlay checks) — 27 Oct |
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

## Plan to deadline (27 Oct 2026, 11:59 pm PT)

**26 Oct (today):**
- **A. Stage 3:** simulator. Responsive rule-based policies, three interventions, seeded paired rollouts, outcomes, paired bootstrap, `/compare`, tests.
- **B. Stage 4:** assumption controls (cover delay, attacker policy), predeclared decision rule, challenger grid search with an inconclusive case, "What if" page with the simulated branch drawn on the pitch, held-out variant check.
- **C. Stage 5:** Microsoft Agent Framework (`agent-framework-foundry`). Planner, evidence, challenger and producer roles calling our tools; claim validation; one repair attempt; offline/fallback labels; trace in the UI.
- **Benedict, in parallel:** install the Azure CLI, run `az login`, create a Foundry project and deploy a small chat model, then share the endpoint and deployment name (not keys).

**27 Oct:**
- Stage 6: casual/analyst modes, recap, overlay export and preview.
- Stage 7: evaluation runs (A/B/C), recorded results, fixes.
- Stage 8: ARCHITECTURE / EVALUATION / DEMO_SCRIPT / SUBMISSION docs, redeploy, link checks.
- Benedict: record the video and submit.

**Cut order if late:** Kiswahili → speech → Missing Player → extra fixture families beyond the held-out variants → SSE.

## Next concrete task

0. **Done (27 Oct): live model via Foundry Local.** `SECOND_LOOK_MODE=foundry_local` runs the four agents on `qwen3-8b` on-device. `SECOND_LOOK_LIVE_TESTS=1 pytest tests/test_agents.py -k live` passed: 4 model calls, 3 tool calls, 4 claims approved, 0 rejected, about 83 s on an RTX 5070 laptop GPU. A UI run also completed (provider badge "AI agents · on-device · qwen3-8b", 4 claims, 0 rejected, ~1.4 min, one malformed challenger reply repaired). Local-model adaptations: JSON shape hints in the prompt instead of `response_format`, `/no_think`, json-repair before schema validation, token caps, an HTTP timeout, `max_invocations=1` on data tools, and one local investigation at a time. `tests/conftest.py` keeps the regular suite offline (77 passed, 1 skipped).
1. **Blocked — Azure model deployment hold (27 Oct, early hours):**
   - Created on Azure for Students (bn7622@princeton.edu, Switzerland North; the subscription policy only allows italynorth, switzerlandnorth, spaincentral, uaenorth and austriaeast): resource group `second-look-rg`, AIServices resource `secondlook-chui-ai`, and project `second-look` (endpoint `https://secondlook-chui-ai.services.ai.azure.com/api/projects/second-look`).
   - Every model deployment fails with **715-123420 "unusual activity"**: gpt-5.4-mini (zero quota), gpt-5-mini (quota 500), gpt-oss-120b (quota 5000).
   - The Gmail account nkiprotich439@gmail.com has no Azure subscription. GitHub Models (the considered fallback) was retired on 30 Jul 2026.
   - Benedict is opening a support ticket and asking the organisers.
   - When a deployment exists: set `.env`, then Then run `SECOND_LOOK_LIVE_TESTS=1 pytest tests/test_agents.py -k live` and an end-to-end UI check in foundry mode, and record the model, calls and tokens.
2. Benedict: support ticket / organisers for the Azure hold. If a model deploys, run the live test and update SUBMISSION.md and README.
3. Benedict: record the demo video (DEMO_SCRIPT.md), make the GitHub repo public, push, update Innovation Studio, check links signed out, submit before 11:59 pm PT.

Superseded Stage 3 plan, kept for reference:
1. `backend/app/simulation/`: kinematic step shared with the generator; rule-based responsive policies (attacker pass/carry/retain choice from local geometry; defender follow/cover/contain); bounded execution noise from a coupled seed schedule keyed by (rollout, player, step, event type).
2. Interventions `hold`, `press_earlier`, `press_with_cover`, branching from the earliest changed frame with no teleport.
3. Outcomes over 6–10 s: dangerous-zone entry, possession retained, time to regain.
4. `POST /api/scenarios/{id}/compare` with 100–200 seeded rollouts, a paired bootstrap for differences, and a cache.
5. Tests: reproducibility, no position jumps, an opponent responds differently to an intervention, rates from actual counts, a paired-interval sanity case.
