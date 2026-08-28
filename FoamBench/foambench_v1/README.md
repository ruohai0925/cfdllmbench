# foambench_v1 — corrected dataset and evaluation harness

Everything we changed about FoamBench lives here. The upstream files in the parent
directory (`../Dataset/FoamBench_*.json`, `../read_json_*.py`, `../run_benchmarks.py`,
`../execution_report.py`, `../similarity_report.py`, `../nmse_report.py`,
`../score_calculation.py`) are kept **unmodified**, so the difference between the
published benchmark and the one we run is exactly the contents of this directory.

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
    patch_dataset.py        regenerates the v1 JSONs from the untouched upstream JSONs
    unpack.py               unpacks v1 into Dataset/{Basic,Advanced} + per-case YAML
    run_gt.sh               runs every GT case under OpenFOAM 10
    run_benchmarks.py       drives MetaOpenFOAM over all 126 cases
    execution_report.py     M_exec
    similarity_report.py    M_file (ROUGE-L) and M_struct (TreeScore)
    nmse_report.py          M_NMSE
    score_calculation.py    aggregates the four into the final table
  results/
    gt_run_summary.tsv      status / wall-clock / last written time for all 126 GT runs
    *.csv                   scoring output (generated; not tracked)
  docs/                     working notes, kept local only (not tracked)
```

All tools resolve their paths against this directory, so they can be invoked from any
working directory. Scoring output always lands in `results/`.

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

## Quickstart

Regenerate the corrected JSONs from the untouched upstream ones (optional; the JSONs are
committed):

```bash
python tools/patch_dataset.py
```

Unpack the cases and write the per-case MetaOpenFOAM YAML:

```bash
python tools/unpack.py --force-yaml \
    --metagpt-path /abs/path/to/MetaGPT \
    --api-key "$FOAMBENCH_OPENAI_API_KEY" \
    --max-loop 10 --run-times 1
```

`unpack.py` writes no API key of its own and never overwrites an existing YAML unless
`--force-yaml` is given. `--original` unpacks the unmodified upstream JSONs instead.

Run the ground truth (needed before NMSE can be scored):

```bash
tools/run_gt.sh 12        # 12 parallel cases; each case itself is serial
```

Run the framework under test, then score:

```bash
python tools/run_benchmarks.py --mode all
python tools/execution_report.py
python tools/similarity_report.py
python tools/nmse_report.py
python tools/score_calculation.py    # -> results/final_benchmark_scores.csv
```

## Fixes to the scoring pipeline

Five bugs made a perfect submission unscoreable. Feeding the ground truth back in as a
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

`execution_report.py` now accepts both a flat case layout and one nested under a parent
directory; the three scoring scripts previously disagreed about which layout a submission
should have, and no single layout satisfied all of them.
