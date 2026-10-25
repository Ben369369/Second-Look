# Second Look — roadmap and instructions for a VS Code coding agent

Prepared for Benedict Ngetich • 25 October 2026 • Version 1.0

## 1. How Benedict should use this document

1. Create a local folder named `second-look` and open it in VS Code.
2. Save this document at the repository root as `PROJECT_SPEC.md`.
3. Open the AI coding agent, attach/reference this file, and paste the kickoff prompt in section 2.
4. Let the agent implement stages in order. Review working software at each milestone rather than accepting a large untested code dump.
5. Configure Azure credentials locally when the agent reaches the real-model integration. Never paste credentials into the chat or commit them.
6. Keep the progress tracker current so a new agent session can continue without rebuilding completed work.

This is a build specification, not a claim that the described system already exists. Framework APIs, model availability, quotas, and installation requirements must be checked at implementation time. Timing below is a planning estimate, not a delivery guarantee.

## 2. Paste this kickoff prompt into the coding agent

> Read PROJECT_SPEC.md completely. Inspect this workspace and any existing AGENTS.md before editing. Build Second Look as specified, beginning with Stage 0 and then delivering a working Stage 1 vertical slice. Make routine implementation choices autonomously and record them. Preserve existing user work. Do not implement every stage in one untested burst. Execute the relevant checks, start the app when possible, and verify the actual UI. Continue through the next stages after each stage's acceptance gates pass, unless a real blocker requires my input. Keep docs/BUILD_STATUS.md updated with completed work, commands run, failures, and the next concrete task. Use current official Microsoft documentation for the Agent Framework and Foundry adapter; do not invent SDK imports or endpoints. Keep offline and real-model modes explicitly labeled. Do not create paid cloud resources, publish a repository, or submit the hackathon entry until I explicitly authorize those actions. First implement the replay, numerical facts, evidence links, and short-horizon scenario tools. The AI must use these tools rather than fabricate numbers. At each checkpoint report what works, how it was verified, and what is still incomplete.

## 3. Product definition

**Name:** Second Look

**Tagline:** Put your football opinions on the pitch.

**Core user job:** Investigate a tactical claim by seeing the relevant events, comparing plausible short alternatives, and understanding the assumptions that change the answer.

**Hero question:** “Should the right-back have pressed earlier?”

**Hero journey:** Play a fictional match sequence → select a suggested claim or enter a supported question → see the evidence → compare hold / early press / press with cover → vary the cover timing → see the recommendation change, remain stable, or become inconclusive → export a short explanation and timed overlay.

Primary customer for the prototype: a football viewer who wants an understandable explanation. Secondary customer: a broadcast producer who needs a concise, defensible segment. Analyst mode exposes the technical basis. Professional coaching effectiveness is not an established result of this prototype.

### The claim we can defend

“Second Look makes a bounded football argument inspectable using synthetic match evidence and transparent scenario assumptions.”

Do not describe it as the first counterfactual football model, a definitive judge of player decisions, a real Premier League tracking system, or an accurate predictor of hypothetical real matches.

## 4. Scope and priority

### P0 — submission core

- A browser app with a polished animated 2D pitch and fictional teams/players.
- Replay controls: play, pause, reset, speed, scrubber, match clock.
- Synthetic tracking and structured event data with stable IDs and documented generation.
- One complete right-back pressing investigation with responsive attackers and defenders.
- Factual evidence cards linked to replay timestamps.
- A short-horizon comparison of three interventions using repeated seeded rollouts.
- Numerical tools and explicit model assumptions.
- Separate observed, estimated, and simulated output labels.
- Casual and analyst views that differ in information density and language.
- A bounded, real-model agent workflow using Microsoft technology, plus a labeled offline fallback.
- A short automatic recap and machine-readable timed overlay export.
- An obvious “synthetic match” label.
- Meaningful tests, README, reproducible setup, public-repository readiness, and a demo script.

### P1 — only after the core works

- Two more scenario families: a decoy run and a failed press/insufficient-data case.
- English and Kiswahili text, reviewed by Benedict.
- “Missing Player” mode that replaces a player's movement with a plausible alternative.
- Visible agent handoff/revision trace.
- Narration audio through Azure AI Speech.
- One-container Azure deployment.

### P2 — stretch

- Live SSE replay from the backend, glossary evaluation, broadcast export bundle, richer evaluation dashboard.

### Out of scope

Real match scraping, social-media ingestion, full 90-minute autonomous simulation, video detection, 3D/VR, training a large world model, calibrated real-match win probabilities, real-time coaching recommendations, injury diagnosis, authentication/subscriptions, mobile apps, a microservice platform, Kubernetes, and Event Hubs unless a measured requirement justifies them.

Do not add features simply to display more Azure logos. Social discourse informed the question catalogue; it is not evidence about a fictional match.

## 5. Suggested stack and architecture

| Layer | Choice | Why |
|---|---|---|
| Backend | Python, FastAPI, Pydantic | Typed numerical tools and API contracts |
| Numerical work | NumPy; standard library where sufficient | Seeded rollouts and geometry |
| Frontend | React, TypeScript, Vite | Interactive application |
| Rendering | Canvas 2D | Lightweight pitch and trajectory animation |
| Charts | SVG or a small chart library only if needed | A few comparison plots |
| Agents | Microsoft Agent Framework | Purposeful typed handoffs |
| Models | A tool-capable deployment available in Microsoft Foundry | Actual model-backed reasoning |
| Speech | Azure AI Speech, optional | English/Kiswahili narration if supported by the chosen voices |
| Storage | Versioned fixture JSON + local JSON/SQLite where needed | Simple prototype persistence |
| Tests | pytest; frontend test runner; Playwright | Numerical and end-to-end verification |
| Deployment | Multi-stage Docker image, FastAPI serving built frontend | One origin and one deployable unit |

Prefer one backend process and one frontend app. Do not introduce Redis, PostgreSQL, a message bus, or distributed task workers for the initial scope.

Data flow:

1. Synthetic tracking/events enter a session with a known replay cursor.
2. A numerical engine computes permitted facts for that cursor/window.
3. The planner chooses a supported investigation and its parameters.
4. Evidence tools retrieve facts and counterexamples.
5. The scenario tool evaluates interventions with bounded, seeded rollouts.
6. A challenger searches the permitted parameter grid for a recommendation reversal.
7. Validation checks the structured output and evidence references.
8. The producer formats approved findings for casual/analyst and language modes.
9. UI renders evidence, alternatives, and a versioned overlay timeline.

The model never owns numerical ground truth. The scenario engine never claims its assumptions are observed reality.

## 6. Repository layout

Use this structure or a comparably simple one; avoid creating empty architectural layers:

```text
second-look/
  PROJECT_SPEC.md
  AGENTS.md
  README.md
  .env.example
  .gitignore
  Dockerfile
  backend/
    pyproject.toml
    app/
      main.py
      config.py
      schemas.py
      api/
      data/             # loaders and fixture validation
      metrics/          # geometry, windowed facts, heuristic estimates
      simulation/       # movement, policies, interventions, rollouts
      investigations/   # orchestration and typed state
      agents/           # model provider, roles, validation, fallback
      exports/          # recap and timed overlay serialization
    tests/
  frontend/
    package.json
    src/
      api/
      components/
      replay/
      features/
      styles/
    tests/
  fixtures/
    development/
    evaluation/
    manifests/
  scripts/
  docs/
    BUILD_STATUS.md
    ARCHITECTURE.md
    DATA_CARD.md
    MODEL_CARD.md
    EVALUATION.md
    DEMO_SCRIPT.md
    SUBMISSION.md
```

Lock the dependency versions actually tested. Do not copy guessed version pins from memory. Choose a Python version compatible with the verified Microsoft SDK; prefer Python 3.11 or 3.12 if compatible. Use a currently supported Node LTS meeting Vite's verified requirements.

AGENTS.md should summarize the product invariants, relevant run/test commands, scope, and status-file convention. Do not assume the selected VS Code assistant reads AGENTS.md automatically; check its instruction-file mechanism and point it to PROJECT_SPEC.md explicitly.

## 7. Local setup instructions

These are baseline commands; the coding agent must create the matching project files and adjust them to verified dependency requirements.

### Windows PowerShell

```powershell
mkdir second-look
cd second-look
code .
```

After the agent scaffolds the backend:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1
```

The direct Python executable avoids needing to change PowerShell execution policy. On macOS/Linux use `python3 -m venv .venv` and `.venv/bin/python` instead. After a lockfile exists, use `npm ci` for reproducible installs.

Use the Vite development proxy for `/api` to the backend. In production serve the frontend and API from the same origin. Document the actual local URL, health URL, API docs URL, and test commands in README.

## 8. Synthetic data design

### Coordinate and timing conventions

- Pitch dimensions: 105 m × 68 m as a documented prototype convention.
- Coordinates use meters; x is pitch length and y is width.
- Store an explicit attacking direction per team/period. Normalize geometry when computing attacking metrics.
- Time fields use seconds relative to the sequence. Store a separate match clock offset.
- Tracking: start with 10 samples/second for a 20–40 second sequence.
- Every sequence includes all 22 players and ball state, even if the camera-style viewport crops some.
- A piecewise interpolated render may run at display refresh rate; interpolated frames are not new observations.
- Keep frame IDs and event IDs stable across reloads.

### Required schemas

Implement Pydantic models, publish them through OpenAPI, and generate or maintain aligned TypeScript types.

**ScenarioManifest:** schema_version, scenario_id, version, seed, description, fictional teams, pitch dimensions, frame rate, match clock offset, attacking directions, fixture paths, generator version, dataset hash, available fields, and known limitations.

**TrackingFrame:** frame_id, time_s, ball {x, y, z, vx, vy, possession_player_id|null}, players [{player_id, team_id, x, y, vx, vy, observed_fields}]. Optional body orientation must be explicitly generated before it can be used.

**MatchEvent:** event_id, scenario_id, time_s, type, team_id, player_id|null, recipient_id|null, start_position, end_position|null, outcome|null, related_frame_ids. Supported events: pass, reception, carry, shot, tackle, interception, turnover, pressure_start, pressure_end, stoppage. Derive goals from shot outcome; do not double-count them.

**Availability:** specify event-only, full-tracking, or degraded-tracking. Represent missing data as missing, never zero. An observed field in this app means present in the synthetic recording, not recorded from a real match.

### Initial fixture families

1. `press_with_cover`: early press can be useful when a teammate covers the inside lane.
2. `press_without_cover`: visually similar start, exposed inside option; holding may be preferable.
3. `decoy_or_no_decoy`: change the supporting runner's behavior and vary whether the defender follows.
4. `insufficient_tracking`: remove relevant positional data; factual event recap works but spatial recommendation is withheld.

Stage 1 can start with one complete sequence. Add variants during evaluation. Fictional labels such as Cedar FC and Harbor FC avoid borrowing real club branding.

### Generator validity

Enforce pitch bounds, legal possession transitions, plausible speeds/accelerations, no teleportation, and coherent ball travel. Simplify the ball to ground passes in the MVP. Treat aerial play and complex offside handling as unsupported, or implement explicit checks before enabling them. Exclude unsupported actions from candidate interventions.

Emit events from state transitions where feasible and validate consistency against frames. Do not independently handwrite contradictory event and tracking files.

Private simulator state can include policy IDs and intended scenario mechanisms for tests. Do not send those labels, future states, expected verdicts, or ground-truth explanations to the analyst tools or LLM.

## 9. Facts, metrics, and evidence contracts

### Three evidence classes

- **OBSERVED:** directly computed from supplied synthetic records, such as a player's recorded position or pass count.
- **ESTIMATED:** an explicitly defined heuristic/model output, such as lane accessibility or pressure intensity.
- **SIMULATED:** aggregate results or trajectories from alternative rollouts.

A source event existing does not prove a sentence's meaning. Verification must check the subject, time window, quantity, comparison, and evidence class.

### P0 metrics

- Euclidean pass distance from recorded endpoints, in meters.
- Completed / attempted passes within a defined window; exclude unknown outcomes from the relevant denominator and report exclusions.
- Possession sequence duration from explicit transitions; do not infer match-wide possession from pass counts.
- Tracked distance and speed using frame intervals. Mark partial coverage, reject duplicate/non-increasing timestamps, and do not bridge large missing intervals.
- Distance from defender to ball carrier.
- Distance and estimated arrival time to the inside passing lane.
- Available passing lanes under a documented reachability heuristic.
- Final-third event share, labeled precisely as final-third event share unless actual touches are generated.
- Transition frequency/volatility as a descriptive supporting metric.

Do not make xG, pass completion probability, or win probability prerequisites. If a heuristic threat estimate is used, call it a **prototype threat score**, explain its formula, version it, and do not display it as a calibrated probability.

### Fact packet

Each fact must include fact_id, class, subject IDs, metric, value, unit, time_window, source_event_ids, source_frame_range, method_version, availability/coverage, and limitations.

Every model-generated factual clause must reference approved fact IDs. Numbers must come from a typed fact or simulation result. Prefer producing semantic claim objects and rendering numerical slots in code, so the model cannot silently edit a value.

Free-form language is allowed only within the validated claim types. Examples: measured comparison, observed movement, conditional scenario result, insufficient-data notice. Unsupported claims are rejected or rewritten into a clearly labeled interpretation.

## 10. Counterfactual scenario engine

### Scope

Evaluate approximately 6–10 seconds from an intervention frame. Do not simulate the remaining match or translate this directly into a match win probability.

Interventions for the hero case:

- `hold`: continue a role-consistent containment policy.
- `press_earlier`: advance the start of the pressing action within configured limits.
- `press_with_cover`: early press plus a coordinated covering action by a designated teammate.

When changing a policy, replay from the earliest changed frame so continuity is preserved. Do not move a player instantaneously at the displayed intervention frame. Reject physically infeasible parameters.

### Responsive policies

Attackers choose among feasible pass/carry/retain actions based on local geometry and configured tendencies. Defenders decide whether to follow, cover, or contain. Changes to one player must affect other players' subsequent decisions. Reusing every other player's recorded future path is only a sensitivity illustration, not a responsive alternative; label it separately if offered.

Start with transparent rule-based policies with bounded stochastic execution error. Do not train RL for the MVP. Record all assumptions and policy versions.

### Experimental comparison

- Use repeated rollouts per action with an explicit seed schedule; begin around 100–200 if performance permits, then benchmark.
- Couple randomness through a shared schedule keyed by rollout, player, timestep, and event type so branching does not silently destroy pairing.
- Use the same initial state and comparable random conditions across actions.
- Record outcomes such as dangerous-zone entry, possession retained, and time to regain.
- Show counts and rates within the simulator, not real-world probabilities.
- When displaying differences and uncertainty, use a documented paired bootstrap or another suitable paired method. A simple binomial interval is suitable for a single action rate, not automatically for a paired difference.
- Explicitly separate Monte Carlo sampling uncertainty from uncertainty about whether the model represents football well.
- If sample count is too small or the ranking is unstable, return inconclusive.

Candidate recommendation rules must be declared before evaluation. A possible rule: recommend an action only when its chosen primary simulated outcome improves beyond a declared practical margin and uncertainty does not undermine the comparison; otherwise describe the trade-off without selecting a winner. Secondary outcomes must remain visible.

### Assumption controls

Use two visible controls first: covering midfielder arrival delay and attacker response policy. Optionally add execution error. Document allowed ranges; the user cannot invent impossible changes.

The challenger searches a fixed, bounded grid for a ranking reversal or inconclusive setting. Finding one counterexample disproves robustness across that grid; failing to find one does not establish universal robustness.

Cache results by scenario hash, frame, normalized intervention, policy version, seed schedule, and rollout count. Bound concurrent jobs and reject oversized requests.

### Missing Player mode

Replace a run with a plausible alternative trajectory/policy. Do not remove the player from the team. A replacement may occupy a different tactical role, so communicate that limitation. Call the measured change a conditional simulation effect; do not assign unique causal credit in a multi-player interaction.

## 11. Agent workflow

### Roles

1. **Planner:** classify the question; select a supported claim template; ask for clarification only if materially ambiguous. Produce a typed plan.
2. **Evidence analyst:** call bounded retrieval/metric tools for the relevant window; produce support and contradicting facts with references.
3. **Challenger:** request scenario variations and search for reversals; point out alternative explanations and missing data.
4. **Producer:** create the audience/language-specific narrative from validated facts and results.

Use real tool calls and typed handoffs. A deterministic numerical function is a tool, not a separate AI agent. Do not label a sequence of hardcoded templates as model-backed multi-agent reasoning.

### Shared investigation state

Include investigation_id, scenario_id/hash, cursor_time_s, question, supported intent, plan, facts, simulation runs, challenges, approved claim objects, narrative, overlay cues, status, errors, provider mode, and trace summaries.

Expose concise decision summaries and tool results, not hidden model chain-of-thought. No model needs arbitrary shell access, unrestricted network access, or executable code generation inside the running application.

### Tool contracts

- `get_events(scenario_id, start_s, end_s, filters)`
- `get_tracking_window(scenario_id, start_s, end_s, player_ids)`
- `compute_metrics(scenario_id, window, metric_names)`
- `evaluate_interventions(scenario_id, frame_id, actions, bounded_config)`
- `search_reversal(scenario_id, frame_id, actions, parameter_grid)`
- `validate_claims(claim_objects, fact_packet, simulation_results)`

Observed retrieval is restricted to the replay cursor. Forecast tools may start at that cursor and simulate forward, but cannot read recorded future outcomes. Post-event explanations may use data only through their declared cutoff. Add tests against future leakage.

### Bounded execution and recovery

Set configurable limits such as 60 seconds end-to-end, 12 total model/tool turns, and bounded rollout work; benchmark and adjust. These are proposed budgets, not measured performance.

Retry transient provider errors at most twice with backoff within the total deadline. On invalid structured output, allow one repair attempt with validation feedback. On exhaustion, return a clear fallback or error. Do not equate an API failure with insufficient football data.

Run modes:

- `offline`: deterministic templates and tools; UI states “Offline demonstration — no language model connected.”
- `foundry`: actual configured Microsoft model calls with trace metadata.
- `fallback`: provider failed; numerical evidence remains available and generated text uses an explicit template label.

Never silently replay a cached model response while claiming a new live run. Precomputed demo material must carry its original run ID and a visible precomputed label.

## 12. API surface

Implement small explicit endpoints; keep names consistent in backend, frontend, and docs.

| Method/path | Purpose |
|---|---|
| GET `/api/health` | Basic liveness, no credentials |
| GET `/api/capabilities` | Provider mode, available scenarios/languages; sanitized configuration |
| GET `/api/scenarios` | Scenario summaries |
| GET `/api/scenarios/{id}` | Manifest |
| GET `/api/scenarios/{id}/replay` | Bounded tracking/events; acceptable to deliver a small fixture for local animation |
| GET `/api/scenarios/{id}/facts?start_s=&end_s=&cursor_s=` | Validated fact packet |
| POST `/api/investigations` | Start bounded investigation; return ID |
| GET `/api/investigations/{id}` | Current status/results; poll initially |
| POST `/api/scenarios/{id}/compare` | Direct scenario comparison for controls |
| GET `/api/investigations/{id}/export` | JSON overlay and recap bundle |

Use 422 for invalid schema/parameters, 404 for unknown IDs, 429/503 for resource/provider limits as appropriate. Use stable machine-readable error codes and friendly UI messages. Prevent arbitrary file paths in scenario IDs.

For small MVP jobs an in-process task registry is acceptable with one server worker, explicit expiration, bounded capacity, and documented loss on restart. Multi-worker production requires shared persistence/job state; do not scale replicas while pretending in-memory jobs are shared.

An optional SSE endpoint can stream statuses `planning`, `evidence_ready`, `simulating`, `challenging`, `validating`, `complete`, `failed`. Correct polling is preferable to fragile streaming.

## 13. Frontend and UX specification

### Desktop layout

- Header: Second Look, synthetic-data badge, scenario selector, provider status.
- Center/left: largest visual region is the pitch with player numbers and ball.
- Under pitch: timeline, playback controls, annotated events.
- Right: investigation question, evidence cards, comparison controls, concise explanation.
- Lower region or tab: assumptions, simulation comparisons, agent status, export.

Use a dark navy/slate base, accessible contrast, one warm highlight color, and distinct team colors with numbers/shapes so color is not the only identifier. Avoid fake terminal clutter. Support laptop widths around 1280 px and a stacked layout for narrower screens.

### Interaction details

- Clicking an evidence card pauses/seeks to the referenced moment and highlights relevant players.
- Recorded and simulated paths have visibly different styles and a legend.
- Compare views show the same timestamp, orientation, and scale.
- Slider changes show stale/pending state until updated results arrive; cancel or ignore late results from prior settings.
- Scrubbing backward invalidates or labels explanations generated at a later cutoff.
- Keyboard-accessible controls, visible focus, captions/text alternatives for audio, reduced-motion behavior.
- Canvas has an accessible text summary and adjacent controls; canvas visuals alone are not an accessible experience.
- No fake confidence percentages. Use explicit classes and scenario counts.

### Audience modes

**Casual:** one plain-language finding, a short replay, one trade-off, an expandable caveat.

**Analyst:** same underlying finding plus definitions, denominators, frame/event IDs, seed/config, intervals, model limitations, and sensitivity results.

The two modes cannot change underlying facts or reverse the conclusion simply to please a fan.

### Language

Build English first. Add Kiswahili through a glossary of football terms and a structured translation stage that preserves numbers, IDs, caveats, and evidence class. Benedict reviews language quality. If unreviewed, label it. Verify current Speech voice/language support before enabling audio; lack of audio support must not block text.

## 14. Recap and overlay export

Create an automatic 30–60 second recap plan with 2–4 supported insights, not a long essay. Export a timeline that can render alongside the synthetic replay.

**OverlayCue fields:** schema_version, cue_id, source_run_id, scenario_hash, start_s, duration_s, graphic_type, title, body, language, audience, highlighted_player_ids, fact_ids, simulation_run_ids, evidence_class, assumptions_summary, status.

Use match-relative or sequence-relative time consistently, with an explicit timebase. State whether a cue belongs to recorded replay or simulated branch. Validate nonnegative durations, supported graphic types, references, and bounds. Provide an HTML/app preview of the exported cues; JSON alone does not prove synchronization.

Suggested graphics: player spotlight, event comparison, trade-off card, insufficient-data card. Include the simulation label in any exported graphic that contains alternative outcomes.

## 15. Ordered implementation roadmap

Indicative focused build time: roughly 24–36 hours for a capable agent plus human review, with considerable uncertainty. If less time remains, reduce breadth in the cut order below. Never trade factual honesty for more features.

| Stage | Work | Acceptance gate | Estimate |
|---|---|---|---|
| 0 | Inspect workspace; verify tool versions; scaffold; docs/status | Backend health works; frontend loads; dependencies locked | 1–2 h |
| 1 | One synthetic fixture; schema validation; pitch renderer | A coherent sequence plays, pauses, scrubs and resets | 3–4 h |
| 2 | Metrics; fact packets; clickable evidence | Independently checked facts seek to correct frames | 2–3 h |
| 3 | Responsive short simulation; three interventions | Reproducible results; no teleportation; opponents react | 4–6 h |
| 4 | Assumption controls; challenger; conditional recommendation | A held-out variant changes or withholds the finding appropriately | 2–3 h |
| 5 | Real Microsoft agent integration; typed handoffs; fallback | Real tool calls visible; fabricated claims rejected; failures labeled | 3–5 h |
| 6 | Audience modes; recap; overlay export; optional Kiswahili | Same facts across modes; timed preview matches export | 2–3 h |
| 7 | Evaluation, failure cases, UI polish | Meaningful checks and recorded results; no known demo-breaking defects | 3–4 h |
| 8 | Container, deployment preparation, demo/submission assets | Fresh setup works; video rehearsed; links checked | 2–3 h |

### Stage 0 deliverables

Create minimal app, environment template, dependency files, ignore rules, instruction file, and BUILD_STATUS. Check for pre-existing files before scaffolding. Establish npm build and pytest commands. Do not install large ML/CV libraries.

### Stage 1 deliverables

Generate coherent scenario data; make it reproducible by seed. Render the pitch and all players; display stable IDs, clock, and synthetic badge. No LLM is required yet. Test actual playback and seek behavior in a browser.

### Stage 2 deliverables

Implement a small set of trusted metrics. Produce evidence cards from code. Check at least one pass distance, speed interval, and possession duration independently with hand-calculated fixtures. Event-only input must refuse tracked running distance.

### Stage 3 deliverables

Implement a minimal physical movement update, opponent response rules, interventions, seeded trials, and a comparison response. Test a changed defender action causes changed attacker choices in at least one controlled state. Do not hardcode a verdict by scenario name.

### Stage 4 deliverables

Add cover-delay and opponent-policy controls. Search for reversals. Use predeclared decision rules. Include a case with inconclusive results; the app must not always pick a winner.

### Stage 5 deliverables

Before wiring SDK code, read the current official Agent Framework Python samples. Prove one minimal tool-calling agent works with the actual deployment, then expand. Store SDK version, model deployment configuration names, and source documentation links in ARCHITECTURE. Test invalid tool arguments and malformed model output. Model absence cannot prevent replay/numerical features from running.

### Stage 6 deliverables

Build genuinely different casual/analyst presentations. Create recap objects from approved claims. Export and replay overlay cues. Add reviewed Kiswahili text if time permits. Keep speech optional.

### Stage 7 deliverables

Run the evaluation matrix below. Capture actual timing, failure counts, and known limitations. Fix stale data/UI race conditions. Check readability at normal laptop size.

### Stage 8 deliverables

Build the container locally; run it without the dev server. Serve compiled frontend from FastAPI with API paths taking precedence over SPA fallback. Prepare Azure instructions and environment configuration. Ask Benedict only for missing account/resource choices or deployment authorization, with the artifact already reviewable. Keep a local demo available if cloud deployment fails.

### Cut order if time is short

Remove speech → extra languages → second/third scenario families beyond required failure testing → SSE → charts beyond comparison cards → Missing Player mode. Preserve the hero question, correct evidence, responsive comparison, real Microsoft integration, audience views, recap, and limitations.

## 16. Tests and evaluation

Do not create hundreds of trivial tests. Cover the risks that could invalidate the demonstration.

### Numerical/data tests

- Same seed/config gives same fixture and results.
- Positions and speeds remain within declared limits; tracking timestamps are monotonic.
- Possession and pass events agree with tracking transitions.
- Metric values agree with tiny independently specified examples.
- Zero denominators, missing frames, unknown outcomes, and attacking-direction normalization behave correctly.
- No hidden scenario answer or future recorded state is exposed to agents.

### Simulation tests

- All actions start from comparable valid states.
- A shorter reaction time cannot create an instantaneous position jump.
- Changing cover arrival affects available options through geometry/policy, not a fixed score lookup.
- At least one opponent responds differently to an intervention.
- Simulation rates are computed from actual trial counts.
- Paired interval computation has an independent sanity case.
- Reversal search obeys bounds and reports the tested parameter domain.

### Agent tests

- Made-up player/event IDs and altered numerical values fail validation.
- A real citation attached to an unrelated claim fails semantic/typed validation.
- Unsupported intent returns supported options.
- API timeout reports provider failure; missing tracking reports insufficient data.
- One invalid-output repair is bounded; the workflow cannot loop indefinitely.
- Real-model integration smoke test is separate and skipped clearly without credentials; never label skipped checks as passed.

### UI/end-to-end tests

- Load → play → pause → scrub → click evidence → compare → change assumption → switch audience → export.
- New controls cannot display old results as current.
- Analyst and casual outputs reference the same approved facts.
- Offline mode and synthetic labels are visible.
- Exported overlay references and timing match the displayed investigation.
- Keyboard controls and small-screen layout work.

### Evaluation set

Create at least 8–12 held-out scenario variants across cover timing, attacker policy, execution noise, and missing data if feasible. Split by scenario configuration/family, not neighboring frames from the same trajectory. Keep expected mechanisms in evaluation metadata inaccessible to runtime agents. Avoid using names that reveal the correct answer.

Compare:

A. Deterministic event recap.
B. Single model agent using the same numerical tools and data budget.
C. Full planner/evidence/challenger/producer workflow.

Measure supported-claim rate, fabricated numerical claims, invalid citations, appropriate abstentions, recommendation stability/reversal detection, completion rate, latency, calls/tokens, and cost where provider usage is available. Treat evaluation as a small diagnostic set, not evidence of general football expertise. Record actual counts and denominators. Do not invent benchmark wins.

Benedict can additionally review 3–5 explanations with football-playing peers: ask what changed, what the trade-off is, and what remains uncertain. Report this as informal feedback with the real sample size.

## 17. Configuration and deployment

The following names are app-owned configuration conventions; the provider adapter maps them to the current SDK. They are not claims about SDK-native environment variable names.

```dotenv
SECOND_LOOK_MODE=offline
FOUNDRY_PROJECT_ENDPOINT=
FOUNDRY_MODEL_DEPLOYMENT=
AZURE_SPEECH_KEY=
AZURE_SPEECH_REGION=
SIMULATION_MAX_ROLLOUTS=200
INVESTIGATION_TIMEOUT_SECONDS=60
```

Add only provider authentication settings actually required by the verified integration. Prefer Azure identity mechanisms where practical. Keep secrets server-side. Do not expose them through Vite client variables. Provide `.env.example`, never an actual credential-bearing `.env`.

Keep cloud resource creation separate from local builds. Prepare a resource list and region/model compatibility check before deploying. Set application limits and document expected consumption; no cost claim without actual rates/usage. A spending alert is not a hard cap. Public model-backed endpoints require access control or strict request/concurrency/rate limits; a public replay-only demo can remain available separately.

Record the deployment command actually tested. Use a health probe, graceful shutdown, structured logs, sanitized error messages, limited retention of questions, and no raw credentials or complete sensitive prompts in logs. Persist important run records if restarting must preserve investigations; otherwise clearly document ephemeral behavior.

## 18. Two-minute demo plan

Target about 110 seconds, leaving margin below two minutes. Record real functioning software.

| Time | On-screen action | Message |
|---|---|---|
| 0–12 s | Synthetic sequence and question | Football arguments often hide assumptions. |
| 12–30 s | Click the right-back pressing claim | Second Look locates the relevant evidence. |
| 30–50 s | Recorded vs early press replay | Show the inside passing option and trade-off. |
| 50–72 s | Adjust cover delay | The recommendation changes or becomes inconclusive. |
| 72–88 s | Analyst view and short agent trace | Facts, tools, challenged finding, and stated assumptions. |
| 88–102 s | Casual/Kiswahili if implemented | Same intelligence, different presentation. |
| 102–110 s | Recap/overlay and closing | Evidence you can inspect; alternatives labeled as simulations. |

Show a real agent correction if reproducible. If using a stored run, label it. Do not fake latency, provider connection, live data, or deployed functionality. Avoid unlicensed match footage, music, club logos, or player likenesses.

## 19. Submission checklist

The official rules reviewed for this planning work specify a public GitHub repository, a functioning new project, a short description, synthetic football-realistic data, and a public demo video under two minutes. Recheck the organizer's current rules before submitting. The reviewed deadline is 27 October 2026, 11:59 p.m. Pacific.

- [ ] README explains the problem and actual implemented behavior.
- [ ] Repository contains reproducible setup, tested dependency locks, fixture generator, tests, and no secrets.
- [ ] Microsoft technology list reflects actual usage, distinguishing planned/optional features.
- [ ] Data card explains synthetic generation and model card explains limitations.
- [ ] Architecture explains each agent's distinct contribution and failure handling.
- [ ] Evaluation lists actual results and omitted checks.
- [ ] Demo video is public, functioning, under two minutes, and uses permitted assets.
- [ ] Innovation Studio page accurately describes delivered functionality.
- [ ] Repository/video/demo links work for a signed-out reviewer where intended.
- [ ] Final submission status is checked in the actual event portal; saving a draft may not be submission.

Suggested category target: Best Multi-Agent Orchestration, provided the actual build demonstrates the claimed handoffs, recovery, and measurable value. Do not claim a category advantage based only on four role names.

## 20. Completion and handoff requirements

The agent must finish with:

1. What works, with precise limits.
2. Exact local startup commands and URL.
3. Checks run, results, and checks skipped.
4. Configuration required to enable real models.
5. Known limitations and remaining P1/P2 work.
6. Documentation and demo assets produced.
7. Any concrete blocker requiring Benedict's input.

Keep docs/BUILD_STATUS.md as:

```markdown
# Build status
## Current milestone
## Implemented and verified
## Checks run and results
## Known failures or limitations
## Decisions and tested dependency versions
## Configuration/deployment status
## Next concrete task
```

Do not mark a milestone complete because code exists. Verify its acceptance gate. Do not claim deployment, accuracy, accessibility validation, human review, or successful tests that did not occur.

## 21. Reference links for the coding agent

Use current primary documentation. Check the specific SDK sample and installed version together before adopting an API.

- Official hackathon rules: https://github.com/microsoft/insidethegamehackathon/blob/main/OFFICIAL%20RULES.md
- Agent Framework documentation: https://learn.microsoft.com/en-us/agent-framework/
- Agent Framework getting started: https://learn.microsoft.com/en-us/agent-framework/get-started/
- Microsoft Agent Framework repository: https://github.com/microsoft/agent-framework
- Python samples: https://github.com/microsoft/agent-framework/tree/main/python/samples
- Azure Container Apps Python overview: https://learn.microsoft.com/en-us/azure/developer/python/tutorial-deploy-python-web-app-azure-container-apps-01
- Foundry portal: https://ai.azure.com/
- Azure Speech documentation: https://learn.microsoft.com/en-us/azure/ai-services/speech-service/
- FastAPI documentation: https://fastapi.tiangolo.com/
- Vite documentation: https://vite.dev/guide/
- React documentation: https://react.dev/
- Playwright documentation: https://playwright.dev/

Research context, not implementations to copy:

- DeepMind TacticAI: https://deepmind.google/blog/tacticai-ai-assistant-for-football-tactics/
- Defensive ghosting: https://studios.disneyresearch.com/2017/03/03/data-driven-ghosting-using-deep-imitation-learning/
- MADRID robustness research: https://arxiv.org/abs/2401.13460

Second Look's defensible contribution is its bounded investigative workflow and honest presentation. Scientific novelty, real-world predictive accuracy, and professional effectiveness remain unproven.
