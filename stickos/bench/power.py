"""
USB lab bench for StickOS — host may supply ONLY power (VBUS).

Allowed host actions:
  - apply_vbus() / remove_vbus()  — 5V power rail
  - optional uart_probe()         — passive listen on StickCPU TX (debug)

Forbidden:
  - interpreting SAY / Stick opcodes
  - calling stickos.vm
  - feeding programs into the stick after power-on
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path


FIRMWARE = Path(__file__).resolve().parents[1] / "native" / "stickcpu"


@dataclass
class BenchLog:
    vbus: bool = False
    uart_lines: list[str] = field(default_factory=list)
    exit_code: int | None = None
    powered_ms: float = 0.0


class UsbPowerBench:
    """Simulates a USB port that only provides VBUS (+ optional UART sniff)."""

    def __init__(self, firmware: Path = FIRMWARE):
        self.firmware = firmware
        self.log = BenchLog()
        self._proc: subprocess.Popen[str] | None = None

    def apply_vbus(self) -> BenchLog:
        """Plug in: 5V only. StickCPU cold-resets and runs its own flash."""
        if not self.firmware.is_file():
            raise FileNotFoundError(
                f"StickCPU firmware missing: {self.firmware} (build silicon first)"
            )
        if self._proc is not None:
            raise RuntimeError("VBUS already applied")

        self.log = BenchLog(vbus=True)
        t0 = time.perf_counter()
        # No stdin program stream. No host opcodes. Power only → MCU runs.
        self._proc = subprocess.Popen(
            [str(self.firmware)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        assert self._proc.stdout is not None
        try:
            for line in self._proc.stdout:
                self.log.uart_lines.append(line.rstrip("\n"))
            self.log.exit_code = self._proc.wait()
        finally:
            if self._proc.stdout is not None:
                self._proc.stdout.close()
            self._proc = None
        self.log.powered_ms = (time.perf_counter() - t0) * 1000.0
        self.log.vbus = False  # unplugged after autonomous halt
        return self.log

    def remove_vbus(self) -> None:
        if self._proc is not None:
            self._proc.kill()
            self._proc = None
            self.log.vbus = False


def uart_transcript(log: BenchLog) -> str:
    return "\n".join(log.uart_lines)
