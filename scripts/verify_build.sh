#!/bin/bash
set -e

echo "========================================"
echo "   RONGLE GOLDEN MASTER BUILD VERIFIER  "
echo "========================================"

# 1. Clean Environment
echo "[1/5] Cleaning build artifacts..."
rm -rf dist build coverage
find . -name "__pycache__" -type d -exec rm -rf {} +

# 2. Frontend Build
echo "[2/5] Building Frontend..."
npm install --silent
npm run build
if [ -f "dist/index.html" ]; then
    echo "✅ Frontend Build Success"
else
    echo "❌ Frontend Build Failed"
    exit 1
fi

# 3. Test Suites
echo "[3/5] Running Tests..."
echo "--> Frontend Unit Tests"
npm run test
echo "✅ Frontend Tests Passed"

echo "--> Backend Unit Tests"
export PYTHONPATH=$PYTHONPATH:.
pytest rongle_operator/tests
echo "✅ Backend Tests Passed"

# 4. Operator Dry Run (Integration Check)
echo "[4/5] Verifying Operator Startup..."
# We run with --dry-run and a timeout to ensure it boots but doesn't hang forever
timeout 5s python3 -m rongle_operator.main --dry-run --goal "Build Verification" > operator_boot.log 2>&1 || true

if grep -q "Environment check passed" operator_boot.log || grep -q "Dry-run mode" operator_boot.log; then
    echo "✅ Operator Booted Successfully (Dry Run)"
else
    echo "❌ Operator Boot Failed"
    cat operator_boot.log
    exit 1
fi

# 5. Documentation Check
echo "[5/5] Verifying Documentation..."
REQUIRED_DOCS=("README.md" "SUMMARY.md" "docs/AGENTS.md" "docs/OPERATIONAL_METRICS.md")
for doc in "${REQUIRED_DOCS[@]}"; do
    if [ -f "$doc" ]; then
        echo "✅ Found $doc"
    else
        echo "❌ Missing $doc"
        exit 1
    fi
done

echo "========================================"
echo "   BUILD VERIFIED - READY FOR RELEASE   "
echo "========================================"
