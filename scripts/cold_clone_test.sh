#!/usr/bin/env bash
# T19 5-minute cold-clone gate: fresh clone → docker build → docker run → curl OK.
# Pass criterion: full wall-clock time ≤ 300s.

set -euo pipefail

REPO="${REPO:-https://github.com/Nafsgerman/siftguard.git}"
BUDGET_SECONDS=300
TMPDIR=$(mktemp -d -t siftguard-coldclone-XXXX)

cleanup() {
    docker rm -f siftguard-demo >/dev/null 2>&1 || true
    rm -rf "$TMPDIR"
}
trap cleanup EXIT

START=$(date +%s)

echo "[1/3] Clone..."
git clone --depth=1 "$REPO" "$TMPDIR/siftguard"
cd "$TMPDIR/siftguard"

echo "[2/3] Build + launch..."
make demo

echo "[3/3] Verify..."
curl -fsS http://localhost:8080/ >/dev/null

END=$(date +%s)
ELAPSED=$((END - START))
echo ""
echo "Cold-clone wall-clock: ${ELAPSED}s (budget: ${BUDGET_SECONDS}s)"

if [ "$ELAPSED" -gt "$BUDGET_SECONDS" ]; then
    echo "✗ FAIL: exceeded 5-minute budget"
    exit 1
fi
echo "✓ PASS"