#!/usr/bin/env python3
from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def run(cmd: list[str]) -> None:
    print("+", " ".join(cmd))
    subprocess.run(cmd, check=True)


def main() -> None:
    ap = argparse.ArgumentParser(description="Build reproducible freestanding RV32IM smoke ELFs")
    ap.add_argument("--clang", default=shutil.which("clang") or "/usr/local/swift/usr/bin/clang")
    ns = ap.parse_args()
    clang = ns.clang
    out = ROOT / "generated"
    out.mkdir(parents=True, exist_ok=True)
    common = [
        clang,
        "--target=riscv32-none-elf",
        "-march=rv32im",
        "-mabi=ilp32",
        "-ffreestanding",
        "-fno-builtin",
        "-fno-stack-protector",
        "-fno-pic",
        "-mno-relax",
        "-msmall-data-limit=0",
        "-fno-jump-tables",
        "-fno-optimize-sibling-calls",
        "-O2",
        "-nostdlib",
        f"-Wl,-T,{ROOT / 'proof/rv32.ld'}",
    ]
    smoke = out / "rv32_smoke.elf"
    div64 = out / "rv32_div64_smoke.elf"
    fnptr = out / "rv32_fnptr_smoke.elf"
    run(common + [str(ROOT / "proof/rv32_smoke.c"), "-o", str(smoke)])
    run(common + [str(ROOT / "tests/rv32_fnptr_smoke.c"), "-o", str(fnptr)])
    run(
        common
        + [
            str(ROOT / "tests/rv32_div64_smoke.c"),
            str(ROOT / "guest/libc/rv32_runtime.S"),
            "-o",
            str(div64),
        ]
    )
    run(["python3", str(ROOT / "tools/audit_elf.py"), str(smoke)])
    run(["python3", str(ROOT / "tools/audit_elf.py"), str(div64)])
    run(["python3", str(ROOT / "tools/audit_elf.py"), str(fnptr)])
    run(["python3", str(ROOT / "tests/rv32_ref.py"), str(smoke)])
    run(["python3", str(ROOT / "tests/rv32_ref.py"), str(div64)])
    run(["python3", str(ROOT / "tests/rv32_ref.py"), str(fnptr)])


if __name__ == "__main__":
    main()
