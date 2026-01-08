#!/bin/bash

# Test Healing Scenarios Script
# This script tests various failure scenarios and demonstrates auto-healing

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "\n${BLUE}================================${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}================================${NC}\n"
}

print_success() {
    echo -e "${GREEN}✓ $1${NC}"
}

print_error() {
    echo -e "${RED}✗ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

# Load environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    print_error ".env file not found"
    exit 1
fi

API_URL=${API_URL:-http://localhost:8000}

# Test 1: Missing Dependency
test_missing_dependency() {
    print_header "Test 1: Missing Dependency Auto-Fix"
    
    print_info "Creating a branch with missing dependency..."
    
    # Create test branch
    git checkout -b test-missing-dep-$(date +%s) 2>/dev/null || git checkout test-missing-dep
    
    # Create file with missing import
    cat > demo-app/test_pandas_feature.py << 'EOF'
import pandas as pd

def process_data():
    df = pd.DataFrame({"col1": [1, 2, 3]})
    return df.describe()

if __name__ == "__main__":
    print(process_data())
EOF
    
    git add demo-app/test_pandas_feature.py
    git commit -m "Add pandas functionality (missing dependency)"
    
    print_info "Pushing to trigger pipeline..."
    git push origin HEAD
    
    print_warning "Expected behavior:"
    echo "  1. Pipeline will fail with: ModuleNotFoundError: No module named 'pandas'"
    echo "  2. Healing system detects missing dependency"
    echo "  3. Auto-adds 'pandas' to requirements.txt"
    echo "  4. Commits the fix"
    echo "  5. Re-triggers pipeline"
    echo "  6. Build succeeds ✅"
    
    print_info "Monitor at: ${API_URL}/pipelines/status"
    
    # Cleanup
    git checkout main
    git branch -D test-missing-dep 2>/dev/null || true
}

# Test 2: Flaky Test
test_flaky_test() {
    print_header "Test 2: Flaky Test Auto-Fix"
    
    print_info "Creating a flaky test..."
    
    git checkout -b test-flaky-$(date +%s) 2>/dev/null || git checkout test-flaky
    
    # Create flaky test
    cat > demo-app/tests/test_flaky_demo.py << 'EOF'
import pytest
import random

def test_unreliable():
    """This test fails randomly to demonstrate flaky test detection"""
    if random.random() < 0.4:  # 40% failure rate
        pytest.fail("Random failure to simulate flakiness")
    assert True
EOF
    
    git add demo-app/tests/test_flaky_demo.py
    git commit -m "Add flaky test"
    git push origin HEAD
    
    print_warning "Expected behavior:"
    echo "  1. Test fails intermittently"
    echo "  2. Healing system detects flaky pattern"
    echo "  3. Adds pytest-rerunfailures to requirements.txt"
    echo "  4. Configures pytest with --reruns 3"
    echo "  5. Test passes on retry ✅"
    
    git checkout main
    git branch -D test-flaky 2>/dev/null || true
}

# Test 3: Test Timeout
test_timeout() {
    print_header "Test 3: Test Timeout Auto-Fix"
    
    print_info "Creating a slow test..."
    
    git checkout -b test-timeout-$(date +%s) 2>/dev/null || git checkout test-timeout
    
    cat > demo-app/tests/test_slow.py << 'EOF'
import pytest
import time

@pytest.mark.timeout(60)
def test_slow_operation():
    """This test takes longer than default timeout"""
    time.sleep(65)  # Exceeds 60s timeout
    assert True
EOF
    
    git add demo-app/tests/test_slow.py
    git commit -m "Add slow test"
    git push origin HEAD
    
    print_warning "Expected behavior:"
    echo "  1. Test times out after 60s"
    echo "  2. Healing system detects timeout"
    echo "  3. Increases timeout to 300s in pytest.ini"
    echo "  4. Test completes successfully ✅"
    
    git checkout main
    git branch -D test-timeout 2>/dev/null || true
}

# Test 4: API Health Check
test_api_health() {
    print_header "Test 4: API Health Check"
    
    print_info "Checking API health..."
    
    response=$(curl -s ${API_URL}/)
    
    if echo "$response" | grep -q "healthy"; then
        print_success "API is healthy"
        echo "$response" | jq '.' 2>/dev/null || echo "$response"
    else
        print_error "API health check failed"
        echo "$response"
        return 1
    fi
}

# Test 5: Get Healing Statistics
test_healing_stats() {
    print_header "Test 5: Healing Statistics"
    
    print_info "Fetching healing statistics..."
    
    response=$(curl -s ${API_URL}/analytics/success-rate)
    
    if [ $? -eq 0 ]; then
        print_success "Statistics retrieved"
        echo "$response" | jq '.' 2>/dev/null || echo "$response"
    else
        print_error "Failed to retrieve statistics"
        return 1
    fi
}

# Test 6: Get Failure Patterns
test_failure_patterns() {
    print_header "Test 6: Failure Patterns Analysis"
    
    print_info "Fetching failure patterns..."
    
    response=$(curl -s ${API_URL}/analytics/failure-patterns)
    
    if [ $? -eq 0 ]; then
        print_success "Failure patterns retrieved"
        echo "$response" | jq '.' 2>/dev/null || echo "$response"
    else
        print_error "Failed to retrieve failure patterns"
        return 1
    fi
}

# Test 7: Manual Healing Trigger
test_manual_healing() {
    print_header "Test 7: Manual Healing Trigger"
    
    print_info "Triggering manual healing for a run..."
    
    # Get recent run ID
    run_id=$(curl -s ${API_URL}/pipelines/status?limit=1 | jq -r '.[0].run_id' 2>/dev/null)
    
    if [ -z "$run_id" ] || [ "$run_id" = "null" ]; then
        print_warning "No recent runs found to test manual healing"
        return 0
    fi
    
    print_info "Triggering healing for run: $run_id"
    
    response=$(curl -s -X POST ${API_URL}/manual-heal/${run_id})
    
    if echo "$response" | grep -q "healing_triggered"; then
        print_success "Manual healing triggered"
        echo "$response" | jq '.' 2>/dev/null || echo "$response"
    else
        print_warning "Healing may have already been attempted for this run"
        echo "$response"
    fi
}

# Test 8: Simulate Deployment Rollback
test_deployment_rollback() {
    print_header "Test 8: Deployment Rollback (Simulation)"
    
    print_info "This test simulates a deployment rollback scenario"
    print_warning "Note: Actual rollback requires Kubernetes deployment"
    
    # Create broken code
    cat > demo-app/broken_app.py << 'EOF'
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    # This will crash the application
    raise Exception("Critical bug causing crash!")
    return {"status": "ok"}
EOF
    
    print_info "Expected behavior:"
    echo "  1. Deploy broken version"
    echo "  2. Health check fails"
    echo "  3. Error rate spikes"
    echo "  4. Auto-rollback initiated"
    echo "  5. Previous version restored ✅"
    echo "  6. Team notified via Slack"
    
    rm demo-app/broken_app.py
}

# Test 9: Model Retraining
test_model_retraining() {
    print_header "Test 9: ML Model Retraining"
    
    print_info "Triggering model retraining..."
    
    response=$(curl -s -X POST ${API_URL}/train-model)
    
    if echo "$response" | grep -q "training_started"; then
        print_success "Model retraining initiated"
        print_info "This will take a few minutes..."
        echo "$response" | jq '.' 2>/dev/null || echo "$response"
    else
        print_error "Failed to trigger retraining"
        echo "$response"
        return 1
    fi
}

# Test 10: End-to-End Integration
test_e2e_integration() {
    print_header "Test 10: End-to-End Integration"
    
    print_info "Running comprehensive integration test..."
    
    # Check all services
    services=("API" "Database" "ML Model")
    all_healthy=true
    
    response=$(curl -s ${API_URL}/)
    
    if echo "$response" | jq -e '.services' > /dev/null 2>&1; then
        for service in "${services[@]}"; do
            status=$(echo "$response" | jq -r ".services.${service,,}")
            if [ "$status" = "true" ]; then
                print_success "$service is healthy"
            else
                print_error "$service is not healthy"
                all_healthy=false
            fi
        done
    else
        print_warning "Could not check individual service status"
    fi
    
    if [ "$all_healthy" = true ]; then
        print_success "All services healthy - Integration test passed ✅"
    else
        print_error "Some services are not healthy"
        return 1
    fi
}

# Menu
show_menu() {
    clear
    cat << "EOF"
╔══════════════════════════════════════════════════════════╗
║     AI Self-Healing CI/CD Pipeline                       ║
║     Test Suite                                           ║
╚══════════════════════════════════════════════════════════╝
EOF
    
    echo ""
    echo "Select a test to run:"
    echo ""
    echo "  1. Missing Dependency Auto-Fix"
    echo "  2. Flaky Test Auto-Fix"
    echo "  3. Test Timeout Auto-Fix"
    echo "  4. API Health Check"
    echo "  5. Healing Statistics"
    echo "  6. Failure Patterns Analysis"
    echo "  7. Manual Healing Trigger"
    echo "  8. Deployment Rollback (Simulation)"
    echo "  9. ML Model Retraining"
    echo " 10. End-to-End Integration Test"
    echo ""
    echo "  0. Run All Tests"
    echo "  q. Quit"
    echo ""
}

# Run all tests
run_all_tests() {
    print_header "Running All Tests"
    
    test_api_health
    test_healing_stats
    test_failure_patterns
    test_manual_healing
    test_model_retraining
    test_e2e_integration
    
    # Git-based tests (commented out by default)
    # test_missing_dependency
    # test_flaky_test
    # test_timeout
    
    print_success "All tests completed!"
}

# Main execution
main() {
    if [ "$1" = "--auto" ]; then
        run_all_tests
        exit 0
    fi
    
    while true; do
        show_menu
        read -p "Enter choice: " choice
        
        case $choice in
            1) test_missing_dependency ;;
            2) test_flaky_test ;;
            3) test_timeout ;;
            4) test_api_health ;;
            5) test_healing_stats ;;
            6) test_failure_patterns ;;
            7) test_manual_healing ;;
            8) test_deployment_rollback ;;
            9) test_model_retraining ;;
            10) test_e2e_integration ;;
            0) run_all_tests ;;
            q|Q) 
                print_info "Exiting..."
                exit 0
                ;;
            *)
                print_error "Invalid choice"
                ;;
        esac
        
        echo ""
        read -p "Press Enter to continue..."
    done
}

main "$@"