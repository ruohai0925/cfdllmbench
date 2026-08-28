"""Unpack the FoamBench dataset JSONs into the directory layout the harness expects.

    Dataset/Basic/<family>/<1..10>/GT_Files/...      + usr_requirement.txt + <family>.yaml
    Dataset/Advanced/<case>/GT_Files/...             + usr_requirement.txt + <case>.yaml

The per-case YAML is the input format MetaOpenFOAM reads: run_benchmarks.py points
CONFIG_FILE_PATH at it, and algorithm/MetaOpenFOAM/src/config_path.py takes the prompt
from its `usr_requirment` key (note the upstream spelling, no 'e') plus the LLM settings.

Unlike the upstream read_json_*.py this hardcodes no API key -- the key comes from
--api-key or $FOAMBENCH_OPENAI_API_KEY -- and an existing YAML is left alone unless
--force-yaml is given, so a hand-edited config survives a re-unpack.

    python Dataset/unpack_v1.py [--original] [--no-yaml] [--force-yaml]
                                [--api-key K] [--model gpt-4o] [--metagpt-path P] ...
"""
import argparse, json, os, stat

HERE = os.path.dirname(os.path.abspath(__file__))
PKG = os.path.dirname(HERE)                                  # foambench_v1/
DATASET = os.path.join(PKG, "Dataset")                       # our corrected data
# --original reads the unmodified Kaggle JSONs, the one input outside this package.
UPSTREAM = os.environ.get("FOAMBENCH_UPSTREAM") or os.path.join(PKG, "upstream")


def yaml_quote(s):
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


def write_yaml(path, requirement, cfg, force):
    if os.path.exists(path) and not force:
        return False
    with open(path, "w", encoding="utf-8") as f:
        # `usr_requirment` is the upstream key spelling; config_path.py reads exactly this.
        f.write("usr_requirment: %s\n" % yaml_quote(requirement))
        f.write("max_loop: %d\n" % cfg["max_loop"])
        f.write("temperature: %s\n" % cfg["temperature"])
        f.write("batchsize: %d\n" % cfg["batchsize"])
        f.write("searchdocs: %d\n" % cfg["searchdocs"])
        f.write("run_times: %d\n\n" % cfg["run_times"])
        f.write("MetaGPT_PATH: %s\n" % yaml_quote(cfg["metagpt_path"]))
        f.write("model: %s\n" % yaml_quote(cfg["model"]))
        f.write("OPENAI_API_KEY: %s\n" % yaml_quote(cfg["api_key"]))
        f.write("OPENAI_BASE_URL: %s\n" % yaml_quote(cfg["base_url"]))
        f.write("OPENAI_PROXY: %s\n" % yaml_quote(cfg["proxy"]))
    return True


def unpack(json_path, out_root, split, cfg):
    data = json.load(open(json_path, encoding="utf-8"))
    n_case = n_file = n_yaml = 0
    for key, files in data.items():
        parts = key.split("/")
        case_dir = os.path.join(out_root, split, *parts)
        gt_dir = os.path.join(case_dir, "GT_Files")
        os.makedirs(gt_dir, exist_ok=True)
        for rel, content in files.items():
            if rel == "usr_requirement":
                with open(os.path.join(case_dir, "usr_requirement.txt"), "w", encoding="utf-8") as f:
                    f.write(content)
                if cfg["yaml"]:
                    # run_benchmarks.py looks for <family>.yaml in Basic/<family>/<i>/ and
                    # <case>.yaml in Advanced/<case>/ -- i.e. always named after parts[0].
                    if write_yaml(os.path.join(case_dir, parts[0] + ".yaml"), content, cfg, cfg["force_yaml"]):
                        n_yaml += 1
                continue
            path = os.path.join(gt_dir, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            if os.path.basename(path).startswith("All"):
                os.chmod(path, os.stat(path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            n_file += 1
        n_case += 1
    extra = ", %d yaml" % n_yaml if cfg["yaml"] else ""
    print(f"{split}: {n_case} cases, {n_file} GT files{extra} -> {os.path.join(out_root, split)}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--original", action="store_true", help="unpack the unmodified Kaggle JSONs instead of v1")
    ap.add_argument("--upstream", default=UPSTREAM, help="where the unmodified Kaggle JSONs live (only used with --original)")
    ap.add_argument("--out", default=DATASET, help="where to unpack (default: foambench_v1/Dataset)")
    ap.add_argument("--no-yaml", dest="yaml", action="store_false", help="do not emit the MetaOpenFOAM case YAML")
    ap.add_argument("--force-yaml", action="store_true", help="overwrite an existing case YAML")
    ap.add_argument("--api-key", default=os.environ.get("FOAMBENCH_OPENAI_API_KEY", ""))
    ap.add_argument("--base-url", default="https://api.openai.com/v1")
    ap.add_argument("--proxy", default="")
    ap.add_argument("--model", default="gpt-4o")
    ap.add_argument("--metagpt-path", default=os.environ.get("METAGPT_PATH", ""))
    ap.add_argument("--max-loop", type=int, default=10)
    ap.add_argument("--batchsize", type=int, default=10)
    ap.add_argument("--searchdocs", type=int, default=2)
    ap.add_argument("--run-times", type=int, default=1)
    ap.add_argument("--temperature", default="0.0")
    args = ap.parse_args()

    cfg = {"yaml": args.yaml, "force_yaml": args.force_yaml, "api_key": args.api_key,
           "base_url": args.base_url, "proxy": args.proxy, "model": args.model,
           "metagpt_path": args.metagpt_path, "max_loop": args.max_loop,
           "batchsize": args.batchsize, "searchdocs": args.searchdocs,
           "run_times": args.run_times, "temperature": args.temperature}
    if args.yaml and not args.api_key:
        print("note: no API key given (--api-key / $FOAMBENCH_OPENAI_API_KEY); "
              "the YAML gets an empty OPENAI_API_KEY and MetaOpenFOAM will not authenticate.")

    suffix = "" if args.original else "_v1"
    src_dir = args.upstream if args.original else DATASET
    out_root = args.out
    unpack(os.path.join(src_dir, f"FoamBench_basic{suffix}.json"), out_root, "Basic", cfg)
    unpack(os.path.join(src_dir, f"FoamBench_advanced{suffix}.json"), out_root, "Advanced", cfg)


if __name__ == "__main__":
    main()
