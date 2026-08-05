"""Build a StickOS native pendrive image (target: kilobytes)."""

from __future__ import annotations

from pathlib import Path

from .apps import load_apps_dir
from .say_compile import compile_say
from .vm import StickImage


BANNER = "StickOS"


def build_image(
    kernel_source: str,
    files: dict[str, bytes] | None = None,
    mem_kb: int = 64,
    version: int = 1,
    banner: str = BANNER,
) -> StickImage:
    compiled = compile_say(kernel_source)
    return StickImage(
        version=version,
        mem_kb=mem_kb,
        entry=0,
        code=compiled.code,
        strings=compiled.strings,
        files=files or {},
        banner=banner,
    )


def collect_rom_files(rom_dir: Path) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    data_dir = rom_dir / "files"
    if data_dir.is_dir():
        for p in data_dir.iterdir():
            if p.is_file():
                files[p.name] = p.read_bytes()
    files.update(load_apps_dir(rom_dir / "apps"))
    return files


def build_from_rom(rom_dir: Path, out_path: Path | None = None) -> tuple[StickImage, bytes]:
    kernel = (rom_dir / "kernel.say").read_text(encoding="utf-8")
    files = collect_rom_files(rom_dir)
    img = build_image(kernel, files=files, mem_kb=64, version=1)
    blob = img.to_bytes()
    if out_path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(blob)
    return img, blob
