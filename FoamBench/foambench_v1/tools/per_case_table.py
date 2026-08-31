"""Join the four report CSVs and the run summary into one row per case.

    python tools/per_case_table.py > results/foam_agent_scores_per_case.tsv

score_calculation.py only reports the two split-level means; this is the same data
before averaging, which is what a per-family or per-case comparison needs. The
NMSE thresholds and the Success rule are taken from score_calculation.py so the
columns here always add up to the numbers in final_benchmark_scores.csv.
"""
import os
import sys

import pandas as pd

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(PKG, "results")

COLUMNS = ["Split", "Dataset", "Directory", "status", "seconds",
           "Execution", "CodeBLEU", "TreeScore", "NMSE", "NMSE_Score", "Success"]


def score_nmse(v):
    return 1.0 if v < 0.1 else (0.5 if v < 0.3 else 0.0)


def load(split, exec_csv, sim_csv, nmse_csv):
    e = pd.read_csv(os.path.join(RESULTS, exec_csv))
    s = pd.read_csv(os.path.join(RESULTS, sim_csv))
    n = pd.read_csv(os.path.join(RESULTS, nmse_csv))
    for df in (e, s, n):
        df["key"] = df["Dataset"].astype(str) + "_" + df["Directory"].astype(str)
    m = e.merge(s, on="key", suffixes=("", "_s")).merge(n, on="key", suffixes=("", "_n"))
    m["Split"] = split
    m["NMSE_Score"] = m["NMSE"].apply(score_nmse)
    m["Success"] = ((m["Execution"] == 1) & (m["NMSE_Score"] == 1)).astype(int)
    return m


def main():
    basic = load("Basic", "basic_success_report.csv", "similarity_report_basic.csv",
                 "basic_nmse_report.csv")
    adv = load("Advanced", "advanced_success_report.csv", "similarity_report_advanced.csv",
               "advanced_nmse_report.csv")
    all_ = pd.concat([basic, adv], ignore_index=True)

    # The run summary labels cases as Basic/<family>/<n> and Advanced/<case>; the reports
    # split that into Dataset + Directory. Rejoin so run status sits beside the scores.
    summary = os.path.join(RESULTS, "foam_agent_run_summary.tsv")
    if os.path.isfile(summary):
        run = pd.read_csv(summary, sep="\t")
        parts = run["case"].str.split("/", expand=True)
        run["Split"] = parts[0]
        run["Dataset"] = parts[1]
        run["Directory"] = parts[2].fillna("1")
        run = run[["Split", "Dataset", "Directory", "status", "seconds"]]
        all_["Directory"] = all_["Directory"].astype(str)
        run["Directory"] = run["Directory"].astype(str)
        all_ = all_.merge(run, on=["Split", "Dataset", "Directory"], how="left")
    else:
        all_["status"] = ""
        all_["seconds"] = ""

    all_ = all_[COLUMNS]
    all_.to_csv(sys.stdout, sep="\t", index=False, float_format="%.4f")


if __name__ == "__main__":
    main()
