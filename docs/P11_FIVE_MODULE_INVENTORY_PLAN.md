# P11 five-module inventory plan

The current accepted P10 inventory contains four historically operational
small boards: F0, F1, R0, and R1. P11 needs five modules simultaneously:
four fixed-fixture positions plus one rotating-fixture position. One
additional compatible module is therefore required.

For the fifth module, record before use:

- manufacturer/device marking consistent with TFDU6102, small-board model,
  PCB revision, serial or durable inventory ID, supplier/source, and photos;
- connector pin numbering and pin-1 orientation;
- VCC1/VCC2 and ground topology, rated voltages, decoupling, and power-up/
  partial-power behavior;
- Txd, Rxd, SD, and Mode paths, polarity, series resistors, pull-up/down
  components, default/reset behavior, and static high-speed Mode selection;
- evidence hashes for the datasheet, schematic/pinout, inspection photos, and
  any electrical verification record.

The existing four modules retain their P10 historical identity in
`config/hardware/p10_tfdu_module_inventory.yaml`; this plan does not rewrite
their P10 acceptance. P11 role assignment must be explicit and must not infer
identity from connector order. The fifth module remains missing at this
checkpoint.
