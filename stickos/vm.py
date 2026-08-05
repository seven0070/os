"""StickOS virtual machine — simulates a kilobyte pendrive OS."""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import Callable


MAGIC = b"STK1"
MAX_STACK = 256
MAX_CALL = 64
VAR_SLOTS = 256


@dataclass
class StickImage:
    version: int
    mem_kb: int
    entry: int
    code: bytes
    strings: list[str]
    files: dict[str, bytes] = field(default_factory=dict)
    banner: str = "StickOS"

    @classmethod
    def from_bytes(cls, blob: bytes) -> "StickImage":
        if blob[:4] != MAGIC:
            raise ValueError("not a StickOS image")
        version = blob[4]
        mem_kb = blob[5]
        entry = struct.unpack_from("<H", blob, 6)[0]
        code_len = struct.unpack_from("<H", blob, 8)[0]
        str_count = struct.unpack_from("<H", blob, 10)[0]
        file_count = struct.unpack_from("<H", blob, 12)[0]
        banner_len = blob[14]
        off = 15
        banner = blob[off : off + banner_len].decode("utf-8", "replace")
        off += banner_len
        code = blob[off : off + code_len]
        off += code_len
        strings: list[str] = []
        for _ in range(str_count):
            n = struct.unpack_from("<H", blob, off)[0]
            off += 2
            strings.append(blob[off : off + n].decode("utf-8", "replace"))
            off += n
        files: dict[str, bytes] = {}
        for _ in range(file_count):
            nl = blob[off]
            off += 1
            name = blob[off : off + nl].decode("ascii", "replace")
            off += nl
            fl = struct.unpack_from("<H", blob, off)[0]
            off += 2
            files[name] = blob[off : off + fl]
            off += fl
        return cls(
            version=version,
            mem_kb=mem_kb,
            entry=entry,
            code=code,
            strings=strings,
            files=files,
            banner=banner,
        )

    def to_bytes(self) -> bytes:
        out = bytearray()
        out += MAGIC
        out.append(self.version & 0xFF)
        out.append(self.mem_kb & 0xFF)
        out += struct.pack("<H", self.entry)
        out += struct.pack("<H", len(self.code))
        out += struct.pack("<H", len(self.strings))
        out += struct.pack("<H", len(self.files))
        b = self.banner.encode("utf-8")[:255]
        out.append(len(b))
        out += b
        out += self.code
        for s in self.strings:
            raw = s.encode("utf-8")
            out += struct.pack("<H", len(raw))
            out += raw
        for name, data in sorted(self.files.items()):
            nb = name.encode("ascii")[:255]
            out.append(len(nb))
            out += nb
            out += struct.pack("<H", len(data))
            out += data
        return bytes(out)


@dataclass
class VMResult:
    ok: bool
    output: list[str]
    ticks: int
    halt_reason: str
    stack: list[int]


class StickVM:
    """Kilobyte StickOS machine."""

    def __init__(self, image: StickImage, on_line: Callable[[str], None] | None = None):
        self.image = image
        self.code = image.code
        self.strings = image.strings
        self.files = dict(image.files)
        self.stack: list[int] = []
        self.call: list[int] = []
        self.vars = [0] * VAR_SLOTS
        self.pc = image.entry
        self.ticks = 0
        self.halted = False
        self.halt_reason = ""
        self.output: list[str] = []
        self._on_line = on_line
        self.mem_bytes = image.mem_kb * 1024

    def _emit(self, line: str) -> None:
        self.output.append(line)
        if self._on_line:
            self._on_line(line)

    def _push(self, v: int) -> None:
        if len(self.stack) >= MAX_STACK:
            raise RuntimeError("stack overflow")
        self.stack.append(int(v))

    def _pop(self) -> int:
        if not self.stack:
            raise RuntimeError("stack underflow")
        return self.stack.pop()

    def boot(self) -> None:
        self._emit(f"[{self.image.banner}] v{self.image.version}  mem={self.image.mem_kb}KB")
        self._emit(f"stick: {len(self.files)} files  code={len(self.code)}B")
        self._emit("--- boot ---")

    def step(self) -> bool:
        if self.halted:
            return False
        if self.pc < 0 or self.pc >= len(self.code):
            self.halted = True
            self.halt_reason = "pc out of range"
            return False

        op = self.code[self.pc]
        self.pc += 1
        self.ticks += 1

        if op == 0x00:  # HALT
            self.halted = True
            self.halt_reason = "halt"
            return False
        if op == 0x01:  # NOP
            return True
        if op == 0x02:  # PUSH
            val = struct.unpack_from("<h", self.code, self.pc)[0]
            self.pc += 2
            self._push(val)
            return True
        if op == 0x03:  # POP
            self._pop()
            return True
        if op == 0x04:  # DUP
            if not self.stack:
                raise RuntimeError("stack underflow")
            self._push(self.stack[-1])
            return True
        if op == 0x05:  # SWAP
            a, b = self._pop(), self._pop()
            self._push(a)
            self._push(b)
            return True
        if op == 0x06:  # DROP
            self._pop()
            return True
        if op == 0x07:  # ADD
            b, a = self._pop(), self._pop()
            self._push(a + b)
            return True
        if op == 0x08:  # SUB
            b, a = self._pop(), self._pop()
            self._push(a - b)
            return True
        if op == 0x09:  # MUL
            b, a = self._pop(), self._pop()
            self._push(a * b)
            return True
        if op == 0x0A:  # DIV
            b, a = self._pop(), self._pop()
            if b == 0:
                raise RuntimeError("divide by zero")
            self._push(a // b)
            return True
        if op == 0x0B:  # MOD
            b, a = self._pop(), self._pop()
            if b == 0:
                raise RuntimeError("mod by zero")
            self._push(a % b)
            return True
        if op == 0x0C:  # EQ
            b, a = self._pop(), self._pop()
            self._push(1 if a == b else 0)
            return True
        if op == 0x0D:  # NE
            b, a = self._pop(), self._pop()
            self._push(1 if a != b else 0)
            return True
        if op == 0x0E:  # LT
            b, a = self._pop(), self._pop()
            self._push(1 if a < b else 0)
            return True
        if op == 0x0F:  # GT
            b, a = self._pop(), self._pop()
            self._push(1 if a > b else 0)
            return True
        if op == 0x10:  # LE
            b, a = self._pop(), self._pop()
            self._push(1 if a <= b else 0)
            return True
        if op == 0x11:  # GE
            b, a = self._pop(), self._pop()
            self._push(1 if a >= b else 0)
            return True
        if op == 0x12:  # NOT
            self._push(0 if self._pop() else 1)
            return True
        if op == 0x13:  # AND
            b, a = self._pop(), self._pop()
            self._push(1 if (a and b) else 0)
            return True
        if op == 0x14:  # OR
            b, a = self._pop(), self._pop()
            self._push(1 if (a or b) else 0)
            return True
        if op == 0x15:  # STORE
            slot = self.code[self.pc]
            self.pc += 1
            self.vars[slot] = self._pop()
            return True
        if op == 0x16:  # LOAD
            slot = self.code[self.pc]
            self.pc += 1
            self._push(self.vars[slot])
            return True
        if op == 0x17:  # SAY number
            self._emit(str(self._pop()))
            return True
        if op == 0x18:  # SAYS
            idx = struct.unpack_from("<H", self.code, self.pc)[0]
            self.pc += 2
            if idx >= len(self.strings):
                raise RuntimeError(f"bad string index {idx}")
            self._emit(self.strings[idx])
            return True
        if op == 0x19:  # JMP
            rel = struct.unpack_from("<h", self.code, self.pc)[0]
            self.pc += 2
            self.pc += rel
            return True
        if op == 0x1A:  # JZ
            rel = struct.unpack_from("<h", self.code, self.pc)[0]
            self.pc += 2
            if self._pop() == 0:
                self.pc += rel
            return True
        if op == 0x1B:  # JNZ
            rel = struct.unpack_from("<h", self.code, self.pc)[0]
            self.pc += 2
            if self._pop() != 0:
                self.pc += rel
            return True
        if op == 0x1C:  # CALL
            addr = struct.unpack_from("<H", self.code, self.pc)[0]
            self.pc += 2
            if len(self.call) >= MAX_CALL:
                raise RuntimeError("call stack overflow")
            self.call.append(self.pc)
            self.pc = addr
            return True
        if op == 0x1D:  # RET
            if not self.call:
                self.halted = True
                self.halt_reason = "return from empty call"
                return False
            self.pc = self.call.pop()
            return True
        if op == 0x1E:  # READ — push size of named file (name from string idx on stack)
            idx = self._pop()
            name = self.strings[idx] if 0 <= idx < len(self.strings) else ""
            data = self.files.get(name, b"")
            self._push(len(data))
            return True
        if op == 0x1F:  # WRITE — pop size ignored; demo: write marker file
            # stack: str_idx, value  -> store value as one-byte file content marker
            val = self._pop()
            idx = self._pop()
            name = self.strings[idx] if 0 <= idx < len(self.strings) else "out"
            self.files[name] = str(val).encode("utf-8")
            self._push(1)
            return True
        if op == 0x20:  # LIST
            names = ", ".join(sorted(self.files)) or "(empty)"
            self._emit(f"files: {names}")
            self._push(len(self.files))
            return True
        if op == 0x21:  # MEM
            used = len(self.code) + sum(len(v) for v in self.files.values())
            self._push(max(0, self.mem_bytes - used))
            return True
        if op == 0x22:  # TICK
            self._push(self.ticks)
            return True
        if op == 0x23:  # SYS
            self._emit(
                f"StickOS/{self.image.version} SAY-native pendrive  "
                f"image~{self.image.mem_kb}KB arena"
            )
            return True

        raise RuntimeError(f"illegal opcode 0x{op:02x} at {self.pc - 1}")

    def run(self, max_ticks: int = 100_000) -> VMResult:
        self.boot()
        try:
            while not self.halted and self.ticks < max_ticks:
                if not self.step():
                    break
            if not self.halted and self.ticks >= max_ticks:
                self.halted = True
                self.halt_reason = "tick limit"
            ok = self.halt_reason == "halt"
            self._emit(f"--- halt: {self.halt_reason} ({self.ticks} ticks) ---")
            return VMResult(ok=ok, output=self.output, ticks=self.ticks, halt_reason=self.halt_reason, stack=list(self.stack))
        except Exception as e:
            self.halted = True
            self.halt_reason = f"trap: {e}"
            self._emit(f"--- halt: {self.halt_reason} ({self.ticks} ticks) ---")
            return VMResult(ok=False, output=self.output, ticks=self.ticks, halt_reason=self.halt_reason, stack=list(self.stack))
