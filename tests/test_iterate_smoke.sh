#!/bin/bash
set -e
SCRIPT="scripts/iterate.sh"
bash "$SCRIPT" --help >/dev/null
if bash "$SCRIPT --demo" | grep -q "CUM"; then
  echo "OK: demo"
else
  echo "FAIL"; exit 1
fi
echo "All passed."
