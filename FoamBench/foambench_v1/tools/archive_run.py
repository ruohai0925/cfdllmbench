"""Park one framework run so another can be scored, and put it back afterwards.

    python tools/archive_run.py --list
    python tools/archive_run.py --archive gpt-5.6-sol     # Dataset/ -> results/runs/<tag>/
    python tools/archive_run.py --restore gpt-5.6-sol     # and back

The three scoring scripts take "the first sub-directory that is not GT_Files" as the
submission, so a case directory can hold exactly one run at a time. Comparing two models
therefore means moving the finished run out of Dataset/ rather than leaving it beside the
new one. The move is a rename within the same filesystem, so it costs nothing and the run
is never copied or rewritten.

Archived along with the submissions: the run summary and the score tables that describe
them, so results/runs/<tag>/ is a complete, self-contained record of that experiment.
"""
import argparse
import os
import shutil
import sys

PKG = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATASET = os.path.join(PKG, "Dataset")
RESULTS = os.path.join(PKG, "results")
ARCHIVE = os.path.join(RESULTS, "runs")
SUBMISSION = "foam_agent_run"
# Everything the report scripts write into results/ belongs to whichever run is currently
# unpacked, and moves with it into results/<tag>/. Only the ground-truth summary, which
# describes the dataset rather than a run, stays behind.
KEEP_IN_PLACE = {"gt_run_summary.tsv"}


def case_dirs():
    """[(label, case_dir), ...] for every unpacked case, in scoring order."""
    out = []
    basic = os.path.join(DATASET, "Basic")
    if os.path.isdir(basic):
        for family in sorted(os.listdir(basic)):
            for i in range(1, 11):
                d = os.path.join(basic, family, str(i))
                if os.path.isdir(d):
                    out.append((f"Basic/{family}/{i}", d))
    adv = os.path.join(DATASET, "Advanced")
    if os.path.isdir(adv):
        for case in sorted(os.listdir(adv)):
            d = os.path.join(adv, case)
            if os.path.isdir(d):
                out.append((f"Advanced/{case}", d))
    return out


def archive(tag):
    dest_root = os.path.join(ARCHIVE, tag)
    moved = 0
    for label, case_dir in case_dirs():
        src = os.path.join(case_dir, SUBMISSION)
        if not os.path.isdir(src):
            continue
        dest = os.path.join(dest_root, label, SUBMISSION)
        if os.path.exists(dest):
            sys.exit(f"refusing to overwrite {dest}\n"
                     f"pick another tag, or move that directory away first")
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.move(src, dest)
        moved += 1
    # The tables stay inside results/ (small, tracked); only the submissions, which are
    # tens of gigabytes, go under results/runs/, which git ignores.
    tables = os.path.join(RESULTS, tag)
    kept = []
    for name in sorted(os.listdir(RESULTS)):
        src = os.path.join(RESULTS, name)
        if not os.path.isfile(src) or name in KEEP_IN_PLACE:
            continue
        os.makedirs(tables, exist_ok=True)
        shutil.move(src, os.path.join(tables, name))
        kept.append(name)
    print(f"archived {moved} submission(s) to {dest_root}")
    if kept:
        print(f"  and {len(kept)} table(s) to {tables}: {', '.join(kept)}")
    if not moved and not kept:
        print("  nothing to archive -- no submission directories found")


def restore(tag):
    src_root = os.path.join(ARCHIVE, tag)
    if not os.path.isdir(src_root):
        sys.exit(f"no archived run at {src_root}; --list shows what is there")
    moved = 0
    for label, case_dir in case_dirs():
        src = os.path.join(src_root, label, SUBMISSION)
        if not os.path.isdir(src):
            continue
        dest = os.path.join(case_dir, SUBMISSION)
        if os.path.exists(dest):
            sys.exit(f"{dest} already holds a run; archive it first "
                     f"(python tools/archive_run.py --archive <other-tag>)")
        shutil.move(src, dest)
        moved += 1
    res = os.path.join(RESULTS, tag)
    back = []
    if os.path.isdir(res):
        for name in sorted(os.listdir(res)):
            dest = os.path.join(RESULTS, name)
            if os.path.exists(dest):
                print(f"  leaving {name} in the archive: {dest} exists")
                continue
            shutil.move(os.path.join(res, name), dest)
            back.append(name)
        if not os.listdir(res):
            os.rmdir(res)
    print(f"restored {moved} submission(s) from {src_root}")
    if back:
        print(f"  with {', '.join(back)}")


def list_runs():
    live = sum(1 for _, d in case_dirs() if os.path.isdir(os.path.join(d, SUBMISSION)))
    print(f"in Dataset/ (scored by the report scripts): {live} submission(s)")
    if not os.path.isdir(ARCHIVE):
        return
    for tag in sorted(os.listdir(ARCHIVE)):
        root = os.path.join(ARCHIVE, tag)
        if not os.path.isdir(root):
            continue
        n = sum(1 for label, _ in case_dirs()
                if os.path.isdir(os.path.join(root, label, SUBMISSION)))
        extra = "" if n else "  (not a case archive)"
        print(f"  results/runs/{tag}: {n} submission(s){extra}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--archive", metavar="TAG", help="move the current run out of Dataset/")
    g.add_argument("--restore", metavar="TAG", help="move an archived run back into Dataset/")
    g.add_argument("--list", action="store_true", help="what is where")
    args = ap.parse_args()
    if args.list:
        list_runs()
    elif args.archive:
        archive(args.archive)
    else:
        restore(args.restore)


if __name__ == "__main__":
    main()
