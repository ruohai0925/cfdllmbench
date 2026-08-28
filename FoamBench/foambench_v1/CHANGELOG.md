# FoamBench dataset changelog

`FoamBench_basic_v1.json` and `FoamBench_advanced_v1.json` are produced from the unmodified Kaggle
originals by `python Dataset/patch_v1.py`. The originals (`FoamBench_basic.json`, md5
`5806109a8d5a45bd8f6f44bb87b66ceb`, 110 cases; `FoamBench_advanced.json`, md5
`4418b079e408d24c89f8c84b60b49581`, 16 cases) are kept unchanged so published numbers remain reproducible.

**104 of 126 cases are modified.** Every change falls into one of five defect classes described below.
`patch_v1.py` asserts the original text before every edit, so the patch fails loudly if the source changes.

Unpack and run the corrected dataset with:

```bash
python Dataset/unpack_v1.py      # Dataset/{Basic,Advanced}/<case>/GT_Files
./Dataset/run_gt.sh 12           # runs every case to completion; writes Dataset/gt_run_summary.tsv
```

All 126 corrected cases run to `End` under OpenFOAM 10 with no `FOAM FATAL` and no time limit.

---

## A. Requirement text contradicts the ground truth

The prompt states one value and the reference case implements another, so a submission that follows the
prompt exactly is scored against a case solving a different problem. Fixed in the prompt, because the GT
was the side that had been swept correctly.

| Case(s) | Defect | Correction |
|---|---|---|
| `Cavity/1`–`/10` | The prompt contains **no flow-regime statement at all** (neither "laminar" nor "turbulent"), while the GT selects `simulationType RAS; model kEpsilon` and supplies `0/k`, `0/epsilon`, `0/nut`. The family's ν sweep {1e-5, 1e-4, 1e-3} with lid speeds {1, 1.5, 2, 3} spans **Re = 150 to 30 000**, so no single default assumption is right for the whole family: a solver that assumes laminar is wrong for half the cases and one that assumes turbulent is wrong for the other half. | Appended one sentence specifying the k-epsilon RAS model with the exact initial values and wall functions taken from the GT (`k = 0.00375`, `epsilon = 0.00754`, `nut = 0`; `kqRWallFunction`, `epsilonWallFunction`, `nutkWallFunction`). |
| `BernardCells/1`–`/10` | Prompt says "Perform a **3D** Bernard Cell simulation ... The computational domain spans 9 m x 1 m x 2 m"; `system/blockMeshDict` is `(90 10 1)` with `frontAndBack` of type `empty`, i.e. the two-dimensional OpenFOAM tutorial case — the 2 m in z is the thickness of a single empty-bounded layer, not a resolved direction. An agent that follows the prompt builds a three-dimensional mesh and is scored against a two-dimensional solution; Foam-Agent did exactly that, generating `(90 10 20)`. The numeric extents 9 × 1 × 2 match the mesh, which is why the earlier numeric reconciliation did not catch the word "3D". | Prompt reworded to "2D ... 9 m x 1 m in x and y, meshed with 90 x 10 cells, with a single cell of 2 m thickness in z and empty front and back patches". GT unchanged. |
| `Diamond_Obstacle_KOMEGASST`, `Rectangular_Obstacle_KOMEGASST` | Prompt says "using the **k-epsilon** RANS turbulence model"; `constant/turbulenceProperties` selects `RASModel kOmegaSST` and the case supplies `0/omega`, not `0/epsilon`. Bluff-body separation is sensitive to this choice, so the two models give different solutions. | Prompt wording changed to "k-omega SST RANS turbulence model". |
| `obliqueShock/8` | GT `0/U` was swept to inlet `(4.0 0 0)` and top `(3.5 -0.50632 0)`, but the prompt kept the template values 2.9 and `(2.61933,-0.50632,0.0)`. In inviscid compressible flow the inlet speed *is* the Mach number and fixes the shock angle, so prompt and GT describe different problems. | Prompt velocities corrected to 4.0 and `(3.5,-0.50632,0.0)`. |
| `squareBend/7`–`/10` | Prompt says "a time step of 1 second"; `system/controlDict` has `deltaT 0.5` (variants 1–6 do have `deltaT 1`; `endTime` and `writeInterval` agree throughout). | Prompt time step corrected to 0.5 s. |
| `forwardStep/1` | Prompt says "fixed velocity of 3m/s"; `0/U` has 4 m/s on the inlet and in `internalField`. Variants 2–10 agree with their own prompts, so this is a single stale variant. | Prompt velocity corrected to 4 m/s. |
| `wedge/7`, `/8`, `/10` | Prompt says "Pr is 1.0" in every variant; GT `constant/physicalProperties` has `Pr` = 0.71, 0.71 and 1.5. It also made three prompts textually identical (6≡7 and 8≡9≡10). Harmless numerically, since `mu 0` makes the flow inviscid, but the text is wrong and the duplication removes variant identity. | Prompt corrected to the GT's `Pr` value; the duplicate prompts become distinct. |
| `Cylinder_LES`, `Cylinder_SA` | Prompt says "Finaltime is 0.5"; `controlDict` has `endTime 2` (`deltaT` and `writeInterval` agree). NMSE compares at the GT's last time, so a submission stopping at t = 0.5 would be scored against the t = 2 wake. | Prompt final time corrected to 2. |
| `pitzDaily/1`–`/10`, `Cylinder/1`–`/10`, `Cylinder_LES`, `Cylinder_SA` | Prompt says "zero gradient pressure at the outlet (right)"; GT `0/p` has `fixedValue 0` at the outlet and it is `0/U` that is `zeroGradient` there. The GT is the conventional outlet treatment, so the prompt names the wrong field. | Prompt reworded to "fixed-value pressure of 0 at the outlet (right) with zero-gradient velocity there". |
| `Double_Square_SA`, `Diamond_Obstacle_SA`, `Diamond_Obstacle_KOMEGASST`, `Rectangular_Obstacle_SA`, `Rectangular_Obstacle_KOMEGASST` | Same defect: prompt says "outlet using zero gradient pressure condition"; GT `0/p` outlet is `fixedValue $internalField` and `0/U` outlet is `pressureInletOutletVelocity`. | Prompt reworded to match the GT treatment. |
| `nozzleFlow2D_SA` | The prompt contradicts itself: "The end time is 1e-5s. seconds, and run the simulation until a final time of 10 seconds." `controlDict` has `endTime 1e-05`, so the first clause is right and the second is a leftover. | Removed the trailing clause; the prompt now reads "The end time is 1e-5 s." |

## B. Ground truth contradicts the requirement text

Here the prompt was swept correctly and the GT was not, so the GT is the side that was corrected.

| Case(s) | Defect | Correction |
|---|---|---|
| `counterFlowFlame2D/9` | The prompt specifies fuel 0.4 m/s and air −0.3 m/s, but the whole GT is a byte-for-byte copy of variant 1 (0.1 / −0.1). Correcting the prompt instead would have made variant 9 a duplicate of variant 1 and destroyed a sweep point. | `0/U` fuel and air inlet velocities set to 0.4 and −0.3. |
| `shallowWaterWithSquareBump/2`–`/10` | The background depth was swept to 0.02 … 0.1 m in both prompt and `setFieldsDict`, but the square-bump override stayed at the depth-0.01 template values (`h 0.009`, `hU (0.0009 0 0)`), and `0/h.orig` / `0/hTotal` stayed at `uniform 0.01`. See the worked example below. | Bump override recomputed per variant for a flat initial free surface and uniform velocity; propagated to `setFieldsDict`, the four bump cells of `0/h` and `0/hU`, and the stale `0/h.orig` and `0/hTotal`. |

## C. Ground truth is internally contradictory or physically impossible

Found by scanning each case's GT files against each other and by running every case under OpenFOAM 10.

| Case(s) | Defect | Correction |
|---|---|---|
| `Rectangular_Obstacle_SA` | `0/nuTilda` names the automatically generated empty patch `defaultfaces`, while `blockMeshDict` and every other `0/*` file use `defaultFaces`. OpenFOAM patch names are case-sensitive, so the case cannot start. | Renamed to `defaultFaces` in `0/nuTilda`. |
| `obliqueShock/2`, `/6`, `/9`, `/10` | The `top` patch imposes the post-shock state, but the prescribed state is not reachable from the case's own inlet: **/2** accelerates (2.900 → 3.042) while heating, **/6** accelerates while *cooling* (T 2.0 → 1.259), **/9** and **/10** show no temperature rise at all. Only the x-component had been swept while `Uy` stayed frozen at −0.50632. | Post-shock state recomputed from the exact oblique-shock relations for γ = 1.4 and R = 0.7143 at a shock angle β chosen per variant to keep the family distinct: **/2** β = 35°, **/6** β = 34°, **/9** β = 29°, **/10** β = 33°. The implementation reproduces the untouched variant `/1` to five decimals (β = 29° exactly), which validates it. `/6` needs β > 29.19° (its Mach angle at M₁ = 2.051) and diverges above ≈35°, so its angle is deliberately modest. Prompt updated to the new values. |
| `obliqueShock/2`, `/6`, `/9`, `/10` | `0/U internalField` was `(2.9 0 0)` and `0/T internalField` was 1 in every variant regardless of that variant's own inlet. Tolerable under the original weak boundary state; with the corrected (stronger) shock state, `/6` and `/10` diverge during the start-up transient with a floating-point exception in `sqrt` (negative temperature). | `internalField` synchronised with each variant's inlet state. |
| `obliqueShock_KE`, `obliqueShock_LES` | `system/fvSolution` defines a solver for `h` (enthalpy) although the thermophysical model uses `energy sensibleInternalEnergy`, so the field is `e`. The entry was dead while `mu 0` kept the solver on its inviscid branch, and became fatal (`keyword e is undefined`) as soon as that branch was left. | `fvSolution` solver entry renamed `h` → `e`. |
| `Diamond_Obstacle_SA`, `Rectangular_Obstacle_SA`, `Double_Square_SA` | `0/nuTilda` applies `nutkWallFunction` at the wall patches. That is `nut`'s wall function, not a Spalart-Allmaras wall condition, which must be `fixedValue 0`. | Wall patches set to `fixedValue uniform 0`. **Measured impact: none.** Re-running gives bit-identical fields (0 of 10 000 cells changed for `Diamond_Obstacle_SA`, 0 of 4 200 for `Double_Square_SA`), because with no `k` field present the wall value was never updated. Kept as a correctness fix so that a submission writing the proper condition matches the GT text. |

## D. Declared turbulence model has no effect

The case names a turbulence model, the model is selected at run time, and it then contributes nothing —
so NMSE cannot distinguish a submission that models turbulence correctly from one that ignores it entirely.

| Case(s) | Defect | Correction |
|---|---|---|
| `Cavity_SA`, `Cavity_geometry_1`, `Cylinder_SA`, `nozzleFlow2D_SA` | `simulationType RAS; model SpalartAllmaras` with `0/nuTilda` identically zero in the interior and at every value-bearing boundary. ν̃ = 0 is an **exact fixed point** of the SA transport equation, so the model can never produce eddy viscosity. Verified by running: end-time `nut` and `nuTilda` are exactly `uniform 0`, i.e. the "SA reference solution" equals the laminar one pointwise. | Freestream/inflow ν̃ set to 3ν (Spalart's recommended freestream value: 3e-05, 3e-05, 0.03, 1.7856e-05 respectively) and wall patches pinned at `fixedValue 0`. After the fix `nut` is non-zero in all four: `nut_max/ν` = 35 (`Cavity_SA`), 51 (`Cavity_geometry_1`), 0.20 (`Cylinder_SA`, correct for its Re = 100) and ν̃ ≈ 1.79e-05 sustained (`nozzleFlow2D_SA`). |
| `obliqueShock_KE`, `obliqueShock_LES` | `constant/physicalProperties` sets `mu 0`. OpenFOAM 10's `rhoCentralFoam/createFieldRefs.H` sets `inviscid = true` unless `max(mu) > 0`, and both `fvm::laplacian(muEff, U)` and `thermophysicalTransport->divq(e)` are guarded by `if (!inviscid)`. The k-epsilon / Smagorinsky fields were solved but never reached the momentum or energy equation. | `mu` set to 1.6646e-04, giving Re = ρUL/μ = 1e5 with ρ = 1.4, U = 2.9, L = 4.1. After the fix `nut_max/ν` = 137 (`obliqueShock_KE`, with k up to 0.084) and 21 (`obliqueShock_LES`). |

**Not corrected, recorded here as a benchmark-design property:** `Cavity/4`, `/7`, `/10` declare k-epsilon at
Re = 150, 200 and 300. Their turbulent kinetic energy collapses to the machine-epsilon floor (`k` = 2.22e-16,
`nut` ≈ 4e-18, with ~1200 `bounding k` warnings each) while the Re ≥ 1500 members of the family keep healthy
values. This is *correct* physics — a k-epsilon model at Re = 150 should predict negligible turbulence — so the
GT is not wrong; these three variants simply carry no turbulence signal and should not be read as evidence that
a submission modelled turbulence correctly.

## E. Files the ground truth ships but no tool reads

`similarity_report.py` grades a submission against the **GT file list**: a file present in the GT but absent
from a submission scores 0 and still counts in the denominator, while a file only the submission has is
ignored. Every such dead file therefore caps the structure score of an otherwise perfect answer.

These were proven dead rather than inferred: each candidate was deleted, the case re-run under OpenFOAM 10,
and the end-time result compared byte-for-byte with the unmodified run. **All 61 cases and 158 files: still
reach `End`, results bit-identical.** The list lives in `Dataset/dead_files_v1.json`.

| Removed | Cases | Why it is dead |
|---|---|---|
| `system/decomposeParDict` | 25 | every `Allrun` is serial; `decomposePar` is never invoked |
| `0/k` | 22 | the case is `laminar`, or the selected model does not read k |
| `0/alphat` | 20 | not read on the selected laminar / model path |
| `0/nut` | 20 | same |
| `system/functions` | 20 | `controlDict` already inlines the same `functions { #includeFunc ... }` block and nothing does `#include "functions"`. The `BernardCells` copy even uses the stale `name=` keyword where `controlDict` correctly uses OpenFOAM 10's `funcName=`, confirming it as a leftover from another version. |
| `0/epsilon` | 12 | wrong-model field |
| `0/nuTilda` | 12 | wrong-model field |
| `0/Ydefault` | 12 | every species has its own file, so the default template is never consulted |
| `0/omega` | 10 | laminar cases |
| `system/blockMeshDict1` | 5 | a header-less fragment, byte-identical across the five obstacle cases, referenced by nothing, describing a different mesh (10×15 cells vs the 50×25 / 100×50 actually used) |

Effect on scoring: the TreeScore ceiling for a perfect submission rises from a mean of **0.9416** — with 59 of
126 cases below 0.95 and `BernardCells` worst at 0.767 — to **1.000** for every case.

---

## Worked example: the shallow-water bump

`shallowWaterFoam` carries three quantities: bed elevation `h0`, water depth `h` (bed to surface), and the free
surface at `h0 + h`. The original tutorial (variant 1, background depth D = 0.01) is self-consistent:

```
background:  h0 = 0      h = 0.010   -> free surface 0.010
bump box:    h0 = 0.001  h = 0.009   -> free surface 0.010   (flat)
             hU = 0.0009 = 0.009 * 0.1 m/s ; background 0.001 = 0.010 * 0.1 m/s   (uniform 0.1 m/s)
```

The bump raises the bed by 0.001 m under a 0.1 × 0.1 m box; the override lowers `h` there so the initial free
surface is flat and the velocity uniform — "uniform flow over a submerged bump".

Variants 2–10 sweep D to 0.02 … 0.1 in both the prompt and the `setFieldsDict` default, but the bump override
keeps the D = 0.01 numbers:

```
variant 2:   background h = 0.020 -> surface 0.020 ; bump h = 0.009 -> surface 0.010   (a 0.010 m hole)
variant 10:  background h = 0.100 -> surface 0.100 ; bump h = 0.009 -> surface 0.010   (a 0.090 m hole)
             velocity 0.1 m/s inside the box vs 0.01 m/s outside
```

The initial condition is therefore no longer "uniform flow over a bump" but a collapsing hole, and the prompt's
"uniform water depth" and "uniform momentum field" contradict it. The correction restores the tutorial's own
construction per variant: `h_bump = D − 0.001`, `U = 0.001 / D`, `hU_bump = U · h_bump`. Applying that formula to
variant 1 reproduces the original bytes exactly, which is what validates it.

---

## How these defects were found: cross-validation between two models

No single reviewer found everything, and each of the three lines used here caught defects the others missed.

**Line 1 — mechanical scanning.** Python checks run directly on the JSON: solver name in the prompt versus
`controlDict application`; every numeric literal in the prompt versus every number in the GT; turbulence model
versus supplied fields; `controlDict` time settings versus the prompt; byte-identical GT or prompt text within a
family; outlet pressure BC versus the prompt. This found the stale variants (`counterFlowFlame2D/9`,
`obliqueShock/8`, `wedge` Pr) and the dead files. Its first version produced **180 findings that were all false
positives**, because three legitimate OpenFOAM constructs defeat naive parsing: nested BC sub-dictionaries (the
`uniformValue` key inside `uniformFixedValue` reads like a patch name), patch *groups* (`wall` legitimately
matches every patch of type `wall`, with `#includeEtc "caseDicts/setConstraintTypes"` covering the constraint
patches), and `defaultPatch { name walls; type wall; }`. Rewritten to parse by brace depth and to ask "does each
field file cover every mesh patch", it reported zero patch-name problems on the corrected data — and, run against
the *originals*, correctly re-found the known `defaultfaces` defect, which is what shows it is not vacuously clean.

**Line 2 — an agent that actually ran the cases.** All 126 cases were materialised and executed under
OpenFOAM 10, and the end-time `nut`, `nuTilda`, `k` and `epsilon` values read back. This is what exposed the
defects that are invisible statically: the SA cases whose eddy viscosity is exactly zero, the `mu 0` inviscid
branch (confirmed against `rhoCentralFoam`'s source), and the k-epsilon collapse at low Re.

**Line 3 — a static reviewer (gpt-5.6-sol).** Independent static analysis. It systematically covered patterns
across whole families — for instance flagging all ten `BernardCells` cases where a `RAS { model kEpsilon; }`
block sits under `simulationType laminar` — and it caught a bug in the patch itself: the `wedge` prompt reads
"Pr is 1.0", so replacing the substring "Pr is 1." produced the malformed "Pr is 0.71.0".

**Where they disagreed, measurement decided.** Three claims were adjudicated by running the cases:

- The `nutkWallFunction` misuse was rated MAJOR by the runtime reviewer and MINOR by the static one. Measurement
  supports MINOR: the corrected condition changes **no** cell.
- The runtime reviewer read `nut == nuTilda` at the maxima as the fingerprint of the wrong wall function. It is
  not: in SA, `nut = ν̃·f_v1` with `f_v1 = χ³/(χ³ + 7.1³)`, and χ ≈ 900 here, so `f_v1 ≈ 1` and the equality is
  ordinary SA behaviour.
- The runtime reviewer reported nine inconsistent `obliqueShock` variants. Recomputing the oblique-shock
  relations shows **four**: `/2`, `/6`, `/9`, `/10`. In `/3`, `/4`, `/5`, `/7` and `/8` the top state simply does
  not track the swept inlet, but it remains a valid compression (decelerating and heating), so those are not
  thermodynamically impossible.

**A verification pitfall worth recording.** OpenFOAM's `runApplication` refuses to re-run when `log.<application>`
already exists — it prints "already run … remove log file to re-run" and **returns success**. A re-run over a
directory that still holds an earlier run is therefore a silent no-op that looks like a pass. Several
intermediate results in this work were invalidated by exactly this and had to be redone; `Dataset/run_gt.sh`
now cleans each case before running. The same trap applies to scoring framework submissions.
