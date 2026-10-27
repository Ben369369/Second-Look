# Submission draft: Innovation Studio

Project page: https://innovationstudio.microsoft.com/hackathons/insidethegamedeveloperhackathon/project/127073

Recheck the organiser's current rules before submitting. Deadline as reviewed: **27 Oct 2026, 11:59 pm Pacific**. Saving a draft may not count as submitting; confirm the final status in the portal.

## Short description (paste-ready)

**Second Look — put your football opinions on the pitch.**

Football arguments like "should the right-back have pressed earlier?" hide their assumptions. Second Look makes one inspectable.

- **Watch and measure.** You watch a synthetic match sequence and see measured evidence: distances, timings and passing lanes, each computed by code and linked to the moment on the pitch.
- **Compare alternatives.** A transparent rule-based simulator replays the next eight seconds 200 times for each choice (hold, press earlier, press with cover). A recommendation rule fixed in advance reports a clear winner, or "no clear winner".
- **Test the assumptions.** A challenger searches a fixed grid of assumptions (cover timing, attacker style) for settings that change the answer.
- **Agents with a validator.** The investigation is orchestrated with Microsoft Agent Framework (planner, evidence analyst, challenger and producer agents calling the same tools). A deterministic validator rejects any claim whose numbers, players or evidence class don't match its cited facts.
- **Two audiences.** Fans and analysts get different presentations of the same facts, and producers can export a timed overlay.

On 12 held-out synthetic variants it met its predeclared behaviour in 12 of 12 cases: answering when the data supports it, abstaining when there is no pressing moment or no tracking. It rejected 60 of 60 injected fabricated claims.

All data is synthetic, and all teams and players are fictional.

## Microsoft technology (actual use)

| Technology | Status |
|---|---|
| **Microsoft Agent Framework (Python)** | **Used.** `agent-framework-core` 1.23.0 and `agent-framework-foundry` 1.15.0: four `Agent` roles with function tools, typed structured outputs and `FunctionInvocationConfiguration` limits, tested through the real framework loop. |
| **Foundry Local** | **Used, live.** The four Agent Framework agents call `qwen3-8b` running on-device through Foundry Local (CLI 0.12.1), via Agent Framework's `OpenAIChatCompletionClient` (`agent-framework-openai` 1.17.0) pointed at the local server. Live test: 4 model calls, 3 tool calls, 4 claims approved, 0 rejected, about 83 s on an RTX 5070 laptop GPU. Verified in the UI with the trace shown. Runs on the developer's machine only; the public Vercel demo stays offline. |
| **Microsoft Foundry (cloud)** | **Provisioned, model not connected.** A Foundry resource and project (`second-look`, Switzerland North) were created. Every model deployment (gpt-5-mini, gpt-oss-120b, within quota) was blocked by Azure error 715-123420 on the Azure for Students subscription. The cloud path is implemented and tested with scripted replies only; the hosted demo runs in clearly labelled offline mode. |
| **Microsoft Entra ID / azure-identity** | Used for Foundry authentication (CLI and service-principal credentials, no API keys). |
| Azure AI Speech, Container Apps | Not used. |

Hosting is Vercel (not Microsoft).

## Category

Best Multi-Agent Orchestration is the natural fit: distinct agent roles with typed handoffs, a challenger, deterministic validation with a bounded repair, and labelled fallback. Live-model results come from Foundry Local on one laptop (one live smoke run plus UI checks), not a full live evaluation; the cloud model was blocked by the Azure hold. Say so.

## Checklist

- [x] README explains the problem and what is actually implemented.
- [x] Reproducible setup, tested dependency locks, fixture generator, tests; no secrets in the repository (`.env*` ignored and checked before the push).
- [x] Microsoft technology list reflects actual use (above).
- [x] Data card, model card, architecture, evaluation with real counts and omitted checks.
- [ ] Demo video: public, under 2 minutes, permitted assets only (`docs/DEMO_SCRIPT.md`).
- [ ] GitHub repository set to **public** and the final code pushed.
- [ ] Innovation Studio page updated with the description, repository link, video link and live demo link.
- [ ] Links checked while signed out.
- [ ] Final submission status confirmed in the portal.
