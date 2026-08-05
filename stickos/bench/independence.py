"""Prove StickOS independence: host supplies VBUS only."""

from __future__ import annotations

import ast
import importlib
import sys
from pathlib import Path

BENCH_DIR = Path(__file__).resolve().parent
FORBIDDEN_IMPORTS = {
    "stickos.vm",
    "stickos.say_compile",
    "stickos.image",
    "stickos.opcodes",
    "stickos.simulate",
}


def audit_bench_source() -> list[str]:
    """Bench Python must not import the host-side Stick interpreter."""
    errors: list[str] = []
    for path in BENCH_DIR.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in FORBIDDEN_IMPORTS or alias.name.startswith("stickos."):
                        if alias.name != "stickos.bench" and not alias.name.startswith(
                            "stickos.bench."
                        ):
                            errors.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                if mod in FORBIDDEN_IMPORTS or (
                    mod.startswith("stickos.")
                    and not mod.startswith("stickos.bench")
                    and mod != "stickos"
                ):
                    # allow nothing from stickos.vm etc.
                    if mod in FORBIDDEN_IMPORTS or mod.startswith(
                        ("stickos.vm", "stickos.say", "stickos.image", "stickos.opcodes", "stickos.simulate", "stickos.silicon")
                    ):
                        errors.append(f"{path.name}: from {mod}")
    return errors


def audit_runtime_modules() -> list[str]:
    """After power path, host Stick VM modules must not be loaded."""
    bad = []
    for name in FORBIDDEN_IMPORTS:
        if name in sys.modules:
            bad.append(f"loaded in host: {name}")
    return bad


def assert_uart_autonomous(lines: list[str]) -> list[str]:
    errors = []
    joined = "\n".join(lines)
    if "POWER: VBUS only" not in joined:
        errors.append("missing VBUS autonomy banner from firmware")
    if "StickOS ready." not in joined:
        errors.append("firmware did not reach ready state")
    if "self-test: PASS" not in joined:
        errors.append("firmware self-test did not pass")
    if "--- halt: halt" not in joined:
        errors.append("firmware did not halt cleanly")
    return errors
