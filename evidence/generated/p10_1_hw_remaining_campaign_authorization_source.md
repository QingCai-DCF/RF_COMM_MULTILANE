# P10.1 remaining hardware campaign authorization audit

## Result

`P10_1-HARDWARE-REMAINING-CAMPAIGN-AUTHORIZATION-SOURCE: AUTHORIZED`

The user explicitly stated: “可以，我授权，请帮我告诉主线程”. This authorizes the remaining hardware campaign for the frozen P10.1 artifact bundle. The source task is `019fbc2e-870c-7a93-94b9-237964bb8b0c`.

This record is an authorization source, not an open hardware gate. Every actual hardware attempt still requires a new unique run ID and a committed immutable current-run authorization. The already consumed faults-only authorization is not rewritten; its PASS evidence remains immutable.

## Frozen binding

- source commit: `bb6ce78ab67ebe8aaa459bdd3e440693ee725cc1`
- fixed bitstream: `1585d1ad90324ac525ec38d5f8323930c0ac52977f3fcacc585863195439608e`
- rotating bitstream: `9ad4f85faf186d709ce887fba432d25524ba719cba74f448cb783e2cd1cdfc5f`
- fixed ELF: `17394f82ecc594562f6ea6209f1075cac9a03e09179879d3d3584437d9b7d728`
- rotating ELF: `88b4ce1d02e63c24687afe10edf6fcdc7b5a2c990b8fea8077f53115c5f444c0`
- fixed board: `AX7020-F/JTAG:210249855178`
- rotating-role board: `AX7020-R/JTAG:210512180081`

## Preserved safety boundaries

- each formal run is at most 1800 seconds;
- lane masks are limited to `0x1`, `0x2`, and `0x3`;
- Ethernet, movement, rotation, angle adjustment, obscuration, module exchange, and rewiring are prohibited;
- every attempt requires shutdown-before;
- error, timeout, Ctrl+C, normal exit, and final exit require verified shutdown of both endpoints;
- the user’s prior “不设上限” retry-count override remains limited to this campaign.

The machine-readable authorization source is `evidence/generated/p10_1_hw_remaining_campaign_authorization_source.json`.
