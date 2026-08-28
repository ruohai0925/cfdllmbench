#!/bin/bash
# Fetch everything foambench_v1 needs from outside itself, into upstream/.
#   tools/fetch_upstream.sh
#
# In practice that is just MetaOpenFOAM, the framework under test: it has its own git
# repo, so it is not tracked here. The unmodified Kaggle JSONs are tracked in upstream/
# already (patch_dataset.py needs them to re-derive the v1 data); this script only
# reports if they are missing.
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
    else
        echo "MISSING $f -- it is normally tracked in upstream/. Download the FoamBench"
        echo "  folder from $KAGGLE"
        echo "  and place $f in $UP/"
    fi
done

if [ -d "$UP/MetaOpenFOAM/.git" ]; then
    echo "have MetaOpenFOAM ($(git -C "$UP/MetaOpenFOAM" rev-parse --short HEAD))"
else
    git clone "$META_URL" "$UP/MetaOpenFOAM"
    git -C "$UP/MetaOpenFOAM" checkout -b pre-deprecate "$META_COMMIT"
fi
echo "upstream/ ready at $UP"
