#!/usr/bin/env python3
from pathlib import Path
import yaml

ROOT=Path(__file__).resolve().parent.parent
runtime_files=[
    ROOT/'runtime/host.luax', ROOT/'runtime/rv32core.luax', ROOT/'runtime/int32.luax',
    ROOT/'guest/platform/hcb_guest.h', ROOT/'guest/platform/i_system.c',
    ROOT/'guest/platform/i_video.c', ROOT/'guest/platform/i_sound.c', ROOT/'guest/platform/i_net.c',
    ROOT/'guest/libc/hcb_libc.c', ROOT/'guest/libc/rv32_runtime.S',
]
text='\n'.join(p.read_text(errors='replace') for p in runtime_files)
for forbidden in ('BinaryCacheLoad','BinaryCacheRead','InputGetAsciiWord','rfvp_hcb','rfvp_doom'):
    assert forbidden not in text, f'zero-patch runtime still references extension {forbidden}'

meta=yaml.safe_load((ROOT/'doom.yaml').read_text())
assert meta.get('syscall_count')==148, meta.get('syscall_count')
all_specs=meta['syscalls'].values() if isinstance(meta['syscalls'],dict) else meta['syscalls']
names={x['name'] for x in all_specs}
required={'InputGetState','TimerGet','TimerSet','ColorSet','PrimSetTile','PrimGroupIn','ThreadNext'}
assert required <= names, sorted(required-names)
assert 'InputGetAsciiWord' not in names and 'BinaryCacheLoad' not in names

# The experiment directory itself must not contain a patch that modifies RFVP.
assert not list(ROOT.glob('*.patch')), 'zero-patch distribution unexpectedly contains an RFVP patch'
print('zero-RFVP-patch structural policy: PASS')
