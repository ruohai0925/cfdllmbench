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
import re
import shutil
import signal
import subprocess
import sys
import time

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
# Model Foam-Agent runs with unless FOAMAGENT_MODEL_VERSION is set. Its own default,
# gpt-5.3-codex, is refused by the subscription backend ("not supported when using
# Codex with a ChatGPT account"); gpt-5.6-sol is accepted.
DEFAULT_MODEL = "gpt-5.6-sol"
# Wall-clock cap per case. Foam-Agent's own limits are max_loop=25 review iterations and
# max_time_limit=3600 s per solver run, neither overridable from the environment, so a
# case that keeps producing a non-terminating solver setup can occupy the machine for a
# day. Past the cap the whole process tree is killed and the case is recorded as failed.
# 15 minutes. The slowest ground-truth case solves in 399 s, so a correct submission
# never needs more than ~7 minutes of solver time. Of the 49 timed successful cases in
# the first 96, the median took 310 s and p90 463 s; three converged after 25-28 min and
# would be lost under this cap. Every case that failed did so within 18 min, and every
# timeout burned the full 30 min of quota, which is what the cap is here to limit.
DEFAULT_CASE_TIMEOUT = 15 * 60
RESULTS = os.path.join(PKG, "results")
RUN_SUMMARY = os.path.join(RESULTS, "foam_agent_run_summary.tsv")


def agent_python():
    """Interpreter that has Foam-Agent's dependencies."""
    explicit = os.environ.get("FOAMAGENT_PYTHON")
    if explicit:
        return explicit
    env_python = os.path.join(AGENT_ROOT, "env", "bin", "python")
    return env_python if os.path.isfile(env_python) else sys.executable


def agent_env():
    """Environment for Foam-Agent's own scripts. foambench_main.py re-invokes a bare
    `python src/main.py`, so the interpreter's directory has to lead PATH; and the
    OPENAI_API_KEY this machine keeps for other purposes must not leak in, because the
    framework is meant to authenticate through its own configured provider."""
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(agent_python()) + os.pathsep + env.get("PATH", "")
    env["WM_PROJECT_DIR"] = OPENFOAM_DIR
    env.setdefault("FOAMAGENT_MODEL_VERSION", DEFAULT_MODEL)
    env.pop("OPENAI_API_KEY", None)
    return env


def run(cmd, cwd):
    print("  $ " + " ".join(cmd), flush=True)
    try:
        subprocess.run(cmd, cwd=cwd, check=True, env=agent_env())
        return True
    except subprocess.CalledProcessError as e:
        print(f"  failed: {e}", flush=True)
        return False


# The four FAISS indices Foam-Agent retrieves from, under database/faiss/<embedding model>/.
DB_INDEXES = ["openfoam_tutorials_structure", "openfoam_tutorials_details",
              "openfoam_allrun_scripts", "openfoam_command_help"]


def database_is_built():
    """True when the pre-built indices for the configured embedding model are present
    and are real files. Foam-Agent ships them through git-LFS; a checkout without
    `git lfs pull` holds ~130-byte pointer files that look like a database but are not."""
    model = os.environ.get("FOAMAGENT_EMBEDDING_MODEL", "Qwen/Qwen3-Embedding-0.6B")
    model_dir = model.replace("/", "_").replace(":", "_")
    base = os.path.join(AGENT_ROOT, "database", "faiss", model_dir)
    for name in DB_INDEXES:
        idx = os.path.join(base, name, "index.faiss")
        if not os.path.isfile(idx) or os.path.getsize(idx) < 4096:
            return False
    return True


def init_database(force=False):
    if database_is_built() and not force:
        print(f"RAG database already present in {os.path.join(AGENT_ROOT, 'database')}; "
              f"skipping (use --rebuild-db to force)", flush=True)
        return True
    print("RAG database missing or still git-LFS pointers. If Foam-Agent was cloned "
          "without git-lfs, run `git lfs pull` in it first: the shipped database was built "
          "from the full OpenFOAM tutorial set, and a rebuild here only sees whatever "
          "tutorials this machine has.", flush=True)
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


def kill_processes_under(directory):
    """Kill every process whose working directory lies under `directory`. Foam-Agent's
    runner starts Allrun in a session of its own, so killing the case's process group
    leaves the solver behind; four reactingFoam orphans were found running 14-16 h
    after their cases had been timed out. Returns the pids killed."""
    directory = os.path.realpath(directory)
    killed = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            cwd = os.path.realpath(os.readlink(f"/proc/{pid}/cwd"))
        except OSError:
            continue
        if cwd == directory or cwd.startswith(directory + os.sep):
            try:
                os.kill(int(pid), signal.SIGKILL)
                killed.append(int(pid))
            except OSError:
                pass
    return killed


def run_case(case_dir, timeout):
    """Run one case; returns (status, seconds). status is 'ok', 'failed' or 'timeout'.
    The framework spawns python -> Allrun -> solver, so it is started in its own process
    group and the whole group is killed on timeout."""
    out = os.path.join(case_dir, SUBMISSION)
    cmd = [agent_python(), "-u", os.path.join(AGENT_ROOT, "foambench_main.py"),
           "--openfoam_path", OPENFOAM_DIR,
           "--output", out,
           "--prompt_path", os.path.join(case_dir, "usr_requirement.txt")]
    print("  $ " + " ".join(cmd), flush=True)
    t0 = time.time()
    proc = subprocess.Popen(cmd, cwd=AGENT_ROOT, env=agent_env(), start_new_session=True)
    try:
        rc = proc.wait(timeout=timeout)
        status = "ok" if rc == 0 else "failed"
        if rc != 0:
            print(f"  failed: exit status {rc}", flush=True)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait()
        status = "timeout"
        stray = kill_processes_under(out)
        if stray:
            print(f"  killed {len(stray)} stray process(es) still running in the case "
                  f"directory: {stray}", flush=True)
        os.makedirs(out, exist_ok=True)
        with open(os.path.join(out, "TIMEOUT"), "w") as f:
            f.write(f"killed after {timeout} s wall-clock (per-case cap of run_benchmarks.py)\n")
        print(f"  timeout: killed after {timeout} s; case recorded as failed", flush=True)
    return status, int(time.time() - t0)


def usage_limit_hit(case_dir):
    """If the framework died on the provider's usage limit, return the epoch time at which
    it resets (or now+1h when it did not say). Such a case produced no result: the
    submission directory is removed so the case is retried, not scored."""
    wf = os.path.join(case_dir, SUBMISSION, "workflow.log")
    try:
        txt = open(wf, errors="replace").read()
    except OSError:
        return None
    if "usage_limit_reached" not in txt:
        return None
    m = re.search(r'"resets_at":\s*(\d+)', txt)
    return int(m.group(1)) if m else int(time.time()) + 3600


# Provider-side failures that say nothing about the agent: a streamed response cut off,
# a gateway error, a dropped connection. A case that died on one of these before doing
# any review round is retried a bounded number of times rather than scored.
TRANSIENT_MARKERS = ("Response ended prematurely", "IncompleteRead", "ChunkedEncodingError",
                     "RemoteDisconnected", "Connection reset", "HTTP 502", "HTTP 503", "HTTP 504",
                     "Connection aborted")
TRANSIENT_RETRIES = 2


def transient_provider_error(case_dir):
    wf = os.path.join(case_dir, SUBMISSION, "workflow.log")
    try:
        txt = open(wf, errors="replace").read()
    except OSError:
        return False
    return any(m in txt for m in TRANSIENT_MARKERS)


def wait_for_usage_reset(resets_at):
    while True:
        remaining = resets_at + 60 - time.time()
        if remaining <= 0:
            return
        print(f"  provider usage limit reached; sleeping until "
              f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(resets_at + 60))} "
              f"({int(remaining // 60)} min)", flush=True)
        time.sleep(min(remaining, 600))


def record(label, status, seconds):
    os.makedirs(RESULTS, exist_ok=True)
    new = not os.path.exists(RUN_SUMMARY)
    with open(RUN_SUMMARY, "a") as f:
        if new:
            f.write("case\tstatus\tseconds\tfinished_at\n")
        f.write(f"{label}\t{status}\t{seconds}\t{time.strftime('%Y-%m-%dT%H:%M:%S')}\n")


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
    ap.add_argument("--case-timeout", type=int, default=DEFAULT_CASE_TIMEOUT, metavar="SECONDS",
                    help=f"wall-clock cap per case (default {DEFAULT_CASE_TIMEOUT}); "
                         f"on expiry the case is killed and recorded as failed")
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
    e = agent_env()
    print(f"model      : {e.get('FOAMAGENT_MODEL_PROVIDER', 'openai-codex (Foam-Agent default)')} / "
          f"{e['FOAMAGENT_MODEL_VERSION']}")
    print(f"cases      : {len(cases)} ({args.mode})")
    print(f"case cap   : {args.case_timeout} s", flush=True)

    if not args.skip_db and not init_database(force=args.rebuild_db):
        raise SystemExit("RAG database build failed; aborting before any case runs")

    failed = []
    for i, (label, case_dir) in enumerate(cases, 1):
        print(f"\n[{i}/{len(cases)}] {label}", flush=True)
        retries = 0
        while True:
            status, seconds = run_case(case_dir, args.case_timeout)
            if status != "failed":
                break
            resets_at = usage_limit_hit(case_dir)
            if resets_at is not None:
                # Not a result: the provider refused to serve. Discard and retry after the reset.
                shutil.rmtree(os.path.join(case_dir, SUBMISSION), ignore_errors=True)
                wait_for_usage_reset(resets_at)
                continue
            if transient_provider_error(case_dir) and retries < TRANSIENT_RETRIES:
                retries += 1
                print(f"  transient provider error; retry {retries}/{TRANSIENT_RETRIES}", flush=True)
                shutil.rmtree(os.path.join(case_dir, SUBMISSION), ignore_errors=True)
                time.sleep(60)
                continue
            break
        record(label, status, seconds)
        print(f"  -> {status} in {seconds} s", flush=True)
        if status != "ok":
            failed.append(f"{label} ({status})")

    print(f"\n{len(cases) - len(failed)}/{len(cases)} cases completed", flush=True)
    if failed:
        print("failed: " + ", ".join(failed), flush=True)


if __name__ == "__main__":
    main()
