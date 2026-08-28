"""Unpack the v1 dataset JSONs into the FoamBench directory layout.

    Dataset/Basic/<family>/<1..10>/GT_Files/...
    Dataset/Advanced/<case>/GT_Files/...

plus usr_requirement.txt next to GT_Files. Unlike the upstream read_json_*.py this
writes no LLM config and hardcodes no API key; use --original to unpack the
unmodified Kaggle files instead of v1.

    python Dataset/unpack_v1.py [--original] [--out Dataset]
"""
import argparse, json, os, stat

HERE = os.path.dirname(os.path.abspath(__file__))


def unpack(json_path, out_root, split):
    data = json.load(open(json_path, encoding="utf-8"))
    n_case = n_file = 0
    for key, files in data.items():
        parts = key.split("/")
        case_dir = os.path.join(out_root, split, *parts)
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
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", action="store_true", help="unpack the unmodified Kaggle JSONs instead of v1")
    ap.add_argument("--out", default=os.path.dirname(HERE), help="repo root (default: parent of Dataset/)")
    args = ap.parse_args()
    suffix = "" if args.original else "_v1"
    out_root = os.path.join(args.out, "Dataset")
    unpack(os.path.join(HERE, f"FoamBench_basic{suffix}.json"), out_root, "Basic")
    unpack(os.path.join(HERE, f"FoamBench_advanced{suffix}.json"), out_root, "Advanced")


if __name__ == "__main__":
    main()
