# Codex Hook Trust Eval

`run-codex-hook-trust-smoke.py` tests the repo-controlled half of issue #89:

- every project hook definition carries the current referenced-script bundle SHA;
- missing runtime receipt is reported as `UNTRUSTED_OR_NOT_LOADED`;
- a SessionStart-style receipt matching the current bundle reports `TRUSTED_AND_LOADED`;
- changing a referenced hook invalidates the bundle and the old receipt.

This synthetic eval does **not** claim that Codex trusted the repo. Final runtime evidence still
requires a human to review hooks with `/hooks`, exit, and start a fresh Codex session.
