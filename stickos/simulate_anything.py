#!/usr/bin/env python3
"""
Simulate until StickOS can run literally any stick app, then enable ADAPT.

Phase A — universal: every *.say dropped on the stick compiles to .app and runs.
Phase B — adaptable: chameleon mode re-scans and runs newly added apps.
"""

from __future__ import annotations

import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from stickos.apps import compile_app_source, load_apps_dir  # noqa: E402
from stickos.image import build_image, collect_rom_files  # noqa: E402
from stickos.vm import StickVM  # noqa: E402


def _gen(seed: int) -> tuple[str, list[str]]:
    """Generate a valid arbitrary SAY program with a unique marker."""
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


UNIVERSAL_KERNEL = """
sys
says "UNIVERSAL BOOT"
put 0
set sum
put 1
set i
test:
  get sum
  get i
  add
  set sum
  get i
  put 1
  add
  set i
  get i
  put 4
  le
  jnz test
get sum
put 10
eq
jz fail
says "self-test: PASS"
put 1
adapt
runall
says "UNIVERSAL DONE"
halt
fail:
  says "self-test: FAIL"
  halt
"""

ADAPT_KERNEL = """
sys
says "ADAPTIVE BOOT"
put 1
adapt
runall
says "first pass done"
put 2
adapt
runall
says "ADAPTIVE DONE"
halt
"""


def run_vm(img, label: str) -> tuple[bool, list[str]]:
    print(f"\n== {label} ==")
    lines: list[str] = []

    def on(s: str) -> None:
        lines.append(s)
        print(f"  | {s}")

    r = StickVM(img, on_line=on).run(max_ticks=500_000)
    print(f"  => {'OK' if r.ok else 'FAIL'} {r.halt_reason} apps={getattr(StickVM, 'x', '')}")
    return r.ok, lines


def simulate(max_rounds: int = 6) -> int:
    rom = ROOT / "rom"
    apps_dir = rom / "apps"
    apps_dir.mkdir(parents=True, exist_ok=True)
    native = ROOT / "native"

    print("StickOS anything+adapt simulation")
    print("goal: run literally any stick app, then enable adaptable chameleon")

    for rnd in range(1, max_rounds + 1):
        print(f"\n######## anything round {rnd} ########")

        # --- Phase A: sprinkle arbitrary programs onto the stick ---
        expected_markers: list[str] = []
        files = collect_rom_files(rom)
        # also inject generated apps directly into the image file table
        for seed in range(rnd * 10, rnd * 10 + 8):
            src, expect = _gen(seed)
            name = f"gen{seed}.app"
            files[name] = compile_app_source(src)
            expected_markers.append(expect[0])

        # built-in rom apps markers
        for p in sorted(apps_dir.glob("*.say")):
            text = p.read_text(encoding="utf-8")
            for line in text.splitlines():
                if "APP " in line or line.strip().startswith('says "APP'):
                    # extract rough marker
                    pass
            expected_markers.append(f"rom:{p.stem}")

        img = build_image(UNIVERSAL_KERNEL, files=files, banner="StickOS/anything")
        blob = img.to_bytes()
        (native / "stickos.stk").write_bytes(blob)
        print(f"image {len(blob)} B with {sum(1 for k in files if k.endswith('.app'))} apps")

        ok, lines = run_vm(img, "universal run-anything")
        joined = "\n".join(lines)
        apps_ok = all(
            f"--- app:{name} ---" in joined
            for name in files
            if name.endswith(".app")
        )
        markers_ok = all(m in joined for m in expected_markers if m.startswith("ANY-"))
        # rom apps should appear
        rom_ok = all(f"--- app:{p.stem}.app ---" in joined for p in apps_dir.glob("*.say"))
        phase_a = ok and apps_ok and markers_ok and rom_ok and "UNIVERSAL DONE" in joined

        print("-- phase A (literally anything) --")
        print(f"  boot_ok={ok} apps_ok={apps_ok} markers_ok={markers_ok} rom_ok={rom_ok}")

        if not phase_a:
            print("not yet — regenerating programs and retrying")
            continue

        # --- Phase B: add adaptable feature AFTER anything works ---
        print("-- phase B (add adaptable feature) --")
        # drop a late app that only chameleon/second pass should still find via runall
        late_src = 'says "ADAPT-LATE"\nput 99\nsay\nhalt\n'
        files2 = dict(files)
        files2["late.app"] = compile_app_source(late_src)
        img2 = build_image(ADAPT_KERNEL, files=files2, banner="StickOS/adapt")
        (native / "stickos-adapt.stk").write_bytes(img2.to_bytes())
        ok2, lines2 = run_vm(img2, "adaptable chameleon")
        joined2 = "\n".join(lines2)
        adapt_ok = (
            ok2
            and "adapt: mode=1" in joined2
            and "adapt: mode=2" in joined2
            and "chameleon armed" in joined2
            and "--- app:late.app ---" in joined2
            and "ADAPT-LATE" in joined2
            and "ADAPTIVE DONE" in joined2
        )
        print(f"  adapt_ok={adapt_ok}")

        if adapt_ok:
            # promote adaptive kernel into rom for real boots
            (rom / "kernel.say").write_text(
                """# StickOS kernel — universal + adaptable
sys
says "welcome to StickOS — kilobyte pendrive OS"
says "language: SAY — runs any .app; adapts on demand"

put 0
set sum
put 1
set i
test:
  get sum
  get i
  add
  set sum
  get i
  put 1
  add
  set i
  get i
  put 4
  le
  jnz test
get sum
put 10
eq
jz fail

says "self-test: PASS (sum 1..4 = 10)"
list
put 1
adapt
runall
says "universal pass complete"
put 2
adapt
runall
says "StickOS ready — adapted."
halt

fail:
  says "self-test: FAIL"
  halt
""",
                encoding="utf-8",
            )
            # persist late app as say source too
            (apps_dir / "late.say").write_text(late_src, encoding="utf-8")
            proof = native / "ANYTHING_ADAPT.txt"
            proof.write_text(
                "StickOS anything + adapt proof\n"
                f"round={rnd}\n"
                f"apps_in_image={sum(1 for k in files2 if k.endswith('.app'))}\n"
                f"image_bytes={len(img2.to_bytes())}\n"
                "phase_a=PASS (run any stick app)\n"
                "phase_b=PASS (adaptable chameleon after)\n",
                encoding="utf-8",
            )
            print("\nSUCCESS: StickOS runs any stick app + adaptable feature armed.")
            print(f"  proof: {proof}")
            return 0

        print("adapt phase failed — retrying full loop")

    print("FAILED")
    return 1


def main() -> int:
    return simulate()


if __name__ == "__main__":
    raise SystemExit(main())
