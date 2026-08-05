#!/usr/bin/env python3
"""
Simulate circumstance-driven adapt phases.

Phases are not a fixed 1→2 script: `sense` reads stick circumstances
(app count, free mem, coverage) and chooses idle / universal / chameleon.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from stickos.apps import compile_app_source  # noqa: E402
from stickos.image import build_image, collect_rom_files  # noqa: E402
from stickos.vm import StickVM  # noqa: E402


def _gen(seed: int) -> tuple[str, list[str]]:
    rng = random.Random(seed)
    marker = f"ANY-{seed:04d}"
    kind = rng.choice(["sum", "loop", "msg", "mul"])
    if kind == "sum":
        a, b = rng.randint(1, 20), rng.randint(1, 20)
        src = f'says "{marker}"\nput {a}\nput {b}\nadd\nsay\nhalt\n'
        return src, [marker, str(a + b)]
    if kind == "loop":
        n = rng.randint(2, 4)
        src = (
            f'says "{marker}"\nput 1\nset i\n'
            f"L:\nget i\nsay\nget i\nput 1\nadd\nset i\n"
            f"get i\nput {n}\nle\njnz L\nhalt\n"
        )
        return src, [marker] + [str(i) for i in range(1, n + 1)]
    if kind == "mul":
        a, b = rng.randint(2, 9), rng.randint(2, 9)
        src = f'says "{marker}"\nput {a}\nput {b}\nmul\nsay\nhalt\n'
        return src, [marker, str(a * b)]
    src = f'says "{marker}"\nsays "ok"\nhalt\n'
    return src, [marker, "ok"]


# Kernel that adapts phases from circumstances (same shape as rom/kernel.say)
CIRCUMSTANCE_KERNEL = (ROOT / "rom" / "kernel.say").read_text(encoding="utf-8")

LIGHT_KERNEL = """
sys
says "LIGHT CIRCUMSTANCE BOOT"
says "sensing circumstances..."
sense
dup
adapt
put 0
eq
jnz settle
runall
sense
dup
adapt
put 0
eq
jnz settle
runall
settle:
  says "LIGHT DONE"
  halt
"""


def run_vm(img, label: str) -> tuple[bool, list[str]]:
    print(f"\n== {label} ==")
    lines: list[str] = []

    def on(s: str) -> None:
        lines.append(s)
        print(f"  | {s}")

    r = StickVM(img, on_line=on).run(max_ticks=500_000)
    print(f"  => {'OK' if r.ok else 'FAIL'} {r.halt_reason}")
    return r.ok, lines


def simulate(max_rounds: int = 6) -> int:
    rom = ROOT / "rom"
    apps_dir = rom / "apps"
    apps_dir.mkdir(parents=True, exist_ok=True)
    native = ROOT / "native"

    print("StickOS circumstance-adapt simulation")
    print("goal: phases chosen by sense from live circumstances")

    for rnd in range(1, max_rounds + 1):
        print(f"\n######## circumstance round {rnd} ########")

        # --- Heavy circumstance: many apps → expect chameleon ---
        files = collect_rom_files(rom)
        markers: list[str] = []
        for seed in range(rnd * 10, rnd * 10 + 8):
            src, expect = _gen(seed)
            files[f"gen{seed}.app"] = compile_app_source(src)
            markers.append(expect[0])

        img = build_image(CIRCUMSTANCE_KERNEL, files=files, banner="StickOS/circ")
        (native / "stickos.stk").write_bytes(img.to_bytes())
        ok, lines = run_vm(img, "heavy circumstances")
        joined = "\n".join(lines)
        heavy_ok = (
            ok
            and "sensing circumstances..." in joined
            and "sense:" in joined
            and "heavy load" in joined
            and "adapt: mode=2" in joined
            and "chameleon follow-up" in joined
            and all(m in joined for m in markers)
            and "phases adapted to circumstances" in joined
        )
        print(f"  heavy_ok={heavy_ok}")

        # --- Light circumstance: 1 app only → expect universal, then settle ---
        one = {
            "solo.app": compile_app_source(
                'says "SOLO"\nput 1\nsay\nhalt\n'
            )
        }
        img_l = build_image(LIGHT_KERNEL, files=one, banner="StickOS/light")
        ok_l, lines_l = run_vm(img_l, "light circumstances")
        joined_l = "\n".join(lines_l)
        light_ok = (
            ok_l
            and "light load → universal" in joined_l
            and "adapt: mode=1" in joined_l
            and "circumstances settled" in joined_l
            and "SOLO" in joined_l
            and "LIGHT DONE" in joined_l
        )
        # Should NOT force chameleon on light load
        light_ok = light_ok and "heavy load" not in joined_l
        print(f"  light_ok={light_ok}")

        # --- Empty circumstance: idle ---
        img_e = build_image(LIGHT_KERNEL, files={}, banner="StickOS/empty")
        ok_e, lines_e = run_vm(img_e, "empty circumstances")
        joined_e = "\n".join(lines_e)
        empty_ok = (
            ok_e
            and "no apps → idle" in joined_e
            and "adapt: mode=0" in joined_e
            and "LIGHT DONE" in joined_e
        )
        print(f"  empty_ok={empty_ok}")

        if heavy_ok and light_ok and empty_ok:
            proof = native / "CIRCUMSTANCE_ADAPT.txt"
            proof.write_text(
                "StickOS circumstance-driven phases\n"
                f"round={rnd}\n"
                "heavy → chameleon (mode 2 + follow-up)\n"
                "light → universal (mode 1) then settle\n"
                "empty → idle (mode 0)\n"
                "PASS\n",
                encoding="utf-8",
            )
            print("\nSUCCESS: phases adapt according to circumstances.")
            print(f"  proof: {proof}")
            return 0

        print("not yet — retrying")

    return 1


def main() -> int:
    return simulate()


if __name__ == "__main__":
    raise SystemExit(main())
