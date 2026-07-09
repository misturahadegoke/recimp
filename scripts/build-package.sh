#!/usr/bin/env bash
# Build recimp.zip for Anvita Flow / Pharos Agent Center upload.
#
# The zip must contain the skill folder at its top level (not the
# files inside it) and `SKILL.md` must be uppercase at the root.
#
# Usage:
#   bash scripts/build-package.sh
#   bash scripts/build-package.sh /path/to/output.zip

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
FOLDER="$(basename "$ROOT")"

OUT="${1:-$ROOT/recimp.zip}"

cd "$ROOT/.."
# zip the folder, not its contents
rm -f "$OUT"
zip -r "$OUT" "$FOLDER" \
  -x "$FOLDER/data/*" \
     "$FOLDER/.git/*" \
     "$FOLDER/.venv/*" \
     "$FOLDER/__pycache__/*" \
     "$FOLDER/**/*.pyc"

echo ""
echo "Built: $OUT"
echo "Top level: $FOLDER/"
echo ""
unzip -l "$OUT" | head -25
