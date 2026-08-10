# RFVP HCB DOOM

A deliberately unreasonable port of **id Software's `linuxdoom-1.10`** to FVP.

The project does not rewrite Doom's gameplay in script code. The original C core is compiled as a freestanding **RV32IM/ILP32** program, audited, translated basic-block-by-basic-block into Luax scripts, and executed on an RV32 architectural state implemented inside *.hcb.

## What this project does

```text
id Software linuxdoom-1.10 C
        +
freestanding guest libc + HCB platform layer
        |
        | clang --target=riscv32-none-elf -march=rv32im -mabi=ilp32
        v
    doom-rv32.elf
        |
        | audit_elf.py
        v
 audited RV32IM ELF
        |
        | rv32_aot.py
        v
  Doom RV32 AOT Luax ------------------+
                                       |
canonical IWAD                         |
        |                              |
        | wad2luax.py                  |
        v                              |
 read-only IWAD-ROM Luax --------------+
                                       |
runtime/int32.luax                     |
runtime/rv32core.luax                  |
runtime/host.luax                      |
        +------------------------------+
        |
        | make_combined.py + validate_luax.py
        v
 doom-zero-combined.luax
        |
        | lua2hcb compiler
        v
      doom.hcb
```

## Design goals

- Keep the Doom gameplay/core source as the official `linuxdoom-1.10` code.
- Replace only the platform/libc boundary needed by a freestanding RV32 guest.
- Do not reimplement Doom gameplay algorithms in RVP.
- Make unsupported machine-code/control-flow forms fail during the build instead of silently changing semantics.
- Require no Doom-specific source modification in the RVP runtime itself.

## Source preservation

`tools/build_official_doom.py` compiles the non-platform source list from the original Linux Doom Makefile. The platform files (`i_system`, `i_sound`, `i_video`, `i_net`, and `i_main`) are replaced by the implementations under `guest/platform/`.

There is one deliberate core-source transformation: `m_fixed.c` selects id Software's existing integer `FixedDiv2` implementation that is present behind `#if 0` in the released source. This avoids introducing floating-point emulation for an RV32IM target and does not replace the fixed-point algorithm with a new approximation.

A source manifest records input hashes, the transformation, compiler flags, platform substitutions, and the final ELF hash.

## Guest machine

The guest architectural state lives in *.hcb tables/globals:

```text
GT[800]  RV32 x0..x31 integer register file
GT[801]  sparse little-endian guest memory, indexed by byte_address / 4
GT[802]  optional per-word dirty markers

g100     guest PC
g101     running flag
g102     trap/status code
g103     exit code
g104     retired-instruction counter
g105     present/yield request
```

`runtime/rv32core.luax` implements the architectural load/store helpers, sign extension, signed/unsigned comparisons, RV32M multiply/divide/remainder behavior, register semantics (including hard-wired `x0`), and the ECALL boundary.

### AOT, not a source-level Doom rewrite

`tools/rv32_aot.py` decodes the linked ELF at build time. Each RV32 basic block becomes an Luax function. Architectural control flow is preserved by updating `g100`:

- conditional RV32 branches select the next PC;
- `JAL` and `JALR` update the link register and PC;
- loads/stores access `GT[801]` through the RV32 memory helpers;
- `ECALL` enters the small HCB host interface.

A generated binary dispatch tree maps the current guest PC to the corresponding AOT basic block. The build rejects instruction/control-flow forms that the translator cannot prove safe rather than pretending to support them.

`tools/audit_elf.py` verifies that the final executable instruction set is exactly covered by the AOT block partition and audits indirect jumps before HCB generation.

## Why this is computationally universal

The interesting part of this project is not that Doom happens to run. Doom is an engineering stress test, not a mathematical proof.

The universality construction is the RV32 machine model implemented on top of HCB:

1. **Mutable machine state** — 32 integer registers plus a mutable sparse memory table.
2. **Indirect memory access** — guest addresses select mutable words/bytes at runtime.
3. **Conditional control flow** — RV32 comparisons and branches can choose the next guest PC.
4. **Unbounded iteration in the language model** — the host loop repeatedly dispatches basic blocks while the guest remains runnable.
5. **General arithmetic** — the implemented RV32I integer operations plus the RV32M arithmetic required by the compiled program operate on the same architectural state.
6. **Call/return and a guest stack** — `JAL/JALR`, `x2`, and guest memory preserve normal compiled C call semantics.


## Host ABI

The guest uses a deliberately small ECALL interface. The current RV32 runtime uses the following call numbers:

```text
1  present framebuffer / poll input return value
2  exit
3  monotonic milliseconds
4  input state
5  commit palette
6  read bytes from the embedded IWAD into guest memory
```

The guest-visible memory-mapped platform region is:

```text
0x10000000  80x50 indexed output framebuffer
0x10001000  256 x RGB palette
0x10002000  IWAD configuration (size + canonical IWAD kind)
```

## Video

Doom itself continues rendering its original **320x200 8-bit indexed framebuffer**.

`guest/platform/i_video.c` samples the center of each 4x4 source block at the presentation boundary and writes an **80x50 indexed framebuffer** to the FVP host region. Palette changes are copied to the host palette region and committed through ECALL 5.

This deliberately preserves the original Doom renderer while keeping the FVP presentation surface small. The large visible pixels are therefore expected for the current backend.

## Input

The current platform mapping is intentionally simple:

| Host input | Doom input |
| --- | --- |
| Shift | Run (`KEY_RSHIFT`) |
| Ctrl or left mouse | Fire (`KEY_RCTRL`) |
| Right mouse | Strafe modifier (`KEY_RALT`) |
| Escape | Escape |
| Enter | Enter |
| Space | Use/open |
| Arrow keys | Movement/turning |
| Tab | Automap |
| F1..F12 | Doom function keys |
| Shift+F1..F7 | Weapon keys `1`..`7` |

## Audio and networking

The current audio backend is intentionally silent: the Doom sound/music APIs are present so the original core can run, but no PCM/music output is emitted yet.

The sound-lump lookup must still preserve original Doom naming semantics (`"ds%s"`, e.g. `pistol -> dspistol`) even with a silent backend, because resource lookup is part of the original program behavior.

Networking is intentionally single-player only. `I_InitNetwork` exposes one local player/node; an attempted network command is treated as an error.

## Freestanding libc

`guest/libc/hcb_libc.c` supplies the subset of libc required by the official Doom core: memory/string routines, a simple allocator, formatted strings, file-like WAD/save access, time/platform calls, and related support.

This layer is intentionally small, but it must preserve the semantics Doom actually relies on. One example found during bring-up is `sprintf("STCFN%.3d", n)`: Doom uses this to construct HUD font lump names such as `STCFN033`, so precision/width handling in the guest formatter is required for startup correctness.

## IWAD embedding

`tools/wad2luax.py` converts the IWAD into a read-only ROM. It uses:

- 4096-byte pages;
- four cache slots;
- 32-bit little-endian words;
- an explicit WAD-size/type configuration block;
- `doom_wad_read_to_guest(offset, dst, len)` for guest reads.

The guest libc maintains normal `open`/`lseek`/`read` state for the IWAD, but ECALL 6 ultimately performs an absolute-offset read from the embedded ROM into guest memory.

### Current performance limitation

The current ROM representation is intentionally simple, not efficient. Every four IWAD bytes become one generated Luax assignment. A 4,196,020-byte Shareware 1.9 IWAD therefore expands to roughly **1,049,005 table assignments** before the RV32 AOT code is even counted.

This has two consequences:

- `lua2hcb` compilation is slow because it must parse/lower more than a million WAD-data assignments;
- cold WAD page fills are also relatively expensive at runtime.

A future optimization should store the IWAD as a true static HCB resource instead of executable table-initialization code. That would improve both compile time and startup/page-miss cost without changing Doom semantics.

## Requirements

- Python 3.11+
- LLVM `clang` with the RISC-V target
- LLVM `ld.lld`
- official id Software `linuxdoom-1.10` source tree
- a legally obtained canonical Doom IWAD
- an external `lua2hcb` compiler for the final Luax -> HCB step

The Doom/RV32 stages do not require the RFVP source tree. Running the resulting RVP program is outside the scope of this README.

On Apple Silicon with Homebrew LLVM, make sure Homebrew LLVM is ahead of Apple Clang when building the guest, for example:

```bash
export PATH="/opt/homebrew/opt/llvm/bin:$PATH"
```

## Build

### 1. Build and validate the combined Luax

From this project directory:

```bash
python3.11 build.py \
  /path/to/DOOM/linuxdoom-1.10 \
  /path/to/doom1.wad \
  --luax-only
```

This produces and validates:

```text
generated/doom-rv32.elf
generated/doom-rv32-aot.luax
generated/doom-iwad-rom.luax
generated/doom-zero-combined.luax
generated/doom-source-manifest.json
generated/doom-build-manifest.json
```

To stop after compiling/auditing the RV32 ELF:

```bash
python3.11 build.py /path/to/DOOM/linuxdoom-1.10 --elf-only
```

### 2. Compile Luax to HCB

Use the external HCB compiler:

```bash
/path/to/lua2hcb \
  --meta doom.yaml \
  --lua generated/doom-zero-combined.luax \
  --out generated/doom.hcb
```

If using the Cargo package directly instead of a prebuilt executable, run it from the Cargo workspace that contains `lua2hcb_compiler`; this Doom directory itself does not contain that workspace.

### 3. Run

Load:

```text
generated/doom.hcb
```

with an HCB-capable runtime. Runtime installation/usage is intentionally not documented here.

## Fast development loop

WAD generation is extremely large. If the C/guest/AOT code changed but the IWAD did not, reuse `generated/doom-iwad-rom.luax` instead of regenerating it:

```bash
python3.11 tools/build_official_doom.py \
  /path/to/DOOM/linuxdoom-1.10 \
  -o generated/doom-rv32.elf \
  --manifest generated/doom-source-manifest.json

python3.11 tools/audit_elf.py generated/doom-rv32.elf

python3.11 tools/rv32_aot.py \
  generated/doom-rv32.elf \
  -o generated/doom-rv32-aot.luax

python3.11 tools/make_combined.py \
  --aot generated/doom-rv32-aot.luax \
  --wad-rom generated/doom-iwad-rom.luax \
  -o generated/doom-zero-combined.luax

python3.11 tools/validate_luax.py \
  generated/doom-zero-combined.luax \
  --meta doom.yaml
```

Then run the Luax -> HCB compiler once.

## Project layout

```text
build.py                 top-level build orchestration
doom.yaml                HCB metadata / syscall declaration

guest/
  doom_rv32.ld           freestanding RV32 linker script
  include/               minimal guest C headers
  libc/                  freestanding libc + RV32 runtime support
  platform/              Doom i_* platform replacements

runtime/
  int32.luax             32-bit helper operations
  rv32core.luax          RV32 register/memory/arithmetic/ECALL model
  host.luax              scheduler + presentation/input host bridge

tools/
  build_official_doom.py official Doom -> RV32IM ELF
  audit_elf.py           machine-code/AOT compatibility audit
  rv32_aot.py            RV32 basic blocks -> Luax/HCB IR
  wad2luax.py            IWAD -> read-only HCB ROM
  make_combined.py       combine runtime + guest + IWAD
  validate_luax.py       static validation before HCB compilation

generated/               generated build artifacts (ignored)
build/                   temporary objects/source copy (ignored)
wad/                     local IWADs (ignored)
```

## Non-goals / current limitations

- No claim of arbitrary ELF compatibility: only the audited RV32IM/control-flow forms accepted by the translator are supported.
- No audio output yet.
- No multiplayer/network transport.
- Output is currently 80x50 indexed pixels sampled from Doom's 320x200 framebuffer.
- IWAD embedding is intentionally inefficient and is the major compile/startup performance problem.
- The guest libc is compatibility-oriented, not a general POSIX libc.

## Legal note

This project does not need to redistribute an IWAD. Supply game data separately and respect the license/distribution terms of the Doom source and the IWAD you use.
