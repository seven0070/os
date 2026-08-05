#!/usr/bin/env python3
"""
StickOS simulator — invent, build, boot, and prove a kilobyte pendrive OS.

Runs until the native image is kilobyte-scale and all boot + demo programs halt cleanly.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))

from stickos.image import build_from_rom, build_image  # noqa: E402
from stickos.say_compile import compile_say  # noqa: E402
from stickos.vm import StickImage, StickVM  # noqa: E402


def kb(n: int) -> str:
    return f"{n} B ({n / 1024:.2f} KB)"


def run_image(img: StickImage, label: str, quiet: bool = False) -> bool:
    lines: list[str] = []

    def on_line(s: str) -> None:
        lines.append(s)
        if not quiet:
            print(f"  | {s}")

    if not quiet:
        print(f"\n== {label} ==")
    vm = StickVM(img, on_line=on_line)
    result = vm.run()
    if not quiet:
        print(f"  => {'OK' if result.ok else 'FAIL'}  reason={result.halt_reason}")
    return result.ok


def run_say_file(path: Path, files: dict[str, bytes] | None = None, quiet: bool = False) -> bool:
    src = path.read_text(encoding="utf-8")
    img = build_image(src, files=files or {}, mem_kb=64, version=1, banner="StickOS/demo")
    return run_image(img, f"demo {path.name}", quiet=quiet)


def simulate(until_ok: bool = True, max_rounds: int = 8) -> int:
    rom = ROOT / "rom"
    native = ROOT / "native" / "stickos.stk"
    demos = ROOT / "demos"

    print("StickOS — kilobyte pendrive OS simulation")
    print("native language: SAY (english words → 1-byte opcodes)")

    for round_i in range(1, max_rounds + 1):
        print(f"\n######## simulation round {round_i} ########")
        img, blob = build_from_rom(rom, out_path=native)
        size = len(blob)
        print(f"native image: {native}")
        print(f"native size:  {kb(size)}")
        print(f"code section: {kb(len(img.code))}")
        print(f"strings:      {len(img.strings)}  files: {len(img.files)}")

        size_ok = size < 64 * 1024 and size > 0  # must be kilobyte-class, under 64KB
        # Prefer truly small: report and require < 8KB for "kilobyte native"
        kilo_ok = size <= 8 * 1024

        boot_ok = run_image(img, "kernel boot")
        demo_ok = True
        for demo in sorted(demos.glob("*.say")):
            if not run_say_file(demo, files=dict(img.files)):
                demo_ok = False

        # reload from disk to prove image round-trips
        loaded = StickImage.from_bytes(native.read_bytes())
        reload_ok = run_image(loaded, "reload native stickos.stk", quiet=False)

        print("\n-- round verdict --")
        print(f"  size_ok   = {size_ok}  (raw {size} bytes)")
        print(f"  kilo_ok   = {kilo_ok}  (target ≤ 8 KB)")
        print(f"  boot_ok   = {boot_ok}")
        print(f"  demo_ok   = {demo_ok}")
        print(f"  reload_ok = {reload_ok}")

        done = size_ok and kilo_ok and boot_ok and demo_ok and reload_ok
        if done:
            print("\nSUCCESS: StickOS native image is kilobyte-scale and simulation passed.")
            print(f"  Image: {native}  ({kb(size)})")
            return 0
        if not until_ok:
            return 1
        print("not done yet — adjusting and retrying...")
        # If somehow too big, we would strip; for now failure is logic not size.

    print("FAILED: exceeded simulation rounds without success")
    return 1


def repl_compile(source: str) -> None:
    c = compile_say(source)
    print(f"bytecode {len(c.code)} B  slots={c.slots}  strings={c.strings}")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="StickOS kilobyte pendrive OS simulator")
    p.add_argument("--once", action="store_true", help="single round, no retry loop")
    p.add_argument("--build-only", action="store_true", help="only build native image")
    args = p.parse_args(argv)

    if args.build_only:
        rom = ROOT / "rom"
        native = ROOT / "native" / "stickos.stk"
        img, blob = build_from_rom(rom, out_path=native)
        print(f"built {native} — {kb(len(blob))}")
        return 0

    return simulate(until_ok=not args.once)


if __name__ == "__main__":
    raise SystemExit(main())
