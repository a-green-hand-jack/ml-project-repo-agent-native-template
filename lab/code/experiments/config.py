from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def config_path(name: str = "base.yaml") -> Path:
    return project_root() / "experiments" / "configs" / name
