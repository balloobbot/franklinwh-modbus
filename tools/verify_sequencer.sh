#!/bin/bash
# Sequencer Conformance Test Runner
# Verifies the sequencer engine logic and example schema validity.

set -e

echo "=== FranklinWH Sequencer Conformance Suite ==="

# 1. Run Unit Tests (Logic Verification)
echo "Running Engine Logic Tests..."
venv/bin/pytest tests/sequencer_conformance/test_sequencer_engine.py -v

# 2. Validate Example JSON Files (Schema Verification)
echo -e "\nValidating Example JSON Files..."
for f in examples/sequencer/*.json; do
    echo -n "  Checking $f... "
    # We use python to check if it's valid JSON
    python3 -c "import json; json.load(open('$f'))"
    echo "OK"
done

echo -e "\n✓ All sequencer conformance tests passed!"
