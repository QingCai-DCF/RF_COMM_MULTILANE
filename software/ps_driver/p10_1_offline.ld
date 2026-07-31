ENTRY(p10_1_performance_entry)

SECTIONS
{
  . = 0x00100000;
  .text : { *(.text*) }
  .p10_1_identity : { KEEP(*(.p10_1_identity)) }
  .rodata : { *(.rodata*) }
  .data : { *(.data*) }
  .bss : { *(.bss*) *(COMMON) }
  /DISCARD/ : { *(.comment) *(.note*) }
}
