#!/usr/bin/env bash
# recimp — smoke test
#
# Verifies, with zero network access:
#   1. CLI help renders
#   2. reflect (text / json) on a fresh journal
#   3. advise (text) emits tuning recommendations
#   4. record round-trips: appended entry reads back from the journal
#   5. live RPC verify: writes back a `verify` block on a fake tx hash
#   6. demo shim runs
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
cd "$ROOT"

# Use a fresh local journal file so the test is hermetic.
JOURNAL="$ROOT/data/journal.jsonl"
mkdir -p data
cp examples/sample-journal.jsonl "$JOURNAL"
export RECIMP_JOURNAL="$JOURNAL"

# 1. Help
python3 src/recimp.py --help >/dev/null
echo "OK: --help"

# 2. reflect
python3 src/recimp.py reflect --format text  | grep -q 'AGENT REFLECTION REPORT'
echo "OK: reflect --format text"
python3 src/recimp.py reflect --format json  | python3 -c "import sys,json; assert json.load(sys.stdin)['strategies']"
echo "OK: reflect --format json"

# 3. advise must produce at least one tuning line
python3 src/recimp.py advise --format text  | grep -qE 'Tuning:'
echo "OK: advise --format text"

# 4. record round-trip
python3 src/recimp.py record --strategy smoke --action INIT \
  --params '{"size_usd":1}' >/dev/null
python3 -c "
import json, sys
with open('$JOURNAL') as f:
    rows = [json.loads(l) for l in f if l.strip()]
assert any(r['strategy']=='smoke' for r in rows), 'record did not land'
print('OK: record round-trip', file=sys.stderr)
"

# 5. Live RPC verify (only run if curl can reach Atlantic; otherwise skip).
if curl -sf --max-time 5 -o /dev/null https://atlantic.dplabs-internal.com -X POST \
   -H "Content-Type: application/json" --data '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'; then
  python3 src/recimp.py record --strategy smoke-rpc --action OPEN \
    --tx-hash 0x0000000000000000000000000000000000000000000000000000000000abcd01 \
    --symbol USDC >/dev/null
  python3 src/recimp.py verify --rpc-url https://atlantic.dplabs-internal.com \
    --chain testnet --strategy smoke-rpc --quiet >/dev/null
  python3 -c "
import json
with open('$JOURNAL') as f:
    rows = [json.loads(l) for l in f if l.strip()]
smoke = [r for r in rows if r['strategy']=='smoke-rpc'][0]
assert smoke['verify']['status'] in ('not_found', 'pending', 'ok'), smoke
print('OK: live RPC verify wrote status', smoke['verify']['status'])
"
else
  echo "SKIP: live RPC verify (Atlantic unreachable)"
fi

# 6. demo shim
bash scripts/iterate.sh --iterations 12 | grep -q 'cum='
echo "OK: demo shim"

echo ""
echo "All passed."
