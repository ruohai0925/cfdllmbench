#!/bin/bash
# Clone Foam-Agent, the framework under test, into upstream/.
#   tools/fetch_upstream.sh
#
# That is the only thing this script downloads. It writes nothing outside upstream/ and
# never touches Dataset/. The two Kaggle JSONs are already tracked in upstream/, so
# nothing needs to be fetched for them -- the loop below only reports if one is missing,
# in which case it prints where to download it by hand.
set -e
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UP="$PKG/upstream"
KAGGLE="https://www.kaggle.com/datasets/nithinsekhar/foambench/data"
AGENT_URL="${FOAMAGENT_URL:-https://github.com/ruohai0925/Foam-Agent.git}"

mkdir -p "$UP"

for f in FoamBench_basic.json FoamBench_advanced.json; do
    if [ -f "$UP/$f" ]; then
        echo "have $f"
    else
        echo "MISSING $f -- it is normally tracked in upstream/. Download the FoamBench"
        echo "  folder from $KAGGLE"
        echo "  and place $f in $UP/"
    fi
done

if [ -d "$UP/Foam-Agent/.git" ]; then
    echo "have Foam-Agent ($(git -C "$UP/Foam-Agent" rev-parse --short HEAD))"
else
    git clone "$AGENT_URL" "$UP/Foam-Agent"
fi

# Foam-Agent's pre-built RAG database lives in git-LFS. Without git-lfs the checkout
# holds pointer files, and the index sizes give it away.
if command -v git-lfs >/dev/null 2>&1 || [ -x "$UP/Foam-Agent/env/bin/git-lfs" ]; then
    [ -x "$UP/Foam-Agent/env/bin/git-lfs" ] && export PATH="$UP/Foam-Agent/env/bin:$PATH"
    git -C "$UP/Foam-Agent" lfs install --local >/dev/null
    git -C "$UP/Foam-Agent" lfs pull
    echo "Foam-Agent database: $(du -sh "$UP/Foam-Agent/database/faiss" | cut -f1) in database/faiss"
else
    echo "git-lfs not found: Foam-Agent's database is still LFS pointers. Install git-lfs"
    echo "  (e.g. conda install -c conda-forge git-lfs) and run: git -C $UP/Foam-Agent lfs pull"
fi

echo
echo "Next: create Foam-Agent's environment (its pyproject deps suffice), then run one case."
echo "  conda create -p $UP/Foam-Agent/env python=3.12 pip git-lfs -c conda-forge"
echo "  $UP/Foam-Agent/env/bin/pip install -e \"$UP/Foam-Agent[all]\" sentence-transformers"
echo "  python $PKG/tools/run_benchmarks.py --only Basic/Cavity/1"
echo "upstream/ ready at $UP"
