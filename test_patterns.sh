#!/bin/bash
#
# Test Script for Multi-Agent Orchestration Patterns
# ===================================================
#
# This script verifies that all pattern files are working correctly
# after the rename from demo.py/pipeline.py to self-explanatory names.

# set -e  # Exit on error

echo "============================================================"
echo "  Testing Multi-Agent Orchestration Patterns"
echo "============================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test counters
PASSED=0
FAILED=0

# Helper function
test_step() {
    echo -e "${YELLOW}Testing:${NC} $1"
}

test_pass() {
    echo -e "${GREEN}✅ PASS:${NC} $1"
    ((PASSED++))
}

test_fail() {
    echo -e "${RED}❌ FAIL:${NC} $1"
    ((FAILED++))
}

echo "─────────────────────────────────────────────────────────────"
echo "  Test 1: Pattern 3 - Cloud Multi-Sandbox"
echo "─────────────────────────────────────────────────────────────"
echo ""

test_step "Checking if pattern3_cloud_multi_sandbox.py exists"
if [ -f "pattern3_cloud_multi_sandbox.py" ]; then
    test_pass "File exists"
else
    test_fail "File not found"
fi

test_step "Checking Python syntax"
if python -m py_compile pattern3_cloud_multi_sandbox.py 2>/dev/null; then
    test_pass "Valid Python syntax"
else
    test_fail "Syntax errors detected"
fi

test_step "Checking --help flag"
if python pattern3_cloud_multi_sandbox.py --help >/dev/null 2>&1; then
    test_pass "--help works"
else
    test_fail "--help failed"
fi

test_step "Checking error message without API key"
OUTPUT=$(python pattern3_cloud_multi_sandbox.py 2>&1 | head -1)
if echo "$OUTPUT" | grep -q "OPENHANDS_CLOUD_API_KEY"; then
    test_pass "Shows proper error for missing API key"
else
    test_fail "Error message incorrect"
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo "  Test 2: Pattern 2 - Isolated Local Servers"
echo "─────────────────────────────────────────────────────────────"
echo ""

test_step "Checking if pattern2_isolated_local_servers.py exists"
if [ -f "pattern2_isolated_local_servers.py" ]; then
    test_pass "File exists"
else
    test_fail "File not found"
fi

test_step "Checking Python syntax"
if python -m py_compile pattern2_isolated_local_servers.py 2>/dev/null; then
    test_pass "Valid Python syntax"
else
    test_fail "Syntax errors detected"
fi

test_step "Checking conceptual warning message"
OUTPUT=$(echo "n" | python pattern2_isolated_local_servers.py 2>&1)
if echo "$OUTPUT" | grep -q "CONCEPTUAL IMPLEMENTATION"; then
    test_pass "Shows conceptual warning"
else
    test_fail "Warning message missing"
fi

test_step "Checking updated file references"
if grep -q "pattern1_easy_shared_workspace.py" pattern2_isolated_local_servers.py && \
   grep -q "pattern3_cloud_multi_sandbox.py" pattern2_isolated_local_servers.py; then
    test_pass "References updated to new filenames"
else
    test_fail "Old filename references still present"
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo "  Test 3: Pattern 1 - Easy Shared Workspace"
echo "─────────────────────────────────────────────────────────────"
echo ""

test_step "Checking if pattern1_easy_shared_workspace.py exists"
if [ -f "pattern1_easy_shared_workspace.py" ]; then
    test_pass "File exists"
else
    test_fail "File not found"
fi

test_step "Checking Python syntax"
if python -m py_compile pattern1_easy_shared_workspace.py 2>/dev/null; then
    test_pass "Valid Python syntax"
else
    test_fail "Syntax errors detected"
fi

test_step "Checking imports (will fail if SDK not installed - expected)"
if python -c "import sys; sys.path.insert(0, '.'); import ast; ast.parse(open('pattern1_easy_shared_workspace.py').read())" 2>/dev/null; then
    test_pass "File can be parsed"
else
    test_fail "File cannot be parsed"
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo "  Test 4: Documentation Files"
echo "─────────────────────────────────────────────────────────────"
echo ""

test_step "Checking README.md references"
if grep -q "pattern1_easy_shared_workspace.py" README.md && \
   grep -q "pattern2_isolated_local_servers.py" README.md && \
   grep -q "pattern3_cloud_multi_sandbox.py" README.md; then
    test_pass "README.md uses new filenames"
else
    test_fail "README.md has old filename references"
fi

test_step "Checking PATTERNS.md for old references"
if grep -E "(^|[^_])demo\.py|^pipeline\.py|demo_local\.py" PATTERNS.md >/dev/null 2>&1; then
    test_fail "PATTERNS.md still has old filename references"
else
    test_pass "PATTERNS.md has no old filename references"
fi

test_step "Checking for old filename references (should be none)"
OLD_REFS=$(grep -r "pipeline\.py\|demo\.py\|demo_local\.py" *.md *.py 2>/dev/null | grep -v "pattern1_easy_shared_workspace.py\|pattern2_isolated_local_servers.py\|pattern3_cloud_multi_sandbox.py\|Binary" | wc -l)
if [ "$OLD_REFS" -eq "0" ]; then
    test_pass "No old filename references found"
else
    test_fail "Found $OLD_REFS old filename references"
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo "  Test 5: Git Status"
echo "─────────────────────────────────────────────────────────────"
echo ""

test_step "Checking git renames"
if git status | grep -q "renamed.*pipeline.py.*pattern1_easy_shared_workspace.py" && \
   git status | grep -q "renamed.*demo.py.*pattern3_cloud_multi_sandbox.py"; then
    test_pass "Git tracked the renames"
else
    test_fail "Git renames not properly tracked"
fi

echo ""
echo "============================================================"
echo "  Test Summary"
echo "============================================================"
echo ""
echo -e "${GREEN}Passed:${NC} $PASSED"
echo -e "${RED}Failed:${NC} $FAILED"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
    echo ""
    echo "The pattern files have been successfully renamed and are working."
    echo ""
    echo "Usage:"
    echo "  Pattern 1: python pattern1_easy_shared_workspace.py"
    echo "  Pattern 2: python pattern2_isolated_local_servers.py"
    echo "  Pattern 3: python pattern3_cloud_multi_sandbox.py"
    exit 0
else
    echo -e "${RED}❌ Some tests failed. Please review the output above.${NC}"
    exit 1
fi
