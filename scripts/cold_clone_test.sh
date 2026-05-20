#!/usr/bin/env bash
# cold_clone_test.sh — validates judge can clone + run make demo in ≤ 5 min
set -euo pipefail

BUDGET_SECONDS=300
REPO_URL="${1:-https://github.com/Nafsgerman/siftguard.git}"
TMPDIR="$(mktemp -d)"
PORT=8080

cleanup() {
    echo "→ Cleaning up temp clone…"
    cd /tmp
    make -C "$TMPDIR" demo-stop 2>/dev/null || true
    rm -rf "$TMPDIR"
}
trap cleanup EXIT

START=$(date +%s)

echo "=== SIFTGuard Cold-Clone Gate ==="
echo "→ Cloning $REPO_URL into $TMPDIR"
git clone --depth 1 "$REPO_URL" "$TMPDIR"

echo "→ Running make demo (budget: ${BUDGET_SECONDS}s)"
cd "$TMPDIR"
make demo

echo "→ Verifying dashboard responds…"
curl -sf "http://localhost:${PORT}/" >/dev/null \
    && echo "✓  Dashboard OK at http://localhost:${PORT}/"

ELAPSED=$(( $(date +%s) - START ))
echo "→ Wall-clock: ${ELAPSED}s / ${BUDGET_SECONDS}s"

if [ "$ELAPSED" -gt "$BUDGET_SECONDS" ]; then
    echo "✗  FAILED: exceeded ${BUDGET_SECONDS}s budget" >&2
    exit 1
fi

echo "✓  PASSED cold-clone gate in ${ELAPSED}s"
