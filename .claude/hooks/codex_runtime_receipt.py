#!/usr/bin/env python3
"""Thin SessionStart hook that records observable Codex project-hook loading."""
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    checker = repo / "scripts" / "check-codex-hook-runtime.py"
    os.execv(sys.executable, [sys.executable, str(checker), "--write-receipt"])


if __name__ == "__main__":
    main()
