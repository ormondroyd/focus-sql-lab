#!/usr/bin/env bash
# Rebuild everything the site derives from FOCUS_Spec, from the commit checked out in <FOCUS_Spec clone>, then list
# the AI summaries that are now due (a dry run: nothing here calls the Claude API).
#
#   GH_TOKEN=<GitHub token> tools/refresh.sh <FOCUS_Spec clone> <raw data folder> [history cache]
#
# The clone needs full history (for git log and git blame). If it doesn't have it, set HISTORY to one that does,
# such as a bare clone. PYTHON picks the interpreter (default: python). The GitHub workflow
# .github/workflows/refresh.yml runs this when someone starts it by hand.
set -euo pipefail
SPEC=$1 RAW=$2 CACHE=${3:-}
HISTORY=${HISTORY:-$SPEC}
PY=${PYTHON:-python}
cd "$(dirname "$0")/.."
COMMIT=$(git -C "$SPEC" rev-parse --short=7 HEAD)
echo "Refreshing from FOCUS_Spec $COMMIT"

$PY -I tools/build_data.py "$SPEC" "$RAW" site/focus/data
$PY -I tools/extract_model.py "$SPEC" site          # before extract_sql and extract_history, which read model.json
$PY -I tools/extract_sql.py "$SPEC" site
$PY -I tools/extract_history.py "$HISTORY" "$COMMIT" site ${CACHE:+"$CACHE"}
$PY -I tools/extract_ai.py "$SPEC" site             # reads model.json and spec-queries.json
$PY -I tools/summarise.py "$SPEC" site --stamp --data
$PY -I tools/summarise.py "$SPEC" site              # dry run: what's due, and an estimated cost
