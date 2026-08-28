#!/bin/bash
# Fetch everything foambench_v1 needs from outside itself, into upstream/.
#   tools/fetch_upstream.sh
#
# Two things live outside this package:
#   1. the unmodified Kaggle JSONs -- only needed to re-derive the corrected v1 data
#      with tools/patch_dataset.py; the v1 JSONs themselves are already in Dataset/
#   2. MetaOpenFOAM, the framework under test (it has its own git repo)
set -e
PKG="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UP="$PKG/upstream"
KAGGLE="https://www.kaggle.com/datasets/nithinsekhar/foambench/data"
META_URL="https://github.com/Terry-cyx/MetaOpenFOAM.git"
# Last commit before the project was deprecated and moved to svd-ai-lab/sim-cli.
META_COMMIT="85aae62"

mkdir -p "$UP"

for f in FoamBench_basic.json FoamBench_advanced.json; do
    if [ -f "$UP/$f" ]; then
        echo "have $f"
    elif [ -f "$PKG/../Dataset/$f" ]; then
        cp "$PKG/../Dataset/$f" "$UP/$f"; echo "copied $f from the sibling upstream checkout"
    else
        echo "MISSING $f -- download the FoamBench folder from"
        echo "  $KAGGLE"
        echo "and place $f in $UP/"
    fi
done

if [ -d "$UP/MetaOpenFOAM/.git" ]; then
    echo "have MetaOpenFOAM ($(git -C "$UP/MetaOpenFOAM" rev-parse --short HEAD))"
else
    git clone "$META_URL" "$UP/MetaOpenFOAM"
    git -C "$UP/MetaOpenFOAM" checkout -b pre-deprecate "$META_COMMIT"
fi
echo "upstream/ ready at $UP"
