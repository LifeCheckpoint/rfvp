ENTRY(_start)
SECTIONS {
  . = 0x00010000;
  .text : { *(.text .text.*) }
  .rodata : { *(.rodata .rodata.*) }
  .data : { *(.data .data.*) }
  .sdata : { *(.sdata .sdata.*) }
  . = ALIGN(16);
  .bss : { *(.bss .bss.* COMMON) }
  .sbss : { *(.sbss .sbss.*) }
  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
