# Dataset changelog

## v1 (2026-08-28) — `FoamBench_basic_v1.json`, `FoamBench_advanced_v1.json`

Generated from the unmodified Kaggle originals by `python Dataset/patch_v1.py`.
Originals (`FoamBench_basic.json` md5 `5806109a…`, `FoamBench_advanced.json` md5 `4418b079…`) are kept as-is
for comparison with published numbers.

Policy: the requirement text is made to fully specify what the GT actually does; GT solver settings are not
changed, so GT reference fields do not need to be re-run. Only dead template files never read by the GT solver
are removed. Full audit: `docs/AUDIT_requirement_vs_GT.md`.

| Cases | Defect | Fix |
|---|---|---|
| `Cavity/1`–`Cavity/10` (Basic) | Requirement has no flow-regime statement at all, GT is `RAS kEpsilon`. Re sweep 150–30000 makes either guess wrong for half the family. | Appended one sentence: k-epsilon RAS, k=0.00375, epsilon=0.00754, nut=0, kqR/epsilon/nutk wall functions (values taken verbatim from GT `0/k`, `0/epsilon`, `0/nut`). Removed `0/omega`, `0/nuTilda` — kEpsilon never reads them; they only penalised structure scores of otherwise-correct submissions. GT file count 14 → 12. |
| `Diamond_Obstacle_KOMEGASST`, `Rectangular_Obstacle_KOMEGASST` (Advanced) | Requirement says "k-epsilon RANS", GT `turbulenceProperties` is `RASModel kOmegaSST`. | Requirement text: "k-epsilon" → "k-omega SST". |

Note for score comparison: Cavity structure scores (TreeScore / ROUGE) are computed against the GT file list per
sub-directory, so the v1 baseline for `0/` is 5 files instead of 7. Basic/Advanced scores on v1 are not directly
comparable to scores on the originals for the Cavity family and the two KOMEGASST cases.

Not yet audited in v1: parameter-by-parameter reconciliation of the remaining 114 cases (only solver name,
numeric presence and turbulence model were checked across all 126; only `Cavity/1` was reconciled by hand).
