# foambench_v1 — corrected dataset and evaluation harness

Everything we changed about FoamBench lives here. The upstream files in the parent
directory (`../Dataset/`, `../read_json_*.py`, `../run_benchmarks.py`,
`../execution_report.py`, `../similarity_report.py`, `../nmse_report.py`,
`../score_calculation.py`) are kept **unmodified**, so the difference between the
published benchmark and the one we run is exactly the contents of this directory.

This directory is self-contained: take it on its own, run `tools/fetch_upstream.sh` to
pull in the framework under test, and everything works. Every tool resolves its paths
relative to this directory rather than the caller's working directory.

## Layout

```
foambench_v1/
  CHANGELOG.md            authoritative, per-case record of every dataset change (English)
  Dataset/
    FoamBench_basic_v1.json      corrected Basic split   (110 cases)
    FoamBench_advanced_v1.json   corrected Advanced split (16 cases)
    dead_files_v1.json           158 files across 61 cases proven to have no effect
    Basic/  Advanced/            unpacked cases (generated; not tracked)
  tools/
    fetch_upstream.sh       clones Foam-Agent into upstream/
    patch_dataset.py        regenerates the v1 JSONs from the untouched upstream JSONs
    unpack.py               unpacks v1 into Dataset/{Basic,Advanced}
    run_gt.sh               runs every ground-truth case under OpenFOAM 10
    run_benchmarks.py       drives Foam-Agent over the cases
    execution_report.py     M_exec
    similarity_report.py    M_file (ROUGE-L) and M_struct (TreeScore)
    nmse_report.py          M_NMSE
    score_calculation.py    aggregates the four into the final table
  results/
    gt_run_summary.tsv      status / wall-clock / last written time for all 126 GT runs
    *.csv                   scoring output (generated; not tracked)
  upstream/
    FoamBench_basic.json    the unmodified Kaggle originals, tracked so that
    FoamBench_advanced.json patch_dataset.py can re-derive v1 offline
    Foam-Agent/             the framework under test; not tracked (own git repo),
                            cloned by tools/fetch_upstream.sh
  docs/                     working notes, kept local only (not tracked)
```

Scoring output always lands in `results/`.

## Why a corrected dataset

104 of the 126 cases were changed. The defects fall into five classes, recorded case by
case with reason and content in `CHANGELOG.md`:

- **A** — the prompt contradicts the ground truth
- **B** — the ground truth contradicts the prompt
- **C** — the ground truth is internally inconsistent or physically impossible
- **D** — a turbulence model is declared but has no effect on the solution
- **E** — dead files that no solver reads

Class E matters for scoring rather than physics: removing the 158 dead files raises the
TreeScore ceiling for a perfect submission from a mean of 0.9416 (59 cases below 0.95,
worst 0.767) to exactly 1.000. Every deletion was verified empirically — the case was
re-run without the file and produced bit-identical results at the end time.

## Case layout

One directory per case, holding the prompt, the reference answer, and the submission:

```
Dataset/Basic/Cavity/1/
├── usr_requirement.txt   the prompt handed to the framework under test
├── GT_Files/             reference answer; the ground-truth solver runs here too
└── foam_agent_run/       the submission

Dataset/Advanced/Cavity_SA/     same, one level shallower
```

The scoring scripts take *the first sub-directory that is not `GT_Files`* as the
submission, so a case must hold exactly one submission directory, and that directory must
be the OpenFOAM case root itself rather than a parent of it.

## Quickstart

Set up OpenFOAM 10 and the Python dependencies, then fetch the framework under test:

```bash
source /opt/openfoam10/etc/bashrc          # never source this under `set -u`
export WM_PROJECT_DIR=/opt/openfoam10
pip install pandas pyvista rouge-score     # for the scoring scripts
tools/fetch_upstream.sh                    # clones Foam-Agent and pulls its git-LFS database
conda create -p upstream/Foam-Agent/env python=3.12 pip git-lfs -c conda-forge
upstream/Foam-Agent/env/bin/pip install -e "upstream/Foam-Agent[all]" sentence-transformers
```

Two things about Foam-Agent's setup are easy to miss. Its pre-built RAG database (FAISS
indices over the full OpenFOAM tutorial set) is stored in git-LFS, so a clone without
`git lfs pull` holds pointer files that look like a database but are not;
`run_benchmarks.py` checks for this and refuses to rebuild from whatever tutorials happen
to be on the machine. And `src/utils.py` imports the Bedrock and Ollama clients
unconditionally, so the `[all]` extras are required even though only one provider is
used.

Regenerate the corrected JSONs from the untouched originals (optional; the v1 JSONs are
committed, so a user who only wants to run the benchmark can skip this step):

```bash
python tools/patch_dataset.py
```

Unpack the cases, then run the ground truth — this is what NMSE is scored against, so it
has to happen before the last step:

```bash
python tools/unpack.py
tools/run_gt.sh 12        # 12 cases at a time; each case itself is serial
```

Run the framework under test, then score:

```bash
python tools/run_benchmarks.py --only Basic/Cavity/1   # verify one case first
python tools/run_benchmarks.py --mode all
python tools/execution_report.py
python tools/similarity_report.py
python tools/nmse_report.py
python tools/score_calculation.py    # -> results/final_benchmark_scores.csv
```

`run_benchmarks.py` builds Foam-Agent's RAG database once rather than once per case
(`--rebuild-db` / `--skip-db` control it), takes `--only <label>` to run a single case,
and `--skip-done` to resume. Which model Foam-Agent uses is its own configuration, read
from `FOAMAGENT_MODEL_PROVIDER` / `FOAMAGENT_MODEL_VERSION`; `FOAMAGENT_ROOT` and
`FOAMAGENT_PYTHON` override where it lives and which interpreter runs it.

## Fixes to the scoring pipeline

Six bugs made a perfect submission unscoreable. Feeding the ground truth back in as a
submission scored `Execution 0.0 / CodeBLEU 0.996` before and `1.0` on every metric
after:

1. `execution_report.py` read a column named `Success` that is written as `Execution`.
2. `execution_report.py` walked the case tree but never inspected the files of each root
   it visited, so a solver log in the case directory itself was missed.
3. `similarity_report.py` returned `""` for any file that is not valid UTF-8, scoring
   byte-identical binary fields as 0.
4. `similarity_report.py` scored an empty-vs-empty comparison as 0 instead of 1.
5. `similarity_report.py` dropped a missing sub-directory from the mean instead of
   scoring it 0, so omitting `constant/` entirely improved the score.
6. `nmse_report.py` iterated each Basic family over a hardcoded 1..10 and called
   `os.listdir` on every one, so a family holding fewer than ten cases aborted the whole
   report with `FileNotFoundError`.

`execution_report.py` now accepts both a flat case layout and one nested under a parent
directory; the three scoring scripts previously disagreed about which layout a submission
should have, and no single layout satisfied all of them.

The upstream files themselves are left untouched, so the upstream `README.md` still names
the execution output `execution_status_basic.csv` / `execution_status_advanced.csv`. No
script writes those; the files are `basic_success_report.csv` and
`advanced_success_report.csv`, and here they land in `results/`.
