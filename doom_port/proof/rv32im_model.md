# RV32IM AOT model used by the Doom witness

The Doom witness no longer interprets an ELF file at RFVP runtime. The ELF is a
build-time intermediate.

`tools/rv32_aot.py` parses an ELF32 little-endian RISC-V executable, decodes
instructions only from allocated `SHF_EXECINSTR` sections, partitions them into
basic blocks, and emits one Luax/HCB function per block. Each emitted operation
implements the corresponding RV32 architectural state transition over the
register table (`GT[800]`), sparse guest memory (`GT[801]`), and program counter
(`g100`).

Non-executable alloc-section bytes are initialized into guest memory by the
generated `doom_guest_image_init()`. NOBITS/BSS reads as zero until written.

The current translator supports the RV32I instructions and RV32M multiply/divide
operations produced by the configured Clang build. Unsupported encodings fail
the build. Compiler jump tables and sibling-call optimization are disabled, and
the auditor rejects computed `jalr x0, xN, imm` forms whose target set is not
proven by the current AOT analysis. `STT_FUNC` addresses are block starts so C
function pointers have explicit generated destinations.

This AOT mechanism is part of the **large-program engineering witness**, not the
formal proof of universality. The direct two-counter construction in
`minsky_bigint.luax` is the formal model used for that claim.
