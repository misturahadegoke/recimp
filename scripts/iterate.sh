#!/usr/bin/env bash
# recimp-iterate — Demo shim for Anvita Flow / Pharos Skill Engine.
#
# The actual skill lives in src/recimp.py (Python, stdlib only). This script
# just prints a synthetic reward curve so a hosted runtime that wants to
# "execute something" without a populated journal still has something to show.
#
# Usage: bash scripts/iterate.sh [--iterations N]

set -euo pipefail

ITERATIONS="${1:-}"

case "$ITERATIONS" in
  --iterations) ITERATIONS="${2:-100}" ;;
  --iterations=*) ITERATIONS="${ITERATIONS#--iterations=}" ;;
  "") ITERATIONS=100 ;;
  --help|-h)
    cat <<USAGE
recimp-iterate — demo shim

Usage:
  bash scripts/iterate.sh                    # 100 iterations
  bash scripts/iterate.sh --iterations 50    # N iterations

The real skill is \`python3 src/recimp.py\`. This shim exists so a hosted
runtime that hasn't been given real journal data can still produce output.
USAGE
    exit 0
    ;;
esac

echo ""
echo "========================================================================"
echo "  RECIMP — Recursive Self-Improvement (DEMO)"
echo "  Iterations: $ITERATIONS  (synthetic — no journal data loaded)"
echo "========================================================================"
echo ""

# Print first 5 and last 5 with dots in between, similar to the older iterate.sh
print_iter() {
  local i="$1" reward_int="$2" cum="$3"
  local whole=$(( reward_int / 100 ))
  local frac=$(( reward_int % 100 ))
  [ $frac -lt 10 ] && frac="0$frac"
  printf "  Iteration %5d/%-5d  reward=0.%s%s  cum=%d\n" "$i" "$ITERATIONS" "$whole" "$frac" "$cum"
}

# Deterministic synthetic curve
CUM=0
for i in $(seq 1 "$ITERATIONS"); do
  REWARD_INT=$(( (i * 7 + 35) % 30 + 40 ))   # 40..69
  CUM=$(( CUM + REWARD_INT ))
  if [ "$ITERATIONS" -le 12 ]; then
    print_iter "$i" "$REWARD_INT" "$CUM"
  elif [ "$i" -le 5 ] || [ "$i" -ge $(( ITERATIONS - 4 )) ]; then
    print_iter "$i" "$REWARD_INT" "$CUM"
    if [ "$i" = "5" ]; then
      echo "  ..."
    fi
  fi
done

echo ""
echo "  Synthetic gain vs baseline:    +18.3% over $ITERATIONS iterations"
echo "  Use 'python3 src/recimp.py reflect --format text' on a real journal"
echo "  for an actual per-strategy report."
echo ""
