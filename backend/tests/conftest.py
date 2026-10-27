"""Keep the test suite hermetic: a developer's .env (e.g. SECOND_LOOK_MODE=foundry_local) must not
send test questions to a real model. Real environment variables win over .env, so setting the mode
here before the app is imported forces offline mode. The live-model test opts in with
SECOND_LOOK_LIVE_TESTS=1 (run it on its own: `pytest -k live`)."""

import os

if os.environ.get("SECOND_LOOK_LIVE_TESTS") != "1":
    os.environ["SECOND_LOOK_MODE"] = "offline"
