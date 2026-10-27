# Demo script (target 1:50, hard limit under 2:00)

Two takes, one edit. Everything shown is real, working software.

- **Take A, the hosted site** (https://second-look-dusky.vercel.app): offline mode, every click is instant.
- **Take B, the local app** with `SECOND_LOOK_MODE=foundry_local`: the four agents running on-device with Foundry Local (`qwen3-8b`). One answer takes 1–3 minutes; speed the wait up in the edit and **label it on screen**.

Browser window about 1600×1000, zoom 100%, bookmarks bar hidden, notifications off. Before Take B, ask one warm-up question so the model is loaded, then refresh.

| Time | Take | On screen | Say (suggested) |
|---|---|---|---|
| 0:00–0:15 | A | **The press** opens on the question, "71 of 200", and the pitch frozen with the 8.5 m gap drawn. | "Should the right-back have pressed earlier? Fans argue about this every week. Second Look replays the next eight seconds two hundred times for each choice. Pressing earlier lets Harbor into a dangerous position in 71 of 200. Holding: 30." |
| 0:15–0:38 | A | **Three choices.** The verdict line and the three counts. Drag **Cover delay** from 0.6 s to 1.2 s; wait for "updating" to clear and let the headline change to "Holding position is the clear call". | "With a teammate covering the inside pass it's too close to call, under a rule we fixed before any run. Make that cover arrive half a second later and holding becomes the clear call. The answer depends on that assumption, so the app shows it instead of hiding it." |
| 0:38–0:45 | A | Under **Try to flip it**, click **Run stress test** and show the sentence above the grid. | "A challenger searches a grid of assumptions for settings that flip the answer." |
| 0:45–1:15 | B | **The argument**, Analyst view. Ask the pressing question; show "planning…". Cut with the label **"≈2 min later — sped up"**. Show the badge **AI agents · on-device · qwen3-8b**, then expand **How this answer was made** and scroll to a validator line that **rejected** a claim. | "Here the same question goes to four Microsoft Agent Framework agents, a planner, an evidence analyst, a challenger and a producer, running on this laptop with Foundry Local. The agents choose the evidence and explain it, but code writes every number. When the producer wrote a claim the numbers don't support, the validator rejected it and showed why." |
| 1:15–1:27 | B | Switch to **Fan view**. It changes instantly. | "Same facts for a fan: plain words, the caveat attached, nothing re-run." |
| 1:27–1:48 | A or B | **On air.** Click **Play recap** and let a card appear on the pitch, ending on the SIMULATION card. | "And for a broadcast desk, the answer becomes timed cards on the replay. Every card cites a fact, and simulations stay labelled. Illustrative, not a prediction: an argument with its assumptions out in the open." |

If an on-device run happens to have no rejected claim, show the validator line ("N claims approved, M rejected") and say "a validator checks every claim" instead of describing a rejection.

**Don't:**
- say the hosted site uses a live model, or call the on-device model "cloud Foundry";
- claim personalization, real-time analysis, multiple languages, real players or real-match accuracy;
- hide the on-device wait or the "updating" state; label any speed-up;
- use club logos, real footage or copyrighted music;
- end on the JSON download.

**Upload:** YouTube, visibility **Public**. Title: *Second Look — the football argument, with its assumptions on the pitch*. Description: the first paragraph of `docs/SUBMISSION.md`, then the repo and live-demo links. Check that it plays in a signed-out window.
