#!/bin/bash
# Clone MetaOpenFOAM, the framework under test, into upstream/.
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
