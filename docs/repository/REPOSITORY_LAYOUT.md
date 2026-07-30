# Repository Layout

| Path | Responsibility |
|---|---|
| `PROJECT_CONSTRAINTS.txt` | Sole canonical normative product constraint; changes require the confirmed workflow in `AGENTS.md`. |
| `config/` | Machine-readable state, requirements, register map, geometry, safety, data-plane, and build configuration. |
| `board_profiles/` | Canonical board/profile inputs. The current AX7010 development pinmap is not reusable for a final Z7020 endpoint. |
| `constraints/` | Profile-scoped XDC and constraint inputs. |
| `rtl/`, `sim/` | Canonical RTL and offline verification models/tests. Legacy references remain segregated and read-only. |
| `software/` | PS/host software and profile-aware runtime sources. |
| `scripts/`, `tools/` | Reproducible generators, gates, audit tooling, and safe wrappers. |
| `docs/` | Current design, safety, verification, repository, and board-reference documentation. Markdown summaries do not replace raw evidence. |
| `legacy/` | Historical, read-only reference inputs; never canonical build inputs or current acceptance evidence. |
| `evidence/` | Raw and generated verification records, including failed history. Evidence is not disposable cache. |
| `artifacts/` | Frozen/content-addressed build artifacts and manifests. |
| `hardware_AX7010/`, `hardware_AX7020/` | Local-only raw vendor/CAD input packages. Their tracked manifests live under `docs/hardware/boards/`; the raw files are not canonical inputs. |

The active development profile remains defined by `board_profiles/ACTIVE_PROFILE.json`, `board_profiles/ax7010_tfdu_j10_j11_pinmap.csv`, and `constraints/active/PORT1.generated.xdc`. Future board profiles must use their own separate profile directories and cannot be inferred from the local-only vendor packages.
