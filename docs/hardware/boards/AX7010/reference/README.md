# AX7010 Local Reference Package

The raw package remains at repository-local `hardware_AX7010/` and is not committed as a canonical build input. Its per-file SHA256 inventory and disposition are recorded in `manifest.json`.

The package appears to contain vendor board schematics, PCB/mechanical references, component datasheets, a user manual, and a separate TFDU CAD package. Redistribution terms and the authoritative revision of the CAD package are unverified, so the raw files remain local-only. Generated CAD history/previews/logs are explicitly non-source. The byte-identical TFDU6102 datasheet already has a tracked canonical reference copy at `docs/datasheets/TFDU6102datasheet.pdf`.

Current AX7010 development inputs remain `board_profiles/ACTIVE_PROFILE.json`, `board_profiles/ax7010_tfdu_j10_j11_pinmap.csv`, and `constraints/active/PORT1.generated.xdc`; this raw package does not override them.
