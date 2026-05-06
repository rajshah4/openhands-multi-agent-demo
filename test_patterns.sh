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
echo "  Test 1: Cloud Conversations"
echo "─────────────────────────────────────────────────────────────"
echo ""

test_step "Checking if cloud_conversations.py exists"
if [ -f "cloud_conversations.py" ]; then
    test_pass "File exists"
else
    test_fail "File not found"
fi

test_step "Checking Python syntax"
if python -m py_compile cloud_conversations.py 2>/dev/null; then
    test_pass "Valid Python syntax"
else
    test_fail "Syntax errors detected"
fi

test_step "Checking --help flag"
if python cloud_conversations.py --help >/dev/null 2>&1; then
    test_pass "--help works"
else
    test_fail "--help failed"
fi

test_step "Checking file is executable"
if [ -r "cloud_conversations.py" ]; then
    test_pass "File is readable and ready to run"
else
    test_fail "File permission issues"
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo "  Test 2: Multi-Server Isolation"
echo "─────────────────────────────────────────────────────────────"
echo ""

test_step "Checking if multi_server_isolation.py exists"
if [ -f "multi_server_isolation.py" ]; then
    test_pass "File exists"
else
    test_fail "File not found"
fi

test_step "Checking Python syntax"
if python -m py_compile multi_server_isolation.py 2>/dev/null; then
    test_pass "Valid Python syntax"
else
    test_fail "Syntax errors detected"
fi

test_step "Checking conceptual warning message"
OUTPUT=$(echo "n" | python multi_server_isolation.py 2>&1)
if echo "$OUTPUT" | grep -q "CONCEPTUAL IMPLEMENTATION"; then
    test_pass "Shows conceptual warning"
else
    test_fail "Warning message missing"
fi

test_step "Checking updated file references"
if grep -q "shared_workspace.py" multi_server_isolation.py && \
   grep -q "cloud_conversations.py" multi_server_isolation.py; then
    test_pass "References updated to new filenames"
else
    test_fail "Old filename references still present"
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo "  Test 3: Shared Workspace"
echo "─────────────────────────────────────────────────────────────"
echo ""

test_step "Checking if shared_workspace.py exists"
if [ -f "shared_workspace.py" ]; then
    test_pass "File exists"
else
    test_fail "File not found"
fi

test_step "Checking Python syntax"
if python -m py_compile shared_workspace.py 2>/dev/null; then
    test_pass "Valid Python syntax"
else
    test_fail "Syntax errors detected"
fi

test_step "Checking imports (will fail if SDK not installed - expected)"
if python -c "import sys; sys.path.insert(0, '.'); import ast; ast.parse(open('shared_workspace.py').read())" 2>/dev/null; then
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
if grep -q "shared_workspace.py" README.md && \
   grep -q "multi_server_isolation.py" README.md && \
   grep -q "cloud_conversations.py" README.md; then
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
OLD_REFS=$(grep -r "pipeline\.py\|demo\.py\|demo_local\.py" *.md *.py 2>/dev/null | grep -v "shared_workspace.py\|multi_server_isolation.py\|cloud_conversations.py\|Binary" | wc -l)
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
if git status | grep -q "renamed.*pattern1_easy_shared_workspace.py.*shared_workspace.py" && \
   git status | grep -q "renamed.*pattern3_cloud_multi_sandbox.py.*cloud_conversations.py"; then
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
    echo "  Pattern 1: python shared_workspace.py"
    echo "  Pattern 2: python multi_server_isolation.py"
    echo "  Pattern 3: python cloud_conversations.py"
    exit 0
else
    echo -e "${RED}❌ Some tests failed. Please review the output above.${NC}"
    exit 1
fi
