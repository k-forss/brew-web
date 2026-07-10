#!/bin/bash
# Test runner script for brew-web
# Uses Docker Compose for ephemeral test PostgreSQL

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${GREEN}🧪 Brew-Web Test Runner${NC}"
echo "================================"

# Cleanup function
cleanup() {
    if [ -n "$TEST_CONTAINER_ID" ]; then
        echo -e "${YELLOW}Stopping test database container...${NC}"
        docker stop "$TEST_CONTAINER_ID" >/dev/null 2>&1 || true
        docker rm "$TEST_CONTAINER_ID" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

# Code quality check functions
check_lint() {
    echo -e "${BLUE}🔍 Running linter (ruff)...${NC}"
    echo "================================"
    if python -m ruff check .; then
        echo -e "${GREEN}✓ Linting passed${NC}"
        return 0
    else
        echo -e "${RED}✗ Linting failed${NC}"
        return 1
    fi
}

check_lint_fix() {
    echo -e "${BLUE}🔧 Auto-fixing lint issues (ruff)...${NC}"
    echo "================================"
    python -m ruff check . --fix
    local LINT_EXIT=$?
    if [ $LINT_EXIT -eq 0 ]; then
        echo -e "${GREEN}✓ Linting passed${NC}"
    else
        echo -e "${YELLOW}⚠️  Some lint issues remain (run 'ruff check .' for details)${NC}"
    fi
    return $LINT_EXIT
}

check_types() {
    echo -e "${BLUE}📝 Running type checker (mypy)...${NC}"
    echo "================================"
    # Run mypy on entire project (including tests/) to match CI scope
    if python -m mypy . --config-file pyproject.toml; then
        echo -e "${GREEN}✓ Type checking passed${NC}"
        return 0
    else
        echo -e "${RED}✗ Type checking failed${NC}"
        return 1
    fi
}

check_format() {
    echo -e "${BLUE}🎨 Checking code format (ruff format)...${NC}"
    echo "================================"
    if python -m ruff format --check .; then
        echo -e "${GREEN}✓ Code formatting passed${NC}"
        return 0
    else
        echo -e "${RED}✗ Code formatting failed${NC}"
        echo -e "${YELLOW}💡 Run 'ruff format .' to auto-fix formatting${NC}"
        return 1
    fi
}

check_format_fix() {
    echo -e "${BLUE}🎨 Auto-formatting code (ruff format)...${NC}"
    echo "================================"
    python -m ruff format .
    local FORMAT_EXIT=$?
    if [ $FORMAT_EXIT -eq 0 ]; then
        echo -e "${GREEN}✓ Code formatting applied${NC}"
    else
        echo -e "${RED}✗ Code formatting failed${NC}"
    fi
    return $FORMAT_EXIT
}

check_security() {
    echo -e "${BLUE}🔒 Running security check (bandit)...${NC}"
    echo "================================"
    # Run bandit on entire project with pyproject.toml config to match CI scope
    # This catches CI workflow issues like missing [toml] extra
    if python -m bandit -r . -c pyproject.toml; then
        echo -e "${GREEN}✓ Security check passed${NC}"
        return 0
    else
        echo -e "${RED}✗ Security check failed${NC}"
        return 1
    fi
}

run_all_checks() {
    local FAILED=0
    
    echo ""
    echo -e "${GREEN}🚀 Running all code quality checks${NC}"
    echo "========================================"
    echo ""
    
    # Lint check
    if ! check_lint; then
        FAILED=1
    fi
    echo ""
    
    # Format check
    if ! check_format; then
        FAILED=1
    fi
    echo ""
    
    # Type check
    if ! check_types; then
        FAILED=1
    fi
    echo ""
    
    # Security check (optional, don't fail overall if bandit not installed)
    if command -v bandit &> /dev/null || python -c "import bandit" 2>/dev/null; then
        if ! check_security; then
            FAILED=1
        fi
        echo ""
    else
        echo -e "${YELLOW}⚠️  Bandit not installed, skipping security check${NC}"
        echo ""
    fi
    
    return $FAILED
}

# Start ephemeral PostgreSQL in Docker
start_test_db() {
    local TEST_PORT=$(shuf -i 5432-5500 -n 1)
    TEST_CONTAINER_ID="brewweb-test-$$"
    
    echo -e "${YELLOW}Starting ephemeral PostgreSQL in Docker (port $TEST_PORT)...${NC}"
    
    docker run -d \
        --name "$TEST_CONTAINER_ID" \
        -e POSTGRES_USER=brewuser \
        -e POSTGRES_PASSWORD=brewpass \
        -e POSTGRES_DB=brewweb-test \
        -p $TEST_PORT:5432 \
        --rm \
        postgres:15 \
        >/dev/null 2>&1
    
    # Wait for PostgreSQL to be ready
    echo -e "${YELLOW}Waiting for PostgreSQL to be ready...${NC}"
    for i in {1..30}; do
        if docker exec "$TEST_CONTAINER_ID" pg_isready -U brewuser -d brewweb-test >/dev/null 2>&1; then
            echo -e "${GREEN}✓ PostgreSQL ready on port $TEST_PORT${NC}"
            export DATABASE_URL="postgresql://brewuser:brewpass@localhost:$TEST_PORT/brewweb-test"
            return 0
        fi
        sleep 1
    done
    
    echo -e "${RED}✗ Failed to start PostgreSQL${NC}"
    return 1
}

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found in PATH${NC}"
    echo "Please install Docker Desktop or Docker Engine"
    exit 1
fi

# Activate virtual environment if it exists
if [ -f ".venv/bin/activate" ]; then
    echo -e "${GREEN}✓ Activating virtual environment${NC}"
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    echo -e "${GREEN}✓ Activating virtual environment${NC}"
    source venv/bin/activate
else
    echo -e "${YELLOW}✓ No venv found, installing in .venv${NC}"
    python -m venv .venv
    echo -e "${GREEN}✓ Installing test dependencies...${NC}"
    .venv/bin/pip install -qr requirements-test.txt
    echo -e "${GREEN}✓ Activating virtual environment${NC}"
    source .venv/bin/activate
fi

# Install test dependencies
echo -e "${YELLOW}Installing test dependencies...${NC}"
pip install -qr requirements-test.txt

# Parse arguments
PYTEST_ARGS=""
PARALLEL_MODE=true
NUM_PROCESSES="auto"
PASSTHROUGH_ARGS=""

# Quality check flags
RUN_LINT=false
RUN_TYPECHECK=false
RUN_FORMAT=false
RUN_SECURITY=false
RUN_ALL_CHECKS=false
QUICK_MODE=false
AUTO_FIX=false
MULTI_PYTHON=false

# Parse arguments for parallel execution and quality checks
while [[ $# -gt 0 ]]; do
    case $1 in
        -n|--numprocesses)
            PARALLEL_MODE=true
            NUM_PROCESSES="$2"
            shift 2
            ;;
        --parallel)
            PARALLEL_MODE=true
            shift
            ;;
        --sequential|--no-parallel)
            PARALLEL_MODE=false
            shift
            ;;
        --lint)
            RUN_LINT=true
            shift
            ;;
        --typecheck|--types)
            RUN_TYPECHECK=true
            shift
            ;;
        --format|--formatter)
            RUN_FORMAT=true
            shift
            ;;
        --security)
            RUN_SECURITY=true
            shift
            ;;
        --full|--all-checks)
            RUN_ALL_CHECKS=true
            shift
            ;;
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --fix)
            AUTO_FIX=true
            shift
            ;;
        --multi-python)
            MULTI_PYTHON=true
            shift
            ;;
        -v|--verbose)
            PYTEST_ARGS="$PYTEST_ARGS -v"
            shift
            ;;
        --cov)
            PYTEST_ARGS="$PYTEST_ARGS --cov=app --cov=config --cov-report=term-missing"
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  Test Execution:"
            echo "    -v, --verbose              Run with verbose output"
            echo "    --cov                     Run with coverage report"
            echo "    -n NUM, --numprocesses=NUM Run tests in parallel with NUM workers"
            echo "    --parallel                Enable parallel execution (auto-detect CPUs)"
            echo "    --sequential              Force sequential execution (default)"
            echo ""
            echo "  Code Quality Checks:"
            echo "    --lint                    Run linter (ruff)"
            echo "    --typecheck, --types      Run type checker (mypy)"
            echo "    --format, --formatter     Check code formatting (ruff format)"
            echo "    --security                Run security scan (bandit)"
            echo "    --full, --all-checks      Run all quality checks + tests"
            echo "    --quick                   Run only tests (skip quality checks)"
            echo "    --fix                     Auto-fix lint and format issues"
            echo "    --multi-python            Test on Python 3.10, 3.11, 3.12 (requires pyenv)"
            echo ""
            echo "  General:"
            echo "    -h, --help                Show this help message"
            echo ""
            echo "How it works:"
            echo "  - Spawns ephemeral PostgreSQL in Docker container"
            echo "  - Random port to avoid conflicts"
            echo "  - Automatic cleanup on exit"
            echo "  - Requires Docker Desktop or Docker Engine"
            echo "  - Parallel mode: Each worker gets isolated schema"
            echo ""
            echo "Environment variables:"
            echo "  DATABASE_URL     Override test database connection"
            echo "  TESTING          Set to 'True' for test mode"
            echo ""
            echo "Examples:"
            echo "  $0                          # Run tests with quality checks"
            echo "  $0 --quick                  # Run only tests (no quality checks)"
            echo "  $0 --full                   # Run all quality checks + tests"
            echo "  $0 --lint --typecheck       # Run specific checks + tests"
            echo "  $0 --fix                    # Auto-fix issues before tests"
            echo "  $0 --parallel --cov         # Parallel with coverage"
            echo "  $0 -n 4                     # Parallel with 4 workers"
            exit 0
            ;;
        --)
            # End of options, pass everything else through
            shift
            PASSTHROUGH_ARGS="$@"
            break
            ;;
        -*)
            # Other pytest options - pass through
            PYTEST_ARGS="$PYTEST_ARGS $1"
            shift
            ;;
        *)
            # Positional arguments (test paths) - pass through
            PASSTHROUGH_ARGS="$PASSTHROUGH_ARGS $1"
            shift
            ;;
    esac
done

# Report parallel mode
if [ "$PARALLEL_MODE" = true ]; then
    echo -e "${BLUE}🚀 Parallel test execution enabled (${NUM_PROCESSES} workers)${NC}"
    echo "   Using pytest-xdist with loadscope scheduling"
    echo ""
fi

# Determine which checks to run
if [ "$QUICK_MODE" = true ]; then
    # Quick mode: skip all quality checks
    echo -e "${YELLOW}⚡ Quick mode: skipping quality checks${NC}"
    echo ""
elif [ "$RUN_ALL_CHECKS" = true ]; then
    # Full mode: run all quality checks
    echo -e "${GREEN}📋 Running full quality suite...${NC}"
    if ! run_all_checks; then
        echo -e "${RED}❌ Quality checks failed${NC}"
        exit 1
    fi
elif [ "$RUN_LINT" = true ] || [ "$RUN_TYPECHECK" = true ] || [ "$RUN_FORMAT" = true ] || [ "$RUN_SECURITY" = true ]; then
    # Individual checks requested
    CHECKS_FAILED=0
    
    if [ "$RUN_LINT" = true ]; then
        if [ "$AUTO_FIX" = true ]; then
            check_lint_fix || CHECKS_FAILED=1
        else
            check_lint || CHECKS_FAILED=1
        fi
        echo ""
    fi
    
    if [ "$RUN_FORMAT" = true ]; then
        if [ "$AUTO_FIX" = true ]; then
            check_format_fix || CHECKS_FAILED=1
        else
            check_format || CHECKS_FAILED=1
        fi
        echo ""
    fi
    
    if [ "$RUN_TYPECHECK" = true ]; then
        check_types || CHECKS_FAILED=1
        echo ""
    fi
    
    if [ "$RUN_SECURITY" = true ]; then
        check_security || CHECKS_FAILED=1
        echo ""
    fi
    
    if [ $CHECKS_FAILED -ne 0 ]; then
        echo -e "${RED}❌ Some quality checks failed${NC}"
        exit 1
    fi
else
    # Default mode: run quality checks before tests
    echo -e "${GREEN}📋 Running default quality checks...${NC}"
    if ! run_all_checks; then
        echo -e "${RED}❌ Quality checks failed${NC}"
        echo -e "${YELLOW}💡 Tip: Use --quick to skip quality checks or --fix to auto-fix issues${NC}"
        exit 1
    fi
fi

# Multi-Python version testing (catches version-specific failures like B2)
if [ "$MULTI_PYTHON" = true ]; then
    echo -e "${GREEN}🐍 Running multi-Python version tests...${NC}"
    echo "================================"
    
    if ! command -v pyenv &> /dev/null; then
        echo -e "${RED}✗ pyenv not found. Install pyenv for multi-Python testing${NC}"
        echo "💡 See: https://github.com/pyenv/pyenv#installation"
        exit 1
    fi
    
    PYTHON_VERSIONS=("3.10" "3.11" "3.12")
    FAILED=0
    
    for PYVER in "${PYTHON_VERSIONS[@]}"; do
        echo -e "${BLUE}Testing on Python $PYVER...${NC}"
        
        # Create version-specific virtualenv
        VENV_DIR=".venv-py${PYVER//./}"
        if [ ! -d "$VENV_DIR" ]; then
            echo -e "${YELLOW}Creating virtualenv for Python $PYVER...${NC}"
            pyenv shell "$PYVER"
            pyenv exec python -m venv "$VENV_DIR"
            pyenv shell --unset
        fi
        
        # Activate and install deps
        source "$VENV_DIR/bin/activate"
        pip install -qr requirements-test.txt >/dev/null 2>&1
        
        # Run tests
        python -m pytest --tb=short -q
        TEST_EXIT=$?
        
        if [ $TEST_EXIT -ne 0 ]; then
            echo -e "${RED}✗ Tests failed on Python $PYVER${NC}"
            FAILED=1
        else
            echo -e "${GREEN}✓ Tests passed on Python $PYVER${NC}"
        fi
        
        deactivate
        echo ""
    done
    
    if [ $FAILED -ne 0 ]; then
        echo -e "${RED}❌ Multi-Python testing failed${NC}"
        exit 1
    fi
    
    # Reactivate main venv for final steps
    source .venv/bin/activate
fi

# Start test database
if ! start_test_db; then
    echo -e "${YELLOW}⚠️  Could not start test database${NC}"
    echo "Falling back to SQLite in-memory database"
    export DATABASE_URL="sqlite:///:memory:"
fi

# Run tests
echo ""
echo -e "${GREEN}Running pytest...${NC}"
echo "================================"

# Run pytest
if [ "$PARALLEL_MODE" = true ]; then
    # Parallel execution with pytest-xdist
    python -m pytest $PYTEST_ARGS -n "$NUM_PROCESSES" --dist=loadscope $PASSTHROUGH_ARGS
else
    # Sequential execution
    python -m pytest $PYTEST_ARGS $PASSTHROUGH_ARGS
fi
TEST_EXIT_CODE=$?

# Report results
echo ""
if [ $TEST_EXIT_CODE -eq 0 ]; then
    echo -e "${GREEN}✅ All tests passed!${NC}"
else
    echo -e "${RED}❌ Some tests failed (exit code: $TEST_EXIT_CODE)${NC}"
fi

exit $TEST_EXIT_CODE
