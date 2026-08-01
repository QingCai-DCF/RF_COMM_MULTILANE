# P10.1 selected tuning configuration

Status: **PASS** for selecting the best measured candidate for sustained
pipeline qualification.

The nine-candidate hardware sweep in
`p10_1_hw_20260801T033309Z_bfff4836_1585d1ad_9ad4f85f` selected:

- buffer count: `4`
- object size: `512 KiB`
- descriptor size: `64 KiB`
- descriptor ring depth: `32`
- descriptor batch: `8`
- ACK threshold: `8`
- outstanding frames: `32`
- measured application goodput: `2,588,639.5636545448 bit/s`

The runtime, pipeline, host plan defaults, and XSDB dynamic-window defaults
now use that configuration. All original tuning vectors remain explicit, and
the tuning plan SHA256 remains
`1e528bb0a2203deb33c74d3f3cd6c3950fb285122690a24654a3e445fc73c9c4`.

This selection does not pass or change the separate `4.0 Mbit/s` hardware
gate. Sustained pipeline stability remains pending a new run-bound hardware
authorization.

Machine-readable evidence is in
`evidence/generated/p10_1_hw_selected_tuning_configuration.json`.
