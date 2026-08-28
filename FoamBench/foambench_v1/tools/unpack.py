"""Unpack the FoamBench dataset JSONs into the directory layout the harness expects.

    Dataset/Basic/<family>/<1..10>/{usr_requirement.txt, GT_Files/...}
    Dataset/Advanced/<case>/{usr_requirement.txt, GT_Files/...}

`usr_requirement.txt` is the prompt handed to the framework under test; `GT_Files/` is
the reference answer, and is also where the ground-truth solver runs happen.

    python tools/unpack.py [--original] [--out DIR] [--upstream DIR]

--original unpacks the unmodified Kaggle JSONs from upstream/ instead of the corrected
v1 data in Dataset/.
"""
import argparse, json, os, stat

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                                  # foambench_v1/
DATASET = os.path.join(PKG, "Dataset")                       # our corrected data
# --original reads the unmodified Kaggle JSONs, tracked in upstream/.
UPSTREAM = os.environ.get("FOAMBENCH_UPSTREAM") or os.path.join(PKG, "upstream")


def unpack(json_path, out_root, split):
    data = json.load(open(json_path, encoding="utf-8"))
    n_case = n_file = 0
    for key, files in data.items():
        case_dir = os.path.join(out_root, split, *key.split("/"))
        gt_dir = os.path.join(case_dir, "GT_Files")
        os.makedirs(gt_dir, exist_ok=True)
        for rel, content in files.items():
            if rel == "usr_requirement":
                with open(os.path.join(case_dir, "usr_requirement.txt"), "w", encoding="utf-8") as f:
                    f.write(content)
                continue
            path = os.path.join(gt_dir, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            if os.path.basename(path).startswith("All"):
                os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            n_file += 1
        n_case += 1
    print(f"{split}: {n_case} cases, {n_file} GT files -> {os.path.join(out_root, split)}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--original", action="store_true",
                    help="unpack the unmodified Kaggle JSONs instead of the corrected v1 data")
    ap.add_argument("--out", default=DATASET,
                    help="where to unpack (default: foambench_v1/Dataset)")
    ap.add_argument("--upstream", default=UPSTREAM,
                    help="where the unmodified Kaggle JSONs live (only used with --original)")
    args = ap.parse_args()

    suffix = "" if args.original else "_v1"
    src_dir = args.upstream if args.original else DATASET
    unpack(os.path.join(src_dir, f"FoamBench_basic{suffix}.json"), args.out, "Basic")
    unpack(os.path.join(src_dir, f"FoamBench_advanced{suffix}.json"), args.out, "Advanced")


if __name__ == "__main__":
    main()
