# Two Models on FoamBench: claude-opus-5 vs gpt-5.6-sol

Two complete runs of the 126-case FoamBench v1 suite through
[Foam-Agent](https://github.com/csml-rpi/Foam-Agent), changing the language model and
nothing else. Scored 2026-08-31 with the benchmark's own unmodified report scripts.

**Headline:** the three structural metrics barely move between two models a generation
apart, while the Success ratio roughly doubles on both splits. Whatever this benchmark
discriminates, it discriminates through NMSE — through whether the simulation produced
the right numbers, not whether it produced a plausible-looking case directory.

---

## 1. What was held constant, and what was varied

A model comparison is only worth reporting if exactly one thing changed. Foam-Agent's
behaviour was not modified between the two runs; the difference is entirely in environment
variables. (One exception, introduced after both runs were complete and quantified as
zero-effect: 13 cases were rerun on a patched framework — see §5.2 and caveat 3.)

**Held constant**

| | |
|---|---|
| Dataset | FoamBench v1 — 110 Basic + 16 Advanced cases |
| Prompts | byte-identical, unmodified between runs |
| Embedding model | `Qwen/Qwen3-Embedding-0.6B` |
| Retrieval | the same pre-built FAISS indices |
| Agent | Foam-Agent, `max_loop = 25`, `run_times = 1` |
| Solver | OpenFOAM 10, serial |
| Scoring | the same four report scripts, unmodified |

**Varied**

| | Run 1 | Run 2 |
|---|---|---|
| Model | `gpt-5.6-sol` | `claude-opus-5` |
| Reasoning effort | medium | high |
| Transport | Foam-Agent's `openai-codex` provider | local OpenAI-compatible bridge over the Claude Code CLI |

The effort levels are not symmetric, and cannot be made so without changing Foam-Agent.
Its Codex provider builds its own request body with no effort field, so run 1 ran at
whatever the backend defaults to — confirmed as `medium` by reading back the echoed
request configuration. Run 2 passes `--effort high` explicitly. The honest label for this
comparison is therefore "opus-5 at high effort vs gpt-5.6 at medium effort", not
"opus-5 vs gpt-5.6" (see caveat 4).

---

## 2. Headline scores

Execution asks whether the case ran to completion. CodeBLEU and Tree ask whether the
generated files resemble the reference. NMSE asks whether the computed fields match it.
Success requires both a clean run and NMSE below 0.1.

### Basic — 110 cases

| Model | Execution | CodeBLEU | Tree | NMSE | **Success** |
|---|---|---|---|---|---|
| gpt-5.6-sol (medium) | 0.791 | 0.717 | 0.947 | 0.255 | **0.218** |
| claude-opus-5 (high) | 0.782 | 0.750 | 0.938 | **0.409** | **0.391** |
| change | −0.009 | +0.034 | −0.009 | **+0.154** | **+0.173** |

### Advanced — 16 cases

| Model | Execution | CodeBLEU | Tree | NMSE | **Success** |
|---|---|---|---|---|---|
| gpt-5.6-sol (medium) | 0.750 | 0.620 | 0.842 | 0.156 | **0.125** |
| claude-opus-5 (high) | **0.875** | 0.612 | 0.818 | **0.250** | **0.250** |
| change | +0.125 | −0.008 | −0.024 | **+0.094** | **+0.125** |

Tree stays at 0.94, CodeBLEU near 0.72, and neither moves by more than 0.034. Both
structural metrics are saturated and were already saturated in run 1; they cannot
separate these two systems. Success and NMSE move by 0.17 and 0.15.

---

## 3. Per-family breakdown

Success ratio and its components, per case family. Six of the twelve groups score zero
for both models — those are the benchmark's genuinely unsolved problems, not a
difference between the two systems.

| Family | n | Execution | Tree | NMSE score | **Success** |
|---|---|---|---|---|---|
| | | claude / gpt | claude / gpt | claude / gpt | claude / gpt |
| Cavity | 10 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 0.60 | **1.00 / 0.40** |
| forwardStep | 10 | 1.00 / 1.00 | 1.00 / 1.00 | 0.90 / 0.10 | **0.80 / 0.10** |
| pitzDaily | 10 | 0.60 / 1.00 | 1.00 / 1.00 | 0.60 / 0.20 | **0.60 / 0.20** |
| wedge | 10 | 1.00 / 1.00 | 1.00 / 1.00 | 1.00 / 0.90 | **1.00 / 0.90** |
| obliqueShock | 10 | 1.00 / 1.00 | 1.00 / 1.00 | 0.90 / 0.90 | **0.90 / 0.80** |
| Advanced | 16 | 0.88 / 0.75 | 0.82 / 0.84 | 0.25 / 0.16 | **0.25 / 0.13** |
| BernardCells | 10 | 1.00 / 1.00 | 0.93 / 0.93 | 0 / 0 | 0 / 0 |
| Cylinder | 10 | 1.00 / 1.00 | 1.00 / 1.00 | 0 / 0 | 0 / 0 |
| damBreakWithObstacle | 10 | 1.00 / 0.90 | 0.75 / 0.90 | 0 / 0 | 0 / 0 |
| shallowWaterWithSquareBump | 10 | 1.00 / 0.70 | 0.76 / 0.71 | 0 / 0.05 | 0 / 0 |
| squareBend | 10 | 0.00 / 0.10 | 1.00 / 1.00 | 0.10 / 0 | 0 / 0 |
| counterFlowFlame2D | 10 | 0.00 / 0.00 | 0.88 / 0.88 | 0 / 0.05 | 0 / 0 |

**forwardStep is the clearest illustration of the headline.** GPT-5.6 ran all ten
variants to completion — Execution 1.00 — and produced NMSE values around 10<sup>8</sup>
on seven of them. The case directories were valid; the answers were off by eight orders
of magnitude. Opus 5 takes the family to 0.80 Success. A benchmark that stopped at
Execution would have scored those ten cases as a tie.

**pitzDaily is the one regression**, and it is a wall-clock effect rather than a
correctness one: Execution drops from 1.00 to 0.60 because four cases hit the 15-minute
per-case cap. Success still rises from 0.20 to 0.60, so the six cases that did finish
were solved more accurately.

---

## 4. Run status and failure attribution

Run status is not the Execution score. A case can crash the agent and still leave behind
a directory that runs; a case can finish cleanly and score zero. They are reported
separately here on purpose.

| Outcome | Count | Meaning |
|---|---|---|
| ok | 102 | agent completed its workflow |
| timeout | 24 | hit the 15-minute per-case cap |
| failed | 0 | — |

As first run, this was 95 ok / 18 timeout / 13 failed. All 13 failures came from a single
Foam-Agent defect (§5.2); after fixing it and rerunning those cases, seven complete and six
time out. **The split-level scores are unchanged by the fix** — see §5.2.

The 24 timeouts are concentrated in three families: 12 counterFlowFlame2D (the entire
family, including both Advanced variants), 8 squareBend, 4 pitzDaily.

**Not one failure was a wrong answer from the model.** As first run, the 13 failures broke
down as:

| Failure mode | Cases | Detail |
|---|---|---|
| Prompt above the CLI's 10 MB stdin limit | 9 | damBreak `/1 /5 /7 /8 /9`, squareBend `/1 /3 /6 /10` |
| Prompt 1.6–7.7 MB, accepted by transport but beyond the context window | 4 | squareBend `/2 /5 /7 /8` |

One further case, `Cylinder/4`, produced an unexplained empty request on a 0.01 MB
prompt. It was discarded as provider noise and rerun clean in 250 s, following the same
protocol already applied to quota and stream errors in run 1.

---

## 5. Findings

### 5.1 Both models miss the same switch, for the same reason

Every counterFlowFlame2D variant scores zero in both runs — 12 of 12 including the two
Advanced variants. The prompt is upstream's own wording, unedited by us, and ends with
*"…and deltaT of 1e-6."* It says nothing about adaptive time stepping. The reference
solution treats `1e-6` as a *starting* step:

```
reference   deltaT 1e-6;   adjustTimeStep yes;   maxCo 0.4;   → finishes in 48 s
both models deltaT 1e-6;   adjustTimeStep no;    maxCo 0.4;   → 500,000 fixed steps
```

Both models wrote `maxCo 0.4` — the reference value, so both knew what Courant limit
this case wants — and both left `adjustTimeStep` off, which makes `maxCo` a dead
parameter sitting in the same dictionary as the setting that contradicts it.

This is not "neither model thought of adaptive stepping". Both thought about the Courant
limit and did not flip the switch: numbers stated in the prompt were implemented
literally, and switches absent from the prompt kept their defaults, even where the two
choices contradict each other.

The physics was otherwise correct. In run 1 an orphaned solver process escaped the
timeout, finished the case on its own, and scored **NMSE 0.025** — mesh, chemistry and
boundary conditions all right, only the stepping strategy wrong.

The underlying issue is a prompt-versus-reference inconsistency in the dataset: following
the prompt literally cannot reproduce the reference. It is reproduced independently by
two vendors' models, which makes it a property of the task specification rather than of
either model. We deliberately did not edit these prompts — real user input is imperfect,
and the benchmark should reflect that.

### 5.2 The agent feeds the solver's own output back into its prompt

All 13 failures trace to one behaviour in Foam-Agent. `scan_case_directory()` collects
every directory one level below the case root, which includes the time directories the
solver has just written; `review_error_logs()` then embeds all of them verbatim in the
reviewer prompt.

| Directory | Size |
|---|---|
| `0/` (the actual initial fields) | 0.1 MB |
| `0.02`, `0.04`, `0.06`, `0.08`, `0.1` (solver output) | 4.5 MB each |
| **total `<foamfiles>` payload** | **22.5 MB ≈ 5.6M tokens** |

(`constant/polyMesh/`, at 4.7 MB, is *not* included — it sits two levels down, and the
scan only descends one.)

This is model-independent: no backend accepts 5.6M tokens. The two transports simply fail
differently — the Claude CLI refuses at its 10 MB stdin limit, while an HTTP transport
sends the request and receives a context-length error. GPT-5.6 completed the same four
squareBend and five damBreak cases only because its review rounds happened to occur
*before* the solver had written any output. That is timing, not immunity.

### The fix, and what it changed

`scan_case_directory()` now skips directories the solver wrote — any float-named directory
(a written time step) plus `processor*`, `postProcessing`, `VTK`, `dynamicCode` — while
keeping `0` and `0.orig`, which are initial conditions and part of the case. The same case
then scans to 0.079 MB with `0/`, `constant/` and `system/` intact.
([upstream PR](https://github.com/csml-rpi/Foam-Agent/pull/42))

This removes no diagnostic information. Error logs reach the reviewer through
`check_foam_errors()`, which reads `log*` files at the **case root** — a separate path that
`scan_case_directory()` never covered, since it only ever collected subdirectories. A 116 KB
`log.interFoam` carries 201 Courant-number readings plus continuity errors and bounding
warnings; the time directories only added per-cell field values.

Nor is the fix a workaround for the CLI. Measured per case, 11 of the 13 prompts exceed
1M tokens (up to 14M for `squareBend/10`) and would be rejected by any backend. The
arithmetic is decisive: 10 MB of text is roughly 2.5M tokens, so the CLI's stdin cap sits
2.5× beyond a 1M context window and can never reject a request a model would have accepted.

Rerunning the 13 on the patched framework: **failures go to zero** — five damBreak cases and
two squareBend cases now complete (188–346 s), six squareBend cases time out instead.

**And the scores do not move.** Basic Execution, Tree, NMSE and Success are bit-identical
before and after; Basic CodeBLEU shifts from 0.7508 to 0.7505; Advanced is untouched. The
damBreak cases already scored Execution 1 (the solver had finished before the crash) and
their NMSE stays far above threshold, 14.6–43.6 before against 3.1–87.2 after. squareBend
scores Execution 0 either way. Per-case detail is in
`results/claude-opus-5-high/prefix_vs_postfix.tsv`.

**Consequence for scoring:** the defect cost 13 runs and zero benchmark points, because it
only struck in two families that score zero regardless. The comparison in §2 and §3 is not
contaminated by it. A useful side effect: squareBend's zero is now visibly *not* the
framework's doing — the family fails on its own merits, 6 timeouts and Execution 0, matching
GPT-5.6's 0.10 Execution on the same family.

### 5.3 Reasoning effort is auditable on only one of the two paths

Run 1's effort level was never a choice. Foam-Agent's Codex provider constructs its own
request body with no effort field, so the backend default applied throughout; the local
CLI configuration never reaches it. We confirmed the effective value by reading back the
echoed request configuration: `{effort: "medium", mode: "standard"}`, with no output
token limit.

Run 2 sets `--effort high` explicitly, and the setting is verifiable per call. On one
identical prompt, the same model returns **90 thinking tokens at `low` and 1,198 at
`high`**. Across the full run: 874k thinking tokens over 3,042 calls.

An effort ablation on the GPT side would require adding a `reasoning.effort` field to
Foam-Agent's request builder — a one-line change, but one that changes the experimental
condition and requires a full re-run.

---

## 6. Caveats

Everything below is known and quantified, and none of it changes the headline conclusion.
It is listed because a reviewer will ask.

1. **The per-case time cap was not uniform in run 1.** Run 2 capped every case at 15
   minutes. Run 1's cap evolved during the run from 2 h to 30 min to 15 min, so 11 of its
   timeouts consumed 1800 s and one consumed 4020 s. Three GPT cases that *succeeded* did
   so past 15 minutes — `forwardStep/9` (1571 s), `squareBend/1` (1662 s), `squareBend/4`
   (1514 s) — and would have been killed under run 2's cap. All three already scored
   Success 0, and two already scored Execution 0, so a uniform cap would cost run 1 at
   most 0.009 of Basic Execution and nothing at all on Success. The asymmetry favours
   run 1 and does not reach the headline metric.

2. **Five cases have status `failed` but Execution 1** — damBreak `/1 /5 /7 /8 /9`. The
   framework crashed during review, but the solver had already finished and its log ends
   in `End`, which is what the Execution rule tests. Their NMSE is 14.6–43.6, so Success
   is 0 regardless. Report run status and Execution as separate columns, never as one
   number.

3. **13 of run 2's cases ran on a patched framework.** They failed on the original one
   because of the defect in §5.2, were rerun after it was fixed, and are reported here in
   their post-fix state. The other 113 cases of run 2, and all 126 of run 1, ran on the
   unpatched framework. This is the single break in "only the model changed", and its
   measured effect on the scores is zero: every split-level metric is bit-identical before
   and after except Basic CodeBLEU, which moves by 0.0003. The pre-fix submissions are
   retained.

4. **Effort differs between runs and cannot be equalised downward.** Medium was imposed
   on run 1 by its transport, not chosen. Until an ablation is run, the comparison is
   "opus-5 high vs gpt-5.6 medium".

5. **One run per case, so no error bars.** Error bars would require running the whole
   benchmark end-to-end N times and scoring each pass separately — not raising
   Foam-Agent's `run_times`, which would leave several submissions per case and make
   "which one is scored" arbitrary.

6. **Timeouts are scored as failures.** A timed-out case receives Execution 0 and
   NMSE 9999. Under a longer cap, some of the 18 might have completed; counterFlowFlame2D
   demonstrably would not (§5.1 — 500,000 fixed steps is roughly 28 hours of serial
   solver time).

---

## 7. Reproducing this

Neither run can overwrite the other. A case directory holds exactly one submission,
because the scoring scripts take "the first sub-directory that is not `GT_Files`" as the
submission. Both runs are therefore parked outside `Dataset/`, and either can be brought
back for re-scoring with one command.

| Path | Contents |
|---|---|
| `results/gpt-5.6-sol/` | run 1 score tables |
| `results/claude-opus-5-high/` | run 2 score tables |
| `results/runs/<tag>/` | 126 submissions per run (git-ignored — tens of GB) |
| `tools/archive_run.py` | park a finished run / restore it for re-scoring |
| `tools/claude_bridge.py` | local OpenAI-compatible endpoint over the Claude Code CLI |
| `tools/run_benchmarks.py --backend {codex,claude}` | run the suite on either backend |
| `tools/per_case_table.py` | join the four report CSVs into one row per case |

```bash
# run 2, from scratch
python tools/claude_bridge.py &
python tools/run_benchmarks.py --backend claude --mode all --case-timeout 900

# score whichever run is currently in Dataset/
python tools/execution_report.py
python tools/similarity_report.py
python tools/nmse_report.py
python tools/score_calculation.py
python tools/per_case_table.py > results/foam_agent_scores_per_case.tsv

# swap runs
python tools/archive_run.py --archive claude-opus-5-high
python tools/archive_run.py --restore gpt-5.6-sol
```

### Why a bridge

Foam-Agent's `anthropic` provider builds a `ChatAnthropic` client, which requires a
metered API key. Its stock `openai` provider goes through `ChatOpenAI`, which honours
`OPENAI_BASE_URL` — so pointing that at a local endpoint turns each of Foam-Agent's ~22
call sites into one `claude -p` invocation, with no change to Foam-Agent itself and no
API key involved. The CLI is reduced to a plain text completion: all built-in tools
disabled, project context and customisations disabled, prompts passed on stdin, sessions
not persisted. Structured outputs (six Pydantic-validated call sites) are handled by
appending the JSON schema to the prompt and extracting the object from the reply — 0
retries were needed across all 3,042 calls.

---

## Run economics

| | Run 1 (gpt-5.6-sol) | Run 2 (claude-opus-5) |
|---|---|---|
| Case wall-clock | 18.8 h | 11.1 h |
| Elapsed | ~43 h across 6 quota windows | 11.1 h, uninterrupted |
| LLM calls | not reliably instrumented | 3,042 |
| Quota stalls | 6 | 0 |
| Structured-output retries | — | 0 |
| Tokens | — | 20.0M in / 2.21M out / 874k thinking |

Plus a 13-case rerun after the framework fix (§5.2), roughly 2 h.
