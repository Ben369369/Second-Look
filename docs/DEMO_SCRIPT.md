# Demo script: local app with live AI (about 2 minutes)

The whole demo runs on the laptop at http://localhost:5173 with `SECOND_LOOK_MODE=foundry_local`: the four Microsoft Agent Framework agents on `qwen3-8b` through Foundry Local. The press and Three choices respond instantly (simulator, no model). Questions on The argument go to the agents and take one to three minutes, so **start the question first** and spend the wait on the instant pages. The question keeps running while you move between pages (verified: start on The press, visit Three choices, return, then On air).

**Setup (10 minutes before):**
1. `foundry server start`, then `foundry model load qwen3-8b`.
2. Backend: in `backend`, `.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000`. Frontend: in `frontend`, `npm run dev`.
3. The header must read "Foundry Local (on-device) · qwen3-8b · Agent Framework".
4. Warm up: on The argument, click **Pressing decision** once and let it finish. Refresh, then open The press.
5. Browser about 1600×1000, zoom 100%, bookmarks bar hidden, notifications off, other GPU-heavy apps closed.

| Time | Page | On screen | Say (suggested) |
|---|---|---|---|
| 0:00–0:20 | The press | The question, "No. Holding was safer.", 30 vs 71, the orange 8.5 m gap. Click **Investigate this decision**: the question goes to the agents and The argument shows "planning…". | "Should the right-back have pressed earlier? Second Look replays the next eight seconds two hundred times for each choice. If he holds, Harbor reach a dangerous position in 30 of 200. If he presses earlier, 71. Lower is safer: holding wins. I've just handed the same question to four AI agents running on this laptop; they'll take a minute or two." |
| 0:20–0:50 | Three choices | Hold is marked. Drag **Cover delay** 0.6 s → 1.2 s; the headline becomes "Holding position is the clear call". | "With a teammate covering the inside pass it's too close to call, under a rule we fixed before any run. Make that cover arrive 0.6 seconds later and holding becomes the clear call. The answer depends on that assumption, so the app shows it instead of hiding it." |
| 0:50–1:05 | Three choices | **Run stress test**; show the sentence. Optional: **Watch an example** under Press earlier. | "A challenger searches a grid of assumptions for settings that flip the answer. The agents run this same search." |
| 1:05–1:35 | The argument | When it says Answered: the badge **AI agents · on-device · qwen3-8b**; expand **How this answer was made**; scroll to a validator line with rejected claims. | "Four Microsoft Agent Framework agents, a planner, an evidence analyst, a challenger and a producer, running on this laptop with Foundry Local. The agents choose the evidence and order it, but code writes every number. When the producer wrote a claim the numbers don't support, the validator rejected it and showed why." |
| 1:35–1:45 | The argument | Switch to **Fan view** (instant). | "Same facts for a fan: plain words, the caveat attached, nothing re-run." |
| 1:45–2:00 | On air | **Play recap**; end on the SIMULATION card. | "For a broadcast desk, the agents' answer becomes timed cards on the replay. Every card cites a fact, and simulations stay labelled. Illustrative, not a prediction: an argument with its assumptions out in the open." |

**If the answer isn't ready:** play the move on The press, or open "Also in this passage" and click a stat. In a recorded video, cut the remaining wait and label it on screen ("≈1 min later — sped up").

**Extras, only after the main answer finishes** (on-device mode runs one question at a time): "Should Messi press earlier?" (no such player) and "Should Kiprono make a run or hold?" (only the right-back's press can be simulated). Both are refused before any model call, so they are instant.

If a run happens to have no rejected claim, point at the validator line ("N claims approved, M rejected") and say "a validator checks every claim".

**Don't:**
- call the on-device model "cloud Foundry", or say the agents write the explanation (they choose and order the evidence; code writes the facts);
- claim personalization, real-time analysis, multiple languages, real players or real-match accuracy;
- refresh while an answer is running, or hide a wait in a video (label any speed-up);
- use club logos, real footage or copyrighted music.

**Upload:** YouTube, visibility **Public**, under 2:00. Title: *Second Look — the football argument, with its assumptions on the pitch*. Description: the first paragraph of `docs/SUBMISSION.md`, then the repo and live-demo links. Check that it plays in a signed-out window.
