"""Run Foam-Agent over the FoamBench cases.

    python tools/run_benchmarks.py --mode all
    python tools/run_benchmarks.py --only Basic/Cavity/1        # verify one case first

Foam-Agent's interface is a plain text prompt file and an output directory, which is
exactly what tools/unpack.py already lays down:

    Dataset/Basic/Cavity/1/
    ├── usr_requirement.txt   -> --prompt_path
    ├── GT_Files/             (the reference answer, untouched)
    └── foam_agent_run/       <- --output, written here

The output directory is the case root itself (services/plan.py resolve_case_dir returns
a supplied case_dir directly), so the submission lands flat, which is the layout the
three scoring scripts expect.

The RAG database is built once by Foam-Agent's own init_database.py, not per case.
"""
import argparse
import os
import subprocess
import sys

# Paths resolve against the foambench_v1/ package, not the caller's cwd.
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASIC_ROOT = os.path.join(PKG, "Dataset", "Basic")
ADVANCED_ROOT = os.path.join(PKG, "Dataset", "Advanced")
# The framework under test lives outside this package (it has its own git repo).
AGENT_ROOT = os.environ.get("FOAMAGENT_ROOT") or os.path.join(PKG, "upstream", "Foam-Agent")
# OpenFOAM 10 is the evaluation environment.
OPENFOAM_DIR = os.environ.get("WM_PROJECT_DIR") or "/opt/openfoam10"
# Name of the submission directory, a sibling of GT_Files. The scoring scripts take
# "the first sub-directory that is not GT_Files" as the submission, so there must be
# exactly one of these per case.
SUBMISSION = "foam_agent_run"


def agent_python():
    """Interpreter that has Foam-Agent's dependencies."""
    explicit = os.environ.get("FOAMAGENT_PYTHON")
    if explicit:
        return explicit
    env_python = os.path.join(AGENT_ROOT, "env", "bin", "python")
    return env_python if os.path.isfile(env_python) else sys.executable


def run(cmd, cwd):
    print("  $ " + " ".join(cmd), flush=True)
    try:
        subprocess.run(cmd, cwd=cwd, check=True)
        return True
    except subprocess.CalledProcessError as e:
        print(f"  failed: {e}", flush=True)
        return False


def database_is_built():
    db = os.path.join(AGENT_ROOT, "database")
    if not os.path.isdir(db):
        return False
    return any(name.startswith("faiss") for name in os.listdir(db))


def init_database(force=False):
    if database_is_built() and not force:
        print(f"RAG database already present in {os.path.join(AGENT_ROOT, 'database')}; "
              f"skipping (use --rebuild-db to force)", flush=True)
        return True
    print("Building the RAG database (once, not per case)", flush=True)
    cmd = [agent_python(), "-u", os.path.join(AGENT_ROOT, "init_database.py"),
           "--openfoam_path", OPENFOAM_DIR]
    if force:
        cmd.append("--force")
    return run(cmd, AGENT_ROOT)


def collect_cases(mode):
    """[(label, case_dir), ...] in the order they will be run."""
    cases = []
    if mode in ("basic", "all") and os.path.isdir(BASIC_ROOT):
        for dataset in sorted(os.listdir(BASIC_ROOT)):
            for case_id in range(1, 11):
                d = os.path.join(BASIC_ROOT, dataset, str(case_id))
                if os.path.isfile(os.path.join(d, "usr_requirement.txt")):
                    cases.append((f"Basic/{dataset}/{case_id}", d))
    if mode in ("advanced", "all") and os.path.isdir(ADVANCED_ROOT):
        for dataset in sorted(os.listdir(ADVANCED_ROOT)):
            d = os.path.join(ADVANCED_ROOT, dataset)
            if os.path.isfile(os.path.join(d, "usr_requirement.txt")):
                cases.append((f"Advanced/{dataset}", d))
    return cases


def run_case(case_dir):
    out = os.path.join(case_dir, SUBMISSION)
    cmd = [agent_python(), "-u", os.path.join(AGENT_ROOT, "foambench_main.py"),
           "--openfoam_path", OPENFOAM_DIR,
           "--output", out,
           "--prompt_path", os.path.join(case_dir, "usr_requirement.txt")]
    return run(cmd, AGENT_ROOT)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mode", choices=["basic", "advanced", "all"], default="all",
                    help="which split to run")
    ap.add_argument("--only", action="append",
                    help="run just this case, by the label printed below "
                         "(e.g. Basic/Cavity/1). Repeatable.")
    ap.add_argument("--rebuild-db", action="store_true",
                    help="rebuild the RAG database even if it is already present")
    ap.add_argument("--skip-db", action="store_true",
                    help="do not touch the RAG database at all")
    ap.add_argument("--skip-done", action="store_true",
                    help="skip cases that already have a submission directory")
    args = ap.parse_args()

    if not os.path.isfile(os.path.join(AGENT_ROOT, "foambench_main.py")):
        raise SystemExit(
            f"Foam-Agent not found at {AGENT_ROOT}\n"
            f"Run tools/fetch_upstream.sh, or set $FOAMAGENT_ROOT to its directory.")
    if not os.path.isdir(OPENFOAM_DIR):
        raise SystemExit(f"OpenFOAM not found at {OPENFOAM_DIR}; set $WM_PROJECT_DIR")

    cases = collect_cases(args.mode)
    if args.only:
        wanted = set(args.only)
        cases = [c for c in cases if c[0] in wanted]
        missing = wanted - {c[0] for c in cases}
        if missing:
            raise SystemExit(f"no such case(s): {', '.join(sorted(missing))}")
    if args.skip_done:
        cases = [c for c in cases if not os.path.isdir(os.path.join(c[1], SUBMISSION))]
    if not cases:
        raise SystemExit(f"no cases to run under {BASIC_ROOT} / {ADVANCED_ROOT} -- "
                         f"run tools/unpack.py first")

    print(f"Foam-Agent : {AGENT_ROOT}")
    print(f"python     : {agent_python()}")
    print(f"OpenFOAM   : {OPENFOAM_DIR}")
    print(f"cases      : {len(cases)} ({args.mode})", flush=True)

    if not args.skip_db and not init_database(force=args.rebuild_db):
        raise SystemExit("RAG database build failed; aborting before any case runs")

    failed = []
    for i, (label, case_dir) in enumerate(cases, 1):
        print(f"\n[{i}/{len(cases)}] {label}", flush=True)
        if not run_case(case_dir):
            failed.append(label)

    print(f"\n{len(cases) - len(failed)}/{len(cases)} cases completed", flush=True)
    if failed:
        print("failed: " + ", ".join(failed), flush=True)


if __name__ == "__main__":
    main()
