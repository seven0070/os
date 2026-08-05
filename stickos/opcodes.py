"""StickOS opcode table — each instruction is one byte."""

from __future__ import annotations

# mnemonic -> opcode
OPS: dict[str, int] = {
    "HALT": 0x00,
    "NOP": 0x01,
    "PUSH": 0x02,  # i16 immediate follows
    "POP": 0x03,
    "DUP": 0x04,
    "SWAP": 0x05,
    "DROP": 0x06,
    "ADD": 0x07,
    "SUB": 0x08,
    "MUL": 0x09,
    "DIV": 0x0A,
    "MOD": 0x0B,
    "EQ": 0x0C,
    "NE": 0x0D,
    "LT": 0x0E,
    "GT": 0x0F,
    "LE": 0x10,
    "GE": 0x11,
    "NOT": 0x12,
    "AND": 0x13,
    "OR": 0x14,
    "STORE": 0x15,  # u8 slot
    "LOAD": 0x16,  # u8 slot
    "SAY": 0x17,
    "SAYS": 0x18,  # u16 string idx
    "JMP": 0x19,  # i16 relative
    "JZ": 0x1A,
    "JNZ": 0x1B,
    "CALL": 0x1C,  # u16 abs
    "RET": 0x1D,
    "READ": 0x1E,
    "WRITE": 0x1F,
    "LIST": 0x20,
    "MEM": 0x21,
    "TICK": 0x22,
    "SYS": 0x23,
    "RUN": 0x24,  # u16 string idx → run .app
    "RUNALL": 0x25,  # run every *.app
    "ADAPT": 0x26,  # pop mode (0/1/2)
}

OP_NAME = {v: k for k, v in OPS.items()}

# English surface words map to opcodes (SAY language)
ENGLISH: dict[str, str] = {
    "halt": "HALT",
    "stop": "HALT",
    "nop": "NOP",
    "push": "PUSH",
    "put": "PUSH",
    "pop": "POP",
    "dup": "DUP",
    "swap": "SWAP",
    "drop": "DROP",
    "add": "ADD",
    "plus": "ADD",
    "sub": "SUB",
    "minus": "SUB",
    "mul": "MUL",
    "times": "MUL",
    "div": "DIV",
    "mod": "MOD",
    "eq": "EQ",
    "equals": "EQ",
    "ne": "NE",
    "lt": "LT",
    "less": "LT",
    "gt": "GT",
    "greater": "GT",
    "le": "LE",
    "ge": "GE",
    "not": "NOT",
    "and": "AND",
    "or": "OR",
    "store": "STORE",
    "set": "STORE",
    "load": "LOAD",
    "get": "LOAD",
    "say": "SAY",
    "print": "SAY",
    "speak": "SAY",
    "says": "SAYS",
    "jump": "JMP",
    "goto": "JMP",
    "jz": "JZ",
    "jnz": "JNZ",
    "call": "CALL",
    "return": "RET",
    "ret": "RET",
    "read": "READ",
    "write": "WRITE",
    "list": "LIST",
    "mem": "MEM",
    "tick": "TICK",
    "sys": "SYS",
    "hello": "SYS",
    "run": "RUN",
    "runall": "RUNALL",
    "adapt": "ADAPT",
}
