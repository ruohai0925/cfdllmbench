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

echo
echo "Next: create Foam-Agent's conda environment, then build its RAG database once."
echo "  conda env create -f $UP/Foam-Agent/environment.yml"
echo "  python $PKG/tools/run_benchmarks.py --only Basic/Cavity/1"
echo "upstream/ ready at $UP"
