"""StickOS APP1 packs — any SAY program becomes a runnable stick app."""

from __future__ import annotations

import struct
from pathlib import Path

from .say_compile import CompileResult, compile_say

APP_MAGIC = b"APP1"


def pack_app(compiled: CompileResult) -> bytes:
    out = bytearray(APP_MAGIC)
    out += struct.pack("<H", len(compiled.code))
    out += struct.pack("<H", len(compiled.strings))
    out += compiled.code
    for s in compiled.strings:
        raw = s.encode("utf-8")
        out += struct.pack("<H", len(raw))
        out += raw
    return bytes(out)


def unpack_app(blob: bytes) -> tuple[bytes, list[str]]:
    if len(blob) < 8 or blob[:4] != APP_MAGIC:
        raise ValueError("not an APP1 blob")
    code_len = struct.unpack_from("<H", blob, 4)[0]
    str_count = struct.unpack_from("<H", blob, 6)[0]
    off = 8
    code = blob[off : off + code_len]
    off += code_len
    strings: list[str] = []
    for _ in range(str_count):
        n = struct.unpack_from("<H", blob, off)[0]
        off += 2
        strings.append(blob[off : off + n].decode("utf-8", "replace"))
        off += n
    return code, strings


def compile_app_source(source: str) -> bytes:
    return pack_app(compile_say(source))


def load_apps_dir(apps_dir: Path) -> dict[str, bytes]:
    """Compile every *.say in apps_dir into name.app stick files."""
    files: dict[str, bytes] = {}
    if not apps_dir.is_dir():
        return files
    for path in sorted(apps_dir.glob("*.say")):
        blob = compile_app_source(path.read_text(encoding="utf-8"))
        files[path.stem + ".app"] = blob
    return files
