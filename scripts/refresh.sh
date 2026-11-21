#!/bin/bash
# Refresh the dashboard data: re-fetch every Routed event from the chain,
# rebuild the aggregates, and print the reconciliation vs Stoa's own stats.
# Free: only reads public RPC + public Stoa API. No keys, no signing, no swaps.
set -e
cd "$(dirname "$0")/.."
python3 scripts/fetch-routed.py
python3 scripts/build-data.py
echo "Done. Open index.html (or serve this dir) to view the dashboard."
