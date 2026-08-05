# StickOS

A **kilobyte-scale operating system for USB pendrives**, with a native language called **SAY** (English words compiled to 1-byte opcodes).

## Why

Most OSes are megabytes to gigabytes. StickOS is designed to live on a stick: the entire native boot image is **under one kilobyte** (currently ~0.33 KB).

## Native size

| Artifact | Size |
|----------|------|
| `stickos/native/stickos.stk` | **342 bytes (0.33 KB)** |
| Kernel bytecode | 72 bytes |
| Memory arena | 64 KB virtual |

## Language: SAY

English-word stack language. Each keyword becomes a single opcode byte.

```say
put 1
set n
loop:
  get n
  say
  get n
  put 1
  add
  set n
  get n
  put 5
  le
  jnz loop
says "counted."
halt
```

Words include: `put`, `set`, `get`, `say`, `says`, `add`, `sub`, `mul`, `div`, `less`, `le`, `jz`, `jnz`, `list`, `mem`, `tick`, `sys`, `halt`, …

## Simulate

```bash
python3 run_stickos.py
```

Builds the native image, boots the kernel, runs demos, reloads the image from disk, and loops until everything passes and size stays in the kilobyte class.

```bash
python3 run_stickos.py --build-only   # only emit stickos.stk
python3 -m stickos.simulate --once    # single round
```

## Layout

```
stickos/
  opcodes.py      # 1-byte ISA
  say_compile.py  # English → bytecode
  vm.py           # pendrive VM + .stk image format
  image.py        # ROM → native image
  simulate.py     # boot until done
  rom/kernel.say  # boot program
  demos/          # sample SAY programs
  native/         # built stickos.stk
```

## Image format (`STK1`)

Magic `STK1`, version, mem KB, entry, code, string table, embedded stick files — all packed into one blob you could drop on a pendrive.
