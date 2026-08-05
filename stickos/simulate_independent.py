#!/usr/bin/env python3
"""
Independence simulation — loop until StickOS runs on StickCPU with host = VBUS only.

Phases:
  1. Manufacture: flash .stk into StickCPU firmware (host tools OK here)
  2. Purge: unload host Stick interpreters from this process
  3. Power: USB bench applies VBUS only; firmware runs alone
  4. Audit: prove bench never used host VM; UART shows autonomous boot
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))


def purge_host_interpreters() -> None:
    doomed = [
        name
        for name in list(sys.modules)
        if name == "stickos.vm"
        or name.startswith("stickos.vm.")
        or name == "stickos.say_compile"
        or name == "stickos.simulate"
        or name == "stickos.opcodes"
        or name == "stickos.image"
    ]
    for name in doomed:
        del sys.modules[name]


def simulate(max_rounds: int = 8) -> int:
    from stickos.bench.independence import (
        assert_uart_autonomous,
        audit_bench_source,
        audit_runtime_modules,
    )
    from stickos.bench.power import UsbPowerBench, uart_transcript
    from stickos.silicon.build_fw import build

    print("StickOS independence simulation")
    print("goal: host supplies USB power (VBUS) only; StickCPU runs alone")

    for round_i in range(1, max_rounds + 1):
        print(f"\n######## independence round {round_i} ########")

        print("-- manufacture: flash ROM into StickCPU --")
        fw = build()
        stk = ROOT / "native" / "stickos.stk"
        print(f"  firmware: {fw}")
        print(f"  ROM image: {stk} ({stk.stat().st_size} B)")

        print("-- purge host interpreters --")
        purge_host_interpreters()
        leftover = audit_runtime_modules()
        if leftover:
            print("  still loaded:", leftover)
        else:
            print("  host Stick VM modules cleared")

        print("-- audit bench source (must be power-only) --")
        src_errs = audit_bench_source()
        if src_errs:
            print("  FAIL source audit:", src_errs)
            continue
        print("  bench imports clean")

        print("-- apply VBUS (power only) --")
        bench = UsbPowerBench(firmware=fw)
        log = bench.apply_vbus()
        print(f"  powered_ms={log.powered_ms:.1f}  exit={log.exit_code}")
        print("  UART TX (passive probe):")
        for line in log.uart_lines:
            print(f"    | {line}")

        print("-- audit autonomy --")
        uart_errs = assert_uart_autonomous(log.uart_lines)
        rt_errs = audit_runtime_modules()
        # power path must not have re-imported interpreters
        ok = (
            not src_errs
            and not uart_errs
            and not rt_errs
            and log.exit_code == 0
        )

        print("  uart_ok   =", not uart_errs, uart_errs or "")
        print("  runtime_ok=", not rt_errs, rt_errs or "")
        print("  exit_ok   =", log.exit_code == 0)

        if ok:
            print("\nSUCCESS: StickOS is independent — host used as VBUS only.")
            print("  StickCPU firmware executed StickOS from its own flash.")
            print("  No host-side opcode interpreter participated in the run.")
            # write proof artifact
            proof = ROOT / "native" / "INDEPENDENCE.txt"
            proof.write_text(
                "StickOS independence proof\n"
                "==========================\n"
                "Host role: USB VBUS (5V) power supply only.\n"
                "Execution: StickCPU firmware (native/stickcpu)\n"
                f"ROM: native/stickos.stk ({stk.stat().st_size} bytes)\n"
                f"exit_code: {log.exit_code}\n"
                f"powered_ms: {log.powered_ms:.2f}\n"
                "\nUART transcript:\n"
                + uart_transcript(log)
                + "\n",
                encoding="utf-8",
            )
            print(f"  proof: {proof}")
            return 0

        print("not independent yet — retrying...")

    print("FAILED: could not prove VBUS-only independence")
    return 1


def main(argv: list[str] | None = None) -> int:
    return simulate()


if __name__ == "__main__":
    raise SystemExit(main())
