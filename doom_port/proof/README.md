# HCB universality construction and the Doom witness

Two claims are intentionally separated.

## 1. Abstract computational universality

`minsky_bigint.luax` implements a two-counter Minsky/register machine using
`INC` and `DEC/JZ` transitions. Its counters are represented as expandable
base-10000 digit tables rather than one fixed-width HCB integer.

Under the standard idealized semantics in which table storage and execution are
not assigned a fixed resource bound, simulation of a universal two-counter
machine establishes the computational-universality result.

The qualification matters: an actual RFVP process has finite integer widths,
finite address/key spaces, and finite host memory. Like every physically finite
computer, a concrete RFVP process is therefore finite-state. The formal claim
is about the usual unbounded-resource language/model abstraction.

## 2. Doom as an engineering witness

Doom is not used as the mathematical proof. It tests whether the same existing
HCB environment can carry a large, pre-existing program without embedding its
game algorithms in RFVP.

The current path is:

1. compile the supplied official `linuxdoom-1.10` core to freestanding RV32IM;
2. audit and AOT-translate RV32 instructions into HCB basic-block functions;
3. encode non-executable ELF data as guest memory;
4. embed exact IWAD bytes into build-time HCB ROM pages;
5. execute the generated HCB under **unmodified RFVP**;
6. keep Doom's normal 320×200 software rendering and alter only the final
   platform presentation to 80×50/4000 existing Tile primitives.

The Doom core modules are not manually replaced with approximate HCB AI,
weapons, BSP, collision, specials, or rendering code. Platform `I_*`,
freestanding libc/compiler runtime, and final display/input mapping form the
port boundary.

See the generated source manifest and `STATUS.md` for what has and has not been
verified on the full program.
