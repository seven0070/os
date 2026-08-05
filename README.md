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

## Circumstance-driven phases

Boot does not hardcode adapt 1 then 2. It **`sense`s** the stick and picks a phase:

| Circumstance | Phase |
|--------------|--------|
| 0 apps | idle (0) |
| 1–2 apps, roomy mem | universal (1) |
| 3+ apps or low mem | chameleon (2) + follow-up pass |
| All apps covered | settle (0) |

```bash
python3 run_anything.py
```


StickOS is meant to run on **StickCPU** inside the pendrive. The host USB port
supplies **VBUS (5V) only**. Host Python must not interpret opcodes at run time.

```bash
python3 run_independent.py
```

That loop:
1. Flashes `stickos.stk` into StickCPU firmware (`native/stickcpu`)
2. Purges host-side interpreters from the process
3. Applies VBUS via the USB power bench (starts firmware; no stdin programs)
4. Passively sniffs UART TX and audits that autonomy held

Proof artifact: `stickos/native/INDEPENDENCE.txt`

## Host-side simulator (dev only)

```bash
python3 run_stickos.py
```

Builds the native image and runs the Python VM (for development). The
independent path above is the real operating contract.

```bash
python3 run_stickos.py --build-only   # only emit stickos.stk
python3 -m stickos.simulate --once    # single round
```

## Layout

```
stickos/
  opcodes.py              # 1-byte ISA
  say_compile.py          # English → bytecode
  vm.py                   # host-side VM (dev only)
  image.py                # ROM → .stk
  silicon/stickos_fw.c    # StickCPU firmware (real runtime)
  silicon/build_fw.py     # flash .stk + gcc
  bench/power.py          # USB VBUS bench (power only)
  bench/independence.py   # autonomy audits
  simulate_independent.py # VBUS-only loop until proven
  rom/kernel.say          # boot program
  demos/                  # sample SAY programs
  native/stickos.stk      # kilobyte ROM image
  native/stickcpu         # StickCPU firmware binary
```

## Image format (`STK1`)

Magic `STK1`, version, mem KB, entry, code, string table, embedded stick files — all packed into one blob you could drop on a pendrive.
