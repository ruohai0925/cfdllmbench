import os
import csv
import pandas as pd

# Paths resolve against the foambench_v1/ package, not the caller's cwd,
# so these tools can be run from anywhere.
PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET = os.path.join(PKG, "Dataset")
RESULTS = os.path.join(PKG, "results")
os.makedirs(RESULTS, exist_ok=True)

def analyze_basic_structure(base_dir):
    dataset_path = os.path.join(base_dir, "Basic")
    datasets = os.listdir(dataset_path)
    results = []

    for dataset in datasets:
        dataset_dir = os.path.join(dataset_path, dataset)
        if not os.path.isdir(dataset_dir):
            continue

        for i in range(1, 11):
            case_dir = os.path.join(dataset_dir, str(i))
            if not os.path.exists(case_dir):
                continue

            run_folders = [f for f in os.listdir(case_dir)
                           if os.path.isdir(os.path.join(case_dir, f)) and f != "GT_Files"]
            if not run_folders:
                results.append([dataset, i, 0])
                continue

            run_path = os.path.join(case_dir, run_folders[0])
            success = 0

            # os.walk already yields every directory including run_path itself, so scan
            # `files` here: the previous version only looked inside `dirs`, which missed a
            # solver log sitting directly in the run folder.
            # A case the harness killed at its wall-clock cap is a failure whatever its
            # directory holds afterwards: the solver Foam-Agent launched can outlive the
            # kill and finish on its own hours later, leaving a log that ends with End.
            if os.path.exists(os.path.join(run_path, "TIMEOUT")):
                results.append([dataset, i, 0])
                continue
            for root, dirs, files in os.walk(run_path):
                for folder_path in [root]:
                    log_files = [f for f in files if f.startswith("log.") and f.endswith("Foam")]
                    for log_file in log_files:
                        log_path = os.path.join(folder_path, log_file)
                        try:
                            with open(log_path, "r") as file:
                                lines = file.readlines()
                                last_line = lines[-2].strip() if len(lines) > 1 else ""
                                if last_line == "End":
                                    success = 1
                                    break
                        except:
                            continue
                    if success:
                        break
                if success:
                    break

            results.append([dataset, i, success])
    return results


def analyze_advanced_structure(base_dir):
    dataset_path = os.path.join(base_dir, "Advanced")
    datasets = os.listdir(dataset_path)
    results = []

    for dataset in datasets:
        case_dir = os.path.join(dataset_path, dataset)
        if not os.path.isdir(case_dir):
            continue

        run_folders = [f for f in os.listdir(case_dir)
                       if os.path.isdir(os.path.join(case_dir, f)) and f != "GT_Files"]
        if not run_folders:
            results.append([dataset, 1, 0])
            continue

        run_path = os.path.join(case_dir, run_folders[0])
        success = 0

        for root, dirs, files in os.walk(run_path):
            for folder_path in [root]:
                log_files = [f for f in files if f.startswith("log.") and f.endswith("Foam")]
                for log_file in log_files:
                    log_path = os.path.join(folder_path, log_file)
                    try:
                        with open(log_path, "r") as file:
                            lines = file.readlines()
                            last_line = lines[-2].strip() if len(lines) > 1 else ""
                            if last_line == "End":
                                success = 1
                                break
                    except:
                        continue
                if success:
                    break
            if success:
                break

        results.append([dataset, 1, success])

    return results

base_dir = DATASET
basic_results = analyze_basic_structure(base_dir)
advanced_results = analyze_advanced_structure(base_dir)

pd.DataFrame(basic_results, columns=["Dataset", "Directory", "Execution"]).to_csv(os.path.join(RESULTS, "basic_success_report.csv"), index=False)
pd.DataFrame(advanced_results, columns=["Dataset", "Directory", "Execution"]).to_csv(os.path.join(RESULTS, "advanced_success_report.csv"), index=False)

print("✅ Reports saved: 'basic_success_report.csv' and 'advanced_success_report.csv'")
