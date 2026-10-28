# Architecture

Second Look is one FastAPI backend and one React frontend, deployed as a single origin (Vercel Services today; a single container is planned). All data is synthetic.

```text
fixtures (seeded generator) ──► loader + validator ──► cutoff view ──► metrics → typed Facts (observed / estimated)
                                                            │
                                                            └─► simulator (branch frame only) → simulated Facts, decision rule, challenger grid
                                                                         ▲
question ──► investigation workflow (offline rules, or Agent Framework agents) ──► tool calls ──┘
                     │
                     └─► claims ──► deterministic validator ──► UI (claims cite facts; clicking a fact seeks the replay)
```

## Components

| Path | Responsibility |
|---|---|
| `backend/app/data/` | Seeded synthetic generator (events emitted from simulator state), fixture loader with hash check, physical/logical validator |
| `backend/app/metrics/` | `view.py` cutoff view (no data after the cursor), `core.py` pure metrics, `facts.py` typed facts with statements rendered by code |
| `backend/app/simulation/` | `engine.py` vectorised rule-based rollouts, `compare.py` predeclared decision rule and challenger grid, `stats.py` Wilson and paired-bootstrap intervals |
| `backend/app/investigations/` | `questions.py` supported-question catalogue and offline router; `registry.py` in-process investigation registry |
| `backend/app/agents/` | `workflow.py` multi-agent orchestration, `tools.py` agent tools, `validate.py` claim validator, `provider.py` chat client for cloud Foundry or Foundry Local |
| `frontend/src/` | Mantine dashboard: replay canvas with telestration, Ask & evidence, What-if, Players, Events, Methods |

## Agent workflow (Microsoft Agent Framework)

There are four `agent_framework.Agent` instances, each with distinct instructions, tools and a typed structured output (`options={"response_format": Model}`). They are coordinated by `Workflow.run_foundry()`:

| Role | Tools | Output (typed handoff) | Distinct contribution |
|---|---|---|---|
| Planner | none (catalogue and roster in its prompt) | `PlanOut`: intent, player/team ids, whether a counterfactual is needed, clarification | Maps free text to one supported intent, or refuses with the supported list |
| Evidence analyst | `compute_metrics`, `get_events` | `EvidenceOut`: supporting / contradicting fact ids, missing data | Retrieves cutoff-bounded facts. Cited ids that no tool returned are ignored and logged |
| Challenger | `evaluate_interventions`, `search_reversal` | `ChallengeOut`: whether the finding survived, concerns (no numbers) | Runs the simulator and searches a fixed assumption grid for settings that change the finding |
| Producer | none | `ProducerOut`: ordered `fact_ids` to show, plus at most 2 `interpretations` `{text, fact_ids}` | Chooses and orders the evidence for the audience and question, and says what it means; code renders every factual sentence |

**Validator (code, not a model).** Every claim is checked by `validate_claim`:
- cited ids must exist;
- factual claims (observed / estimated / simulated) must consist only of the code-rendered `statement` or `plain` sentences of the facts they cite, so the model never words a quantity, unit, relation or comparison; paired comparisons and the decision rule's verdict are facts themselves (`sim_compare`, `sim_verdict`);
- claim type must match the cited evidence classes, and simulated claims must say they are simulated;
- interpretations must cite facts and may not contain numbers or quantity words, certainty words, causal wording, events the data does not record, hand-written comparisons between choices, or counterfactuals that are not tied to cited simulated facts and labelled as simulation;
- every named player must be a subject of a cited fact.

These checks limit what an interpretation can assert; they do not prove it true. Interpretations are shown labelled as interpretation.

**Router guard.** Before any model call, the deterministic router refuses questions naming a player who is not in the sequence and "should have" questions about anything other than the right-back's press (for example an attacker's run), showing the passing evidence at that moment instead.

Rejected claims go back to the producer once with the errors (one repair round). If nothing passes, code-rendered fact statements are shown, labelled in the trace. Rejected claims are listed in the UI trace, never in the answer.

**Bounds and recovery.**
- 60 s total budget (`INVESTIGATION_TIMEOUT_SECONDS`) and at most 30 s per model call.
- Transient provider errors are retried at most 2 times with backoff, inside the budget.
- Malformed structured output gets one repair attempt with the schema error.
- Tool loops are capped through `FunctionInvocationConfiguration` (`max_iterations=4`, `max_function_calls=6`, `max_duration_seconds=30`).
- On provider failure the rule-based pipeline answers, labelled **fallback**, with the error recorded. A provider failure is never reported as insufficient data.

**Modes.**
- `offline`: rule-based router, same tools, labelled "Offline demonstration — no language model connected".
- `foundry`: real model calls to a cloud Foundry deployment, with model and tool-call counts and tokens in the trace.
- `foundry_local`: the same agents on a model running on this device through Foundry Local, reached with Agent Framework's `OpenAIChatCompletionClient` at the local server's OpenAI-compatible endpoint (the `agent-framework-foundry-local` package pins an SDK that does not work with Foundry Local CLI 0.12). Small local models need extra care: JSON shape hints in the prompt instead of `response_format` (the local server mishandles it), `/no_think`, json-repair of syntax before schema validation, per-role token caps, an HTTP timeout of a third of the budget, `max_invocations=1` on the data tools (reset per retry), no tool for the planner (the roster is in its prompt), and one investigation at a time.
- `fallback`: as described above.

Cached model responses are never replayed as live runs.

**Trace.** The UI's "How this answer was made" lists each model call, tool call (with arguments summarised), validation result, repair and fallback, with durations. It shows decision summaries and tool results, not hidden model reasoning.

**What models cannot do.** They have no shell, file, network or code-execution tools. They cannot read recorded data after the cursor, and cannot produce a number that is not in a code-generated fact.

## Testing the agent loop without a model

`backend/tests/fake_chat.py` subclasses the framework's own `BaseChatClient` with `FunctionInvocationLayer`, so `Agent.run`, tool invocation and structured-output handling are the real framework code; only model replies are scripted. `tests/test_agents.py` checks:
- real tool calls and handoffs;
- altered numbers rejected, with one repair;
- a bounded repair when the model keeps failing;
- fabricated ids and mis-attached citations rejected;
- unsupported intent;
- provider failure leading to a labelled fallback;
- malformed output getting one repair, then fallback;
- invalid tool arguments.

A live Foundry smoke test runs only with `SECOND_LOOK_LIVE_TESTS=1`, and is reported as **skipped** otherwise. `tests/conftest.py` forces offline mode for the regular suite. With Foundry Local it passed; in a small benchmark of the current workflow, 4 of 4 fresh runs of the pressing question completed with the live agents (no fallback), 70–196 s each on an RTX 5070 laptop GPU, with the reversal search run and the validator rejecting 12 model interpretations (docs/EVALUATION.md).

## Configuration

| Variable | Meaning |
|---|---|
| `SECOND_LOOK_MODE` | `offline` (default), `foundry` or `foundry_local` |
| `FOUNDRY_LOCAL_MODEL` | Foundry Local model alias, e.g. `qwen3-8b` |
| `FOUNDRY_LOCAL_ENDPOINT` | Optional; otherwise read from `foundry server status` |
| `FOUNDRY_PROJECT_ENDPOINT` | `https://<resource>.services.ai.azure.com/api/projects/<project>` |
| `FOUNDRY_MODEL_DEPLOYMENT` | Model deployment name in that project |
| `INVESTIGATION_TIMEOUT_SECONDS` | Total budget per investigation (default 60) |
| `SIMULATION_MAX_ROLLOUTS` | Cap per action (default 200) |

Authentication uses Microsoft Entra ID only, through `ChainedTokenCredential(EnvironmentCredential(), AzureCliCredential())`: `az login` locally, or a service principal in a deployment. No API keys. Secrets stay server-side and are never exposed to the frontend. A local `.env` at the repo root is loaded if present and is git-ignored.

## Versions (as installed and tested)

agent-framework-core 1.23.0, agent-framework-foundry 1.15.0, agent-framework-openai 1.17.0, azure-ai-projects 2.7.0, azure-identity 1.27.0, FastAPI 0.162.0, Pydantic 2.14.1, NumPy 2.5.4, Python 3.12.10. Frontend: React 19.3.1, Mantine 9.7.4, Vite 8.3.5, TypeScript 7.0.2. The full lock files are `backend/requirements.lock` and `frontend/package-lock.json`.

## Source documentation used

- Agent Framework: Your first agent (Python): https://learn.microsoft.com/en-us/agent-framework/get-started/your-first-agent?pivots=programming-language-python. Source of `Agent`, `FoundryChatClient(project_endpoint=, model=, credential=)` and `AzureCliCredential`.
- Agent Framework: Add tools: https://learn.microsoft.com/en-us/agent-framework/get-started/add-tools?pivots=programming-language-python. Source of the `@tool(approval_mode="never_require")` pattern.
- Installed SDK signatures were checked directly: `Agent.__init__`, `Agent.run(options=...)`, `ChatOptions.response_format`, `FunctionInvocationConfiguration`, `BaseChatClient._inner_get_response`.
- Vercel Services and the FastAPI runtime: https://vercel.com/docs/services and https://vercel.com/docs/frameworks/backend/fastapi.

## Known architectural limits

- The investigation registry is in-process: one worker, a capacity of 64, 30-minute expiry, lost on restart. Multi-instance hosting would need shared storage. On Vercel, Foundry mode would need the registry moved to storage, or the investigation run inside the request.
- The offline router is keyword-based.
- The simulator is uncalibrated against real football (see MODEL_CARD).
