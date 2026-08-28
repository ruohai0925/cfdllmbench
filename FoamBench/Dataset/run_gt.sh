#!/bin/bash
# Run every unpacked GT case to completion under OpenFOAM 10.
#   Dataset/run_gt.sh [parallelism]     (default 12)
# Each case runs its own Allrun in Dataset/{Basic,Advanced}/**/GT_Files.
# Results (time directories + log.*) stay in place for the NMSE step.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
JOBS="${1:-12}"
SUMMARY="$ROOT/Dataset/gt_run_summary.tsv"

# NB: OpenFOAM's bashrc references unset variables -- never run it under `set -u`.
FOAM_BASHRC="${FOAM_BASHRC:-/opt/openfoam10/etc/bashrc}"
if [ ! -f "$FOAM_BASHRC" ]; then echo "OpenFOAM bashrc not found: $FOAM_BASHRC" >&2; exit 1; fi
. "$FOAM_BASHRC"
export WM_PROJECT_DIR="${WM_PROJECT_DIR:-/opt/openfoam10}"
command -v blockMesh >/dev/null || { echo "blockMesh not on PATH after sourcing $FOAM_BASHRC" >&2; exit 1; }
echo "OpenFOAM $WM_PROJECT_VERSION at $WM_PROJECT_DIR"

# OpenFOAM's runApplication REFUSES to re-run when log.<app> exists ("already run ...
# remove log file to re-run") and returns success, so a stale case silently produces a
# no-op that still looks like a pass. Always clean before running.
clean_case() {
    local d="$1"
    ( cd "$d" && rm -rf processor* constant/polyMesh postProcessing VTK \
        && rm -f log.* *.foam \
        && for t in [0-9]*; do [ "$t" != "0" ] && [ -d "$t" ] && rm -rf "$t"; done ) 2>/dev/null
    return 0
}

run_one() {
    local d="$1" t0 rc app last
    clean_case "$d"
    t0=$(date +%s)
    ( cd "$d" && ./Allrun ) >"$d/log.Allrun" 2>&1
    rc=$?
    local elapsed=$(( $(date +%s) - t0 ))
    app=$(ls "$d"/log.*Foam 2>/dev/null | head -1)
    local status="NO_SOLVER_LOG"
    if [ -n "$app" ]; then
        if tail -5 "$app" | grep -q '^End'; then status="OK"; else status="INCOMPLETE"; fi
        grep -q "FOAM FATAL" "$app" && status="FATAL"
    fi
    grep -qs "FOAM FATAL" "$d"/log.* && status="${status}+FATAL_IN_STEP"
    last=$(ls -d "$d"/[0-9]* 2>/dev/null | xargs -r -n1 basename | grep -E '^[0-9.eE+-]+$' | sort -g | tail -1)
    printf '%s\t%s\t%s\t%s\t%s\n' "${d#$ROOT/Dataset/}" "$status" "$elapsed" "${last:-none}" "$(basename "${app:-none}")" >>"$SUMMARY"
    echo "[$status ${elapsed}s] ${d#$ROOT/Dataset/}"
}
export -f run_one clean_case
export ROOT SUMMARY

: >"$SUMMARY"
printf 'case\tstatus\tseconds\tlast_time\tsolver_log\n' >>"$SUMMARY"

mapfile -t CASES < <(find "$ROOT/Dataset/Basic" "$ROOT/Dataset/Advanced" -name Allrun -printf '%h\n' | sort)
echo "Running ${#CASES[@]} cases with $JOBS parallel jobs, no time limit (each case cleaned first)."
printf '%s\n' "${CASES[@]}" | xargs -P "$JOBS" -I{} bash -c 'run_one "$@"' _ {}

echo
echo "=== summary ==="
awk -F'\t' 'NR>1{c[$2]++} END{for(k in c) printf "%-28s %d\n", k, c[k]}' "$SUMMARY"
