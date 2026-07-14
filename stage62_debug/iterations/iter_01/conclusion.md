# Iteration 01 conclusion

The hardware hypothesis is neither supported nor refuted because hardware was
never launched.  The dry failure is explained by a validation mismatch:

- the normal linked OCM image ends at `0x00019840` below the mailbox boundary;
- the fixed diagnostic record is an intentional SHF_ALLOC/SHT_NOBITS section at
  `0x00021000..0x00021600`;
- the safe wrapper compared the highest end of *all* SHF_ALLOC sections with the
  normal image end, so the valid separate diagnostic section caused a false
  rejection.

The repair must remain fail closed: parse ELF section names/types, require the
diagnostic section to be unique and exactly placed/sized, and compare the build
summary OCM end only with the remaining normal allocated image.
