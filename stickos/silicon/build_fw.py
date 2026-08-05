#!/usr/bin/env python3
"""Flash StickOS .stk into StickCPU firmware and compile the silicon image.

Host role ends at: produce a binary that lives on the stick.
After flash, the stick runs without host OS services.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SILICON = Path(__file__).resolve().parent
NATIVE = ROOT / "native"


def embed_rom(stk: Path, header: Path) -> int:
    data = stk.read_bytes()
    if data[:4] != b"STK1":
        raise SystemExit(f"not an STK1 image: {stk}")
    lines = [
        "/* Auto-generated — StickOS ROM in StickCPU flash */",
        "#pragma once",
        "#include <stdint.h>",
        f"static const uint32_t stick_rom_len = {len(data)};",
        "static const uint8_t stick_rom[] = {",
    ]
    for i in range(0, len(data), 12):
        chunk = data[i : i + 12]
        lines.append("  " + ", ".join(f"0x{b:02x}" for b in chunk) + ",")
    lines.append("};")
    header.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(data)


def compile_firmware(out: Path) -> None:
    """Compile StickCPU firmware.

    Prefer a static binary so runtime needs no host shared libs — closer to
    on-stick flash. Falls back to dynamic if static libc is unavailable.
    """
    src = SILICON / "stickos_fw.c"
    base = ["gcc", "-O2", "-Wall", "-Wextra", "-o", str(out), str(src)]
    try:
        subprocess.check_call(base[:1] + ["-static"] + base[1:], cwd=str(SILICON))
    except subprocess.CalledProcessError:
        subprocess.check_call(base, cwd=str(SILICON))


def build() -> Path:
    sys.path.insert(0, str(ROOT.parent))
    from stickos.image import build_from_rom

    stk = NATIVE / "stickos.stk"
    build_from_rom(ROOT / "rom", out_path=stk)
    rom_len = embed_rom(stk, SILICON / "rom_image.h")
    fw = NATIVE / "stickcpu"
    compile_firmware(fw)
    print(f"flashed ROM {rom_len} B into StickCPU → {fw}")
    return fw


if __name__ == "__main__":
    build()
