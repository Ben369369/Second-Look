# Data card: Second Look synthetic sequences

## What this is

These are short synthetic football sequences produced by a seeded, rule-based kinematic simulator (`backend/app/data/generator.py`, generator version `0.1.0`). **Nothing is recorded from a real match.** Teams (Cedar FC, Harbor FC) and player names are invented. In this app, "observed" means *present in the synthetic recording*.

## Fixtures

| scenario_id | Seed | Duration | Frames | Events | Availability |
|---|---|---|---|---|---|
| `rb_press_hero` | 20261025 | 21.9 s | 220 @ 10 Hz | 26 | full-tracking |

Each fixture directory contains `manifest.json`, `tracking.json`, and `events.json`. The manifest's `dataset_hash` (SHA-256 of canonical frames and events) is checked on load.

`rb_press_hero` follows Harbor FC as they circulate from the right centre-back to the left flank. Cedar's right-back (#2) holds off the winger (#11), then presses about 1.4 s after the winger receives. The winger plays inside to #8, who finds the striker (#9), and the striker's shot is saved.

## Conventions

- Pitch 105 × 68 m. Coordinates are in metres: x along the length, y across the width, origin at a corner.
- Period 2: Harbor FC attacks +x, and Cedar FC attacks −x (defending the goal at x = 105). Cedar's right flank and Harbor's left flank are at high y.
- `frame_id` is the frame index from 0, so a frame's time is `frame_id / frame_rate_hz`. The cutoff view relies on this to judge event completion when no tracking is present.
- `time_s` is seconds from sequence start. Match clock = `match_clock_offset_s` + `time_s` (63:12 at t = 0).
- All 22 players and the ball are present in every frame. The ball is on the ground (z = 0).
- The renderer interpolates between frames at display rate. Interpolated positions are not observations, and possession is never interpolated.

## How it is generated

- Players steer toward targets with maximum acceleration 4.5 m/s², a per-player top speed of 7–8 m/s (goalkeepers 6 m/s), and 6 m/s while dribbling.
- On-ball actions follow a fixed script (carry → pass → … → shot). Meeting points and pass speeds get seeded jitter. Off-ball movement and **all defending** come from policies that react to the live state: team shape shifting with the ball, the right-back holding off and then pressing, cover and tracking runs.
- Passes are ground passes at constant speed toward a meeting point. The flight time is stretched if the receiver needs longer to arrive. A reception occurs when the ball has arrived and the receiver is within 1 m.
- Events are emitted from state transitions: pass, reception, carry (≥ 1 m displacement), shot, and pressure_start/end. Pressure starts when the nearest outfield opponent is within 3 m of the carrier and ends beyond 4 m or on release. Goals would be derived from shot outcome, but none occurs here.
- Validation (`backend/app/data/validation.py`) runs on every load and in tests. It checks pitch bounds, speed ≤ 9 m/s, acceleration ≤ 6 m/s², ball speed ≤ 35 m/s, strictly increasing uniform timestamps, the ball within 1 m of the recorded possessor, and that every gain of possession follows a reception or saved-shot event.

## Known limitations

- Ground passes only, at constant ball speed. There is no aerial play, spin, or deflection.
- Offside is not modelled. Body orientation is not generated.
- The ball-carrier's script is fixed. Only off-ball and defensive behavior reacts to state, so the recorded sequence is one illustrative trajectory, not a sample from a calibrated model of real football.
- Pressure thresholds (3 m / 4 m) are prototype conventions.
- Only one sequence family exists so far. Variants (`press_with_cover`, `press_without_cover`, decoy, insufficient tracking) arrive in later stages.
