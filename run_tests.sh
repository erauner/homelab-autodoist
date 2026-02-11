#!/bin/bash
# Run Autodoist tests
#
# Usage:
#   ./run_tests.sh                    # Run all tests (requires TODOIST_API_TOKEN)
#   TODOIST_API_TOKEN=xxx ./run_tests.sh  # Run with token
#   ./run_tests.sh -k "test_sdk"      # Run only SDK tests

set -e

# Check for token
if [ -z "$TODOIST_API_TOKEN" ]; then
    echo "WARNING: TODOIST_API_TOKEN not set, API tests will be skipped"
    echo "Set it with: export TODOIST_API_TOKEN=your_token"
    echo ""
fi

# Install dependencies if needed
pip install -q requests todoist_api_python pytest

# Run tests
cd "$(dirname "$0")"
python -m pytest tests/ -v "$@"
