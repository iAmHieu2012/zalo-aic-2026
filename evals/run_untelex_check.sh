#!/usr/bin/env bash
# Telex rewrite on/off over the train questions it changes (one GPU session, ~15 min).
#   bash evals/run_untelex_check.sh
set -uo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH=src LLM_PARSE_MODEL=
for flag in false true; do
  echo "=== UNTELEX=${flag}"
  UNTELEX=${flag} .venv/bin/python -m evals.run_eval --system pipeline_llm --subset telex \
    --workers "${WORKERS:-8}" 2>&1 | grep -E "^N=|Run saved"
done
