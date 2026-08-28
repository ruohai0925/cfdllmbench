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
    return d


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
