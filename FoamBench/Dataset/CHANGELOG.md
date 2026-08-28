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
| `obliqueShock/8` | GT was swept (inlet 4.0, top (3.5,-0.50632,0)) but the prose kept the template velocities (2.9 / (2.61933,…)). Inviscid compressible: inlet speed sets the Mach number and shock angle, so requirement and GT solve different problems. | Requirement velocities → 4.0 / (3.5,-0.50632,0.0). Resulting combination is distinct from variants 7 and 9. |
| `counterFlowFlame2D/9` | Prose was swept (fuel 0.4, air −0.3 m/s) but GT is a byte-identical copy of variant 1 (0.1 / −0.1). | **GT edit** (deviation from policy A): `0/U` fuel/air → 0.4 / −0.3. Editing the prose instead would have made /9 a duplicate of /1. GT reference fields for this case must be re-run locally (they are not in the JSON anyway). |
| `Cylinder_LES`, `Cylinder_SA` (Advanced) | Prose says "Finaltime is 0.5", GT `controlDict` `endTime 2` (deltaT 0.0025 and writeInterval 0.05 agree). NMSE compares at the GT's last time, so a 0.5 s submission is scored against the t = 2 s wake. | Requirement "Finaltime is 0.5" → "Finaltime is 2". |
| `forwardStep/1` | Prose "fixed velocity of 3m/s", GT `0/U` inlet/internal 4 m/s (variants 2–10 agree with their prose). | Prose 3 → 4 m/s. |
| `squareBend/7`–`/10` | Prose "time step of 1 second", GT `deltaT 0.5` (endTime/writeInterval agree; 1–6 have deltaT 1). | Prose 1 → 0.5 s. |
| `pitzDaily/1`–`/10`, `Cylinder/1`–`/10`, `Cylinder_LES`, `Cylinder_SA` | Prose "zero gradient pressure at the outlet (right)"; GT `0/p` outlet is `fixedValue 0` and it is `0/U` that is `zeroGradient` (conventional outlet). | Prose → "fixed-value pressure of 0 at the outlet (right) with zero-gradient velocity there". |
| `Double_Square_SA`, `Diamond_Obstacle_SA`, `Diamond_Obstacle_KOMEGASST`, `Rectangular_Obstacle_SA`, `Rectangular_Obstacle_KOMEGASST` | Prose "outlet using zero gradient pressure condition"; GT `0/p` outlet `fixedValue $internalField`, `0/U` outlet `pressureInletOutletVelocity`. | Prose → fixed-value p / pressureInletOutletVelocity U. |
| `shallowWaterWithSquareBump/1`–`/10` | Prose only states uniform depth (0.01…0.1) and uniform momentum (0.001,0,0); GT `setFieldsDict` additionally overrides the bump box with `h 0.009`, `hU (0.0009 0 0)`, `h0 0.001` — template values that were never swept with the depth. GT was run as-is, so the stored `0/h`/`0/hU` contain them. | Prose: append the bump-box override explicitly (values as in GT). Physically the bump override is stale for depth ≥ 0.02 (free-surface dip); a v2 could re-derive the override per variant, which requires re-running GT. |
| `nozzleFlow2D_SA` | Prose self-contradicts: "The end time is 1e-5s. seconds, and run the simulation until a final time of 10 seconds."; GT `endTime 1e-05`. | Prose → "The end time is 1e-5 s." |
| `Rectangular_Obstacle_SA` | GT `0/nuTilda` names the auto-generated empty patch `defaultfaces`; blockMesh and every other `0/*` file use `defaultFaces`. Patch names are case-sensitive, so the GT cannot start. | **GT edit** (executability): rename to `defaultFaces` in `0/nuTilda`. |
| `wedge/7`, `wedge/8`, `wedge/10` | GT `Pr` was swept (0.71 / 0.71 / 1.5) but every prose says "Pr is 1"; also made requirements 6≡7 and 8≡9≡10 identical. mu = 0 (inviscid) so Pr does not affect the solution — wording/ROUGE only. | Requirement "Pr is 1" → "Pr is 0.71 / 0.71 / 1.5". |

### Independent validation

The first v1 (19 cases) was reviewed by gpt-5.6-sol (`docs/VALIDATION_v1_gpt56sol.md`): all 19 defects CONFIRMED;
it caught one bug in the patch (wedge prose was "Pr is 1.0", so replacing "Pr is 1." produced "Pr is 0.71.0" — fixed)
and reported the additional discrepancies listed above, each of which was re-verified directly on the JSON before
being added. It also confirmed the structural-score mechanics described in the audit and noted that `similarity_report.py`
skips a scored sub-directory entirely (instead of scoring 0) when the submission lacks it — a scorer bug tracked in
`docs/PIPELINE_NOTES.md`.

Note for score comparison: Cavity structure scores (TreeScore / ROUGE) are computed against the GT file list per
sub-directory, so the v1 baseline for `0/` is 5 files instead of 7. Basic/Advanced scores on v1 are not directly
comparable to scores on the originals for the Cavity family and the two KOMEGASST cases.

Not yet audited in v1: parameter-by-parameter reconciliation of the remaining cases (only solver name,
numeric presence and turbulence model were checked across all 126; only `Cavity/1` was reconciled by hand).
