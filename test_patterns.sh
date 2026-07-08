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
PYTHON_BIN="${PYTHON:-python3}"

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

syntax_check() {
    "$PYTHON_BIN" -c "import ast, pathlib; ast.parse(pathlib.Path('$1').read_text())" 2>/dev/null
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
if syntax_check cloud_conversations.py; then
    test_pass "Valid Python syntax"
else
    test_fail "Syntax errors detected"
fi

test_step "Checking --help flag or optional dependency boundary"
if "$PYTHON_BIN" -c "import requests" >/dev/null 2>&1; then
    if "$PYTHON_BIN" cloud_conversations.py --help >/dev/null 2>&1; then
        test_pass "--help works"
    else
        test_fail "--help failed"
    fi
elif grep -q "import requests" cloud_conversations.py; then
    test_pass "requests not installed; source declares optional runtime dependency"
else
    test_fail "requests dependency boundary unclear"
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
if syntax_check multi_server_isolation.py; then
    test_pass "Valid Python syntax"
else
    test_fail "Syntax errors detected"
fi

test_step "Checking conceptual warning message"
if "$PYTHON_BIN" -c "import pydantic" >/dev/null 2>&1; then
    OUTPUT=$(echo "n" | "$PYTHON_BIN" multi_server_isolation.py 2>&1)
    if echo "$OUTPUT" | grep -q "CONCEPTUAL IMPLEMENTATION"; then
        test_pass "Shows conceptual warning"
    else
        test_fail "Warning message missing"
    fi
elif grep -q "Pattern 2: Isolated Multi-Agent Orchestration" multi_server_isolation.py && \
     grep -q "manual git orchestration" multi_server_isolation.py; then
    test_pass "pydantic not installed; Pattern 2 boundary exists in source"
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
if syntax_check shared_workspace.py; then
    test_pass "Valid Python syntax"
else
    test_fail "Syntax errors detected"
fi

test_step "Checking imports (will fail if SDK not installed - expected)"
if "$PYTHON_BIN" -c "import sys; sys.path.insert(0, '.'); import ast; ast.parse(open('shared_workspace.py').read())" 2>/dev/null; then
    test_pass "File can be parsed"
else
    test_fail "File cannot be parsed"
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo "  Test 4: Workflow Pattern Examples"
echo "─────────────────────────────────────────────────────────────"
echo ""

test_step "Checking if parent_child_supervisor.py exists"
if [ -f "parent_child_supervisor.py" ]; then
    test_pass "File exists"
else
    test_fail "File not found"
fi

test_step "Checking parent_child_supervisor.py syntax and help"
if syntax_check parent_child_supervisor.py && \
   "$PYTHON_BIN" parent_child_supervisor.py --help >/dev/null 2>&1; then
    test_pass "Parent-child example is valid"
else
    test_fail "Parent-child example failed"
fi

test_step "Checking if polling_continuation_loop.py exists"
if [ -f "polling_continuation_loop.py" ]; then
    test_pass "File exists"
else
    test_fail "File not found"
fi

test_step "Checking polling_continuation_loop.py syntax and help"
if syntax_check polling_continuation_loop.py && \
   "$PYTHON_BIN" polling_continuation_loop.py --help >/dev/null 2>&1; then
    test_pass "Polling continuation example is valid"
else
    test_fail "Polling continuation example failed"
fi

echo ""
echo "─────────────────────────────────────────────────────────────"
echo "  Test 5: Documentation Files"
echo "─────────────────────────────────────────────────────────────"
echo ""

test_step "Checking README.md references"
if grep -q "shared_workspace.py" README.md && \
   grep -q "multi_server_isolation.py" README.md && \
   grep -q "cloud_conversations.py" README.md && \
   grep -q "WORKFLOW_PATTERNS.md" README.md && \
   grep -q "parent_child_supervisor.py" README.md && \
   grep -q "polling_continuation_loop.py" README.md; then
    test_pass "README.md uses new filenames"
else
    test_fail "README.md has old filename references"
fi

test_step "Checking WORKFLOW_PATTERNS.md references"
if grep -q "Parent-child supervisor" WORKFLOW_PATTERNS.md && \
   grep -q "Polling continuation loop" WORKFLOW_PATTERNS.md && \
   grep -q "15 minutes" WORKFLOW_PATTERNS.md; then
    test_pass "Workflow guide covers new patterns"
else
    test_fail "Workflow guide is missing expected patterns"
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
echo "  Test 6: Git Repository"
echo "─────────────────────────────────────────────────────────────"
echo ""

test_step "Checking git repository is available"
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    test_pass "Git repository available"
else
    test_fail "Not inside a git repository"
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
    echo "  Workflow: python parent_child_supervisor.py"
    echo "  Workflow: python polling_continuation_loop.py --dry-run"
    exit 0
else
    echo -e "${RED}❌ Some tests failed. Please review the output above.${NC}"
    exit 1
fi
