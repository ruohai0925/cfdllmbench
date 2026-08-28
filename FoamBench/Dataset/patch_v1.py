"""Generate FoamBench v1 datasets from the unmodified Kaggle originals.

Fixes 12 cases where the usr_requirement and GT disagree (see docs/AUDIT_requirement_vs_GT.md).
Policy "A": edit the requirement text so it fully specifies what the GT does; GT solver
settings are untouched, only dead template files that GT never reads are removed.

    python Dataset/patch_v1.py   # writes FoamBench_basic_v1.json / FoamBench_advanced_v1.json
"""
import json, os, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))

CAVITY_TURB_SENTENCE = (
    " Model turbulence with the standard k-epsilon RAS model (simulationType RAS, "
    "model kEpsilon), with uniform initial values k = 0.00375 m^2/s^2 and "
    "epsilon = 0.00754 m^2/s^3, nut initialised to 0, and standard wall functions on "
    "movingWall and fixedWalls (kqRWallFunction for k, epsilonWallFunction for epsilon, "
    "nutkWallFunction for nut)."
)
CAVITY_DEAD_FILES = ["0/omega", "0/nuTilda"]  # kEpsilon never reads these; template leftovers

KOMEGASST_CASES = ["Diamond_Obstacle_KOMEGASST", "Rectangular_Obstacle_KOMEGASST"]


def patch_stale_variants(d, log):
    """Generator-script slips: one side of a variant was swept, the other stayed at the template."""
    # obliqueShock/8: GT was swept (inlet 4.0, top 3.5) but the prose kept template velocities.
    v = d["obliqueShock/8"]
    assert "uniform (4.0 0 0)" in v["0/U"] and "uniform (3.5 -0.50632 0)" in v["0/U"], "obliqueShock/8 GT"
    old = "Use inlet velocity of 2.9 m/s and top velocity of (2.61933,-0.50632,0.0) m/s."
    assert old in v["usr_requirement"], "obliqueShock/8 req"
    v["usr_requirement"] = v["usr_requirement"].replace(
        old, "Use inlet velocity of 4.0 m/s and top velocity of (3.5,-0.50632,0.0) m/s.")
    log.append("obliqueShock/8: usr_requirement velocities 2.9/(2.61933,..) -> 4.0/(3.5,..) to match GT 0/U")

    # counterFlowFlame2D/9: prose was swept (0.4 / -0.3) but GT is a byte-identical copy of variant 1.
    # Policy A (edit prose) would make /9 a duplicate of /1, so here the GT 0/U is edited instead.
    v = d["counterFlowFlame2D/9"]
    assert "velocity of fuel is 0.4 m/s and velocity of air is -0.3 m/s" in v["usr_requirement"]
    assert {k: x for k, x in v.items() if k != "usr_requirement"} == \
           {k: x for k, x in d["counterFlowFlame2D/1"].items() if k != "usr_requirement"}, "cff/9 GT != cff/1 GT"
    u = v["0/U"]
    assert u.count("uniform (0.1 0 0)") == 1 and u.count("uniform (-0.1 0 0)") == 1
    v["0/U"] = u.replace("uniform (0.1 0 0)", "uniform (0.4 0 0)").replace("uniform (-0.1 0 0)", "uniform (-0.3 0 0)")
    log.append("counterFlowFlame2D/9: GT 0/U fuel/air 0.1/-0.1 -> 0.4/-0.3 to match usr_requirement (GT edit; reference fields must be re-run)")

    # wedge/7,8,10: GT Pr was swept (0.71 / 0.71 / 1.5) but every prose still says "Pr is 1".
    # mu = 0 (inviscid) so Pr does not affect the solution; this only fixes the wording / ROUGE on physicalProperties.
    import re
    for i in (7, 8, 10):
        v = d[f"wedge/{i}"]
        pr = re.search(r"Pr\s+([\d.]+);", v["constant/physicalProperties"]).group(1)
        assert pr in ("0.71", "1.5"), (i, pr)
        assert v["usr_requirement"].count("Pr is 1.") == 1, i
        v["usr_requirement"] = v["usr_requirement"].replace("Pr is 1.", f"Pr is {pr}.")
        log.append(f"wedge/{i}: usr_requirement 'Pr is 1' -> 'Pr is {pr}' to match GT physicalProperties")
    return d


def md5(p):
    return hashlib.md5(open(p, "rb").read()).hexdigest()


def patch_basic(d, log):
    for i in range(1, 11):
        k = f"Cavity/{i}"
        v = d[k]
        assert "kEpsilon" in v["constant/momentumTransport"], k
        assert "epsilon" not in v["usr_requirement"].lower(), k
        v["usr_requirement"] = v["usr_requirement"].rstrip() + CAVITY_TURB_SENTENCE
        removed = [f for f in CAVITY_DEAD_FILES if v.pop(f, None) is not None]
        log.append(f"{k}: appended k-epsilon sentence to usr_requirement; removed {removed}")
    return patch_stale_variants(d, log)


def patch_advanced(d, log):
    for k in KOMEGASST_CASES:
        v = d[k]
        assert "RASModel        kOmegaSST" in v["constant/turbulenceProperties"], k
        old = "using the k-epsilon RANS turbulence model"
        assert old in v["usr_requirement"], k
        v["usr_requirement"] = v["usr_requirement"].replace(old, "using the k-omega SST RANS turbulence model")
        log.append(f"{k}: usr_requirement 'k-epsilon' -> 'k-omega SST' (matches GT RASModel kOmegaSST)")
    return d


def main():
    log = []
    for name, fn in [("basic", patch_basic), ("advanced", patch_advanced)]:
        src = os.path.join(HERE, f"FoamBench_{name}.json")
        dst = os.path.join(HERE, f"FoamBench_{name}_v1.json")
        d = json.load(open(src, encoding="utf-8"))
        n_before = sum(len(v) for v in d.values())
        d = fn(d, log)
        n_after = sum(len(v) for v in d.values())
        with open(dst, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
        log.append(f"{name}: {len(d)} cases, {n_before} -> {n_after} keys; src md5 {md5(src)}; out md5 {md5(dst)}")
    print("\n".join(log))


if __name__ == "__main__":
    main()
