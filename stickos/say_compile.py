"""SAY — StickOS English programming language compiler.

English-ish stack language. Example:

    put 1
    set a
    put 5
    set n
  loop:
    get a
    say
    get a
    put 1
    add
    set a
    get a
    get n
    less
    jnz loop
    says "done"
    halt
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field

from .opcodes import ENGLISH, OPS


@dataclass
class CompileResult:
    code: bytes
    strings: list[str] = field(default_factory=list)
    labels: dict[str, int] = field(default_factory=dict)
    slots: dict[str, int] = field(default_factory=dict)


_STR = re.compile(r'"([^"\\]*(?:\\.[^"\\]*)*)"')
_NUM = re.compile(r"^-?\d+$")
_LABEL = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):$")
_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _unescape(s: str) -> str:
    return (
        s.replace(r"\\", "\\")
        .replace(r"\"", '"')
        .replace(r"\n", "\n")
        .replace(r"\t", "\t")
    )


def compile_say(source: str) -> CompileResult:
    """Compile SAY source into Stick bytecode + string table."""
    lines = []
    for raw in source.splitlines():
        # strip comments
        if "#" in raw:
            raw = raw.split("#", 1)[0]
        raw = raw.strip()
        if not raw:
            continue
        lines.append(raw)

    labels: dict[str, int] = {}
    slots: dict[str, int] = {}
    strings: list[str] = []
    string_index: dict[str, int] = {}

    def slot_of(name: str) -> int:
        if name not in slots:
            if len(slots) >= 256:
                raise ValueError("too many variables (max 256)")
            slots[name] = len(slots)
        return slots[name]

    def str_of(text: str) -> int:
        if text not in string_index:
            string_index[text] = len(strings)
            strings.append(text)
        return string_index[text]

    # Pass 1: tokenize with unresolved labels
    # Each item is ("op", name, args...) or ("label", name)
    tokens: list[tuple] = []
    for line in lines:
        m = _LABEL.match(line)
        if m:
            tokens.append(("label", m.group(1)))
            continue

        # extract strings first
        parts: list[str] = []
        pos = 0
        for sm in _STR.finditer(line):
            before = line[pos : sm.start()].strip()
            if before:
                parts.extend(before.split())
            parts.append('"' + sm.group(1) + '"')
            pos = sm.end()
        tail = line[pos:].strip()
        if tail:
            parts.extend(tail.split())

        i = 0
        while i < len(parts):
            w = parts[i].lower() if not parts[i].startswith('"') else parts[i]
            if parts[i].startswith('"'):
                raise SyntaxError(f"orphan string: {parts[i]}")

            # sugar: set NAME / get NAME / store NAME / load NAME
            if w in ("set", "store", "get", "load") and i + 1 < len(parts):
                name = parts[i + 1]
                if not _IDENT.match(name):
                    raise SyntaxError(f"bad variable name: {name}")
                op = "STORE" if w in ("set", "store") else "LOAD"
                tokens.append(("op", op, slot_of(name)))
                i += 2
                continue

            # sugar: says "text" or say "text"
            if w in ("says", "say", "print", "speak") and i + 1 < len(parts) and parts[i + 1].startswith('"'):
                text = _unescape(parts[i + 1][1:-1])
                tokens.append(("op", "SAYS", str_of(text)))
                i += 2
                continue

            # sugar: run "app.app"
            if w == "run" and i + 1 < len(parts) and parts[i + 1].startswith('"'):
                text = _unescape(parts[i + 1][1:-1])
                tokens.append(("op", "RUN", str_of(text)))
                i += 2
                continue

            # sugar: put N / push N
            if w in ("put", "push") and i + 1 < len(parts) and _NUM.match(parts[i + 1]):
                tokens.append(("op", "PUSH", int(parts[i + 1])))
                i += 2
                continue

            # jumps / call with label
            if w in ("jump", "goto", "jz", "jnz", "call") and i + 1 < len(parts):
                op = ENGLISH[w]
                tokens.append(("op", op, parts[i + 1]))  # label name
                i += 2
                continue

            if w in ENGLISH:
                tokens.append(("op", ENGLISH[w]))
                i += 1
                continue

            # bare number => PUSH
            if _NUM.match(parts[i]):
                tokens.append(("op", "PUSH", int(parts[i])))
                i += 1
                continue

            # bare ident used as load? treat as load for friendliness
            if _IDENT.match(parts[i]):
                tokens.append(("op", "LOAD", slot_of(parts[i])))
                i += 1
                continue

            raise SyntaxError(f"unknown word: {parts[i]!r}")

    # Pass 2: measure code sizes & resolve label addresses
    def op_size(tok: tuple) -> int:
        if tok[0] == "label":
            return 0
        op = tok[1]
        if op == "PUSH":
            return 3
        if op in ("STORE", "LOAD"):
            return 2
        if op in ("SAYS", "RUN"):
            return 3
        if op in ("JMP", "JZ", "JNZ"):
            return 3
        if op == "CALL":
            return 3
        return 1

    pc = 0
    for tok in tokens:
        if tok[0] == "label":
            labels[tok[1]] = pc
        else:
            pc += op_size(tok)

    # Pass 3: emit
    out = bytearray()
    for tok in tokens:
        if tok[0] == "label":
            continue
        op = tok[1]
        code = OPS[op]
        if op == "PUSH":
            out.append(code)
            out += struct.pack("<h", int(tok[2]))
        elif op in ("STORE", "LOAD"):
            out.append(code)
            out.append(int(tok[2]) & 0xFF)
        elif op in ("SAYS", "RUN"):
            out.append(code)
            out += struct.pack("<H", int(tok[2]))
        elif op in ("JMP", "JZ", "JNZ"):
            target = labels.get(tok[2])
            if target is None:
                raise SyntaxError(f"undefined label: {tok[2]}")
            # relative from after this instruction
            here = len(out)
            rel = target - (here + 3)
            out.append(code)
            out += struct.pack("<h", rel)
        elif op == "CALL":
            target = labels.get(tok[2])
            if target is None:
                raise SyntaxError(f"undefined label: {tok[2]}")
            out.append(code)
            out += struct.pack("<H", target)
        else:
            out.append(code)

    return CompileResult(code=bytes(out), strings=strings, labels=labels, slots=slots)
