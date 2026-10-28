"""Small live benchmark of the on-device agent workflow, through the running app's HTTP API.

Start the backend with SECOND_LOOK_MODE=foundry_local first. Each question runs as a fresh
investigation, one at a time; results go to docs/live_results.json and are summarised in
docs/EVALUATION.md by scripts/evaluate.py.

    python scripts/live_benchmark.py [base_url] [runs_of_the_pressing_question]
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
RUNS = int(sys.argv[2]) if len(sys.argv) > 2 else 4
PRESS = "Should the right-back have pressed earlier?"
QUESTIONS = [PRESS] * RUNS + ["What passing options did Harbor's #11 have?", "Should Kiprono make a run or hold?"]


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body else None, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main() -> None:
    caps = call("GET", "/api/capabilities")[1]
    rows = []
    for q in QUESTIONS:
        t0 = time.time()
        _, s = call("POST", "/api/investigations?scenario_id=rb_press_hero", {"question": q})
        while s.get("status") not in ("complete", "failed") and time.time() - t0 < 420:
            time.sleep(3)
            _, s = call("GET", f"/api/investigations/{s['investigation_id']}")
        trace = s.get("trace", [])
        exports = {a: call("GET", f"/api/investigations/{s['investigation_id']}/export?audience={a}")[0] == 200 for a in ("analyst", "casual")}
        row = {
            "question": q,
            "status": s.get("status"),
            "outcome": s.get("outcome"),
            "provider_mode": s.get("provider_mode"),
            "elapsed_s": round((s.get("elapsed_ms") or 0) / 1000, 1),
            "model_calls": s.get("model_calls"),
            "tool_calls": s.get("tool_calls"),
            "claims": len(s.get("claims", [])),
            "rejected": len(s.get("rejected_claims", [])),
            "repairs": sum(1 for t in trace if t["kind"] == "repair"),
            "fallback": s.get("provider_mode") == "fallback",
            "reversal_search_ran": any(t.get("tool") == "search_reversal" for t in trace),
            "verdict_shown": any(c["fact_ids"] and c["fact_ids"][0].startswith("sim_verdict") for c in s.get("claims", [])),
            "exports_ok": exports,
            "errors": s.get("errors", []),
        }
        rows.append(row)
        print(json.dumps(row), flush=True)
    out = {"run_at": datetime.now(timezone.utc).isoformat(timespec="minutes"), "provider": caps.get("provider_label"), "runs": rows}
    (ROOT / "docs" / "live_results.json").write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
