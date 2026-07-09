from __future__ import annotations

from project_code import __version__
from eval.metrics import placeholder_metric


def test_placeholder_package_imports() -> None:
    assert __version__


def test_placeholder_metric() -> None:
    assert placeholder_metric(1.0) == 1.0
