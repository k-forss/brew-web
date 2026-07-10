#!/bin/bash
# Coverage report generator for brew-web
# Uses Docker for ephemeral test PostgreSQL

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}📊 Brew-Web Coverage Report Generator${NC}"
echo "=========================================="

# Cleanup function
cleanup() {
    if [ -n "$TEST_CONTAINER_ID" ]; then
        echo -e "${YELLOW}Stopping test database container...${NC}"
        docker stop "$TEST_CONTAINER_ID" >/dev/null 2>&1 || true
        docker rm "$TEST_CONTAINER_ID" >/dev/null 2>&1 || true
    fi
}
trap cleanup EXIT

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
    for i in {1..30}; do
        if docker exec "$TEST_CONTAINER_ID" pg_isready -U brewuser -d brewweb-test >/dev/null 2>&1; then
            export DATABASE_URL="postgresql://brewuser:brewpass@localhost:$TEST_PORT/brewweb-test"
            return 0
        fi
        sleep 1
    done
    
    return 1
}

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found in PATH${NC}"
    echo "Please install Docker Desktop or Docker Engine"
    exit 1
fi

# Start test database
if ! start_test_db; then
    echo -e "${YELLOW}⚠️  Could not start test database${NC}"
    echo "Falling back to SQLite in-memory database"
    export DATABASE_URL="sqlite:///:memory:"
fi

# Activate virtual environment if it exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Check if pytest-cov is installed
if ! python -c "import pytest_cov" &> /dev/null; then
    echo -e "${YELLOW}Installing pytest-cov...${NC}"
    pip install pytest-cov
fi

# Run tests with coverage
echo -e "${GREEN}Running tests with coverage...${NC}"
python -m pytest \
    --cov=app \
    --cov=config \
    --cov-report=term-missing \
    --cov-report=html:htmlcov \
    --cov-report=xml:coverage.xml \
    --cov-fail-under=80 \
    tests/

# Check if coverage threshold was met
COVERAGE_FILE=".coverage"
if [ -f "$COVERAGE_FILE" ]; then
    echo ""
    echo -e "${GREEN}✓ Coverage data generated${NC}"
    echo ""
    echo -e "${BLUE}Coverage reports:${NC}"
    echo "  - Terminal: (shown above)"
    echo "  - HTML:     file://$PROJECT_ROOT/htmlcov/index.html"
    echo "  - XML:      $PROJECT_ROOT/coverage.xml"
    echo ""
    echo -e "${YELLOW}To view HTML report:${NC}"
    echo "  open htmlcov/index.html  # macOS"
    echo "  xdg-open htmlcov/index.html  # Linux"
    echo "  start htmlcov\\index.html  # Windows"
else
    echo -e "${YELLOW}⚠️  Coverage file not found${NC}"
fi

echo ""
echo -e "${GREEN}✅ Coverage report generation complete!${NC}"
