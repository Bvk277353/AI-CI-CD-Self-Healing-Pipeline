#!/bin/bash

# Deployment Script for AI Self-Healing CI/CD Pipeline
# Deploys the application to Kubernetes

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

# Check prerequisites
check_prerequisites() {
    print_header "Checking Prerequisites"
    
    if ! command -v kubectl &> /dev/null; then
        print_error "kubectl not found. Please install kubectl"
        exit 1
    fi
    print_success "kubectl is installed"
    
    if ! command -v docker &> /dev/null; then
        print_error "docker not found. Please install docker"
        exit 1
    fi
    print_success "docker is installed"
    
    # Check kubectl connection
    if ! kubectl cluster-info &> /dev/null; then
        print_error "Cannot connect to Kubernetes cluster"
        exit 1
    fi
    print_success "Connected to Kubernetes cluster"
}

# Build Docker images
build_images() {
    print_header "Building Docker Images"
    
    # Load environment variables
    if [ -f .env ]; then
        export $(cat .env | grep -v '^#' | xargs)
    else
        print_error ".env file not found"
        exit 1
    fi
    
    print_info "Building pipeline-monitor image..."
    docker build -t ${DOCKER_USERNAME}/pipeline-monitor:latest ./pipeline-monitor
    print_success "pipeline-monitor image built"
    
    print_info "Building demo-app image..."
    docker build -t ${DOCKER_USERNAME}/demo-app:latest ./demo-app
    print_success "demo-app image built"
}

# Push Docker images
push_images() {
    print_header "Pushing Docker Images"
    
    print_info "Logging in to Docker Hub..."
    echo ${DOCKER_PASSWORD} | docker login -u ${DOCKER_USERNAME} --password-stdin
    
    print_info "Pushing pipeline-monitor..."
    docker push ${DOCKER_USERNAME}/pipeline-monitor:latest
    print_success "pipeline-monitor pushed"
    
    print_info "Pushing demo-app..."
    docker push ${DOCKER_USERNAME}/demo-app:latest
    print_success "demo-app pushed"
}

# Create Kubernetes secrets
create_secrets() {
    print_header "Creating Kubernetes Secrets"
    
    kubectl create namespace healing-cicd --dry-run=client -o yaml | kubectl apply -f -
    
    kubectl create secret generic github-credentials \
        --from-literal=token=${GITHUB_TOKEN} \
        --from-literal=repo=${GITHUB_REPO} \
        --namespace=healing-cicd \
        --dry-run=client -o yaml | kubectl apply -f -
    
    print_success "Secrets created"
}

# Deploy to Kubernetes
deploy_k8s() {
    print_header "Deploying to Kubernetes"
    
    print_info "Applying namespace..."
    kubectl apply -f kubernetes/namespace.yaml
    
    print_info "Deploying PostgreSQL..."
    kubectl apply -f kubernetes/postgres-deployment.yaml
    print_success "PostgreSQL deployed"
    
    print_info "Deploying Redis..."
    kubectl apply -f kubernetes/redis-deployment.yaml
    print_success "Redis deployed"
    
    print_info "Deploying Pipeline Monitor..."
    kubectl apply -f kubernetes/pipeline-monitor-deployment.yaml
    print_success "Pipeline Monitor deployed"
    
    print_info "Deploying Grafana..."
    kubectl apply -f kubernetes/grafana-deployment.yaml
    print_success "Grafana deployed"
    
    print_info "Creating Ingress..."
    kubectl apply -f kubernetes/ingress.yaml
    print_success "Ingress created"
}

# Wait for deployments
wait_for_deployments() {
    print_header "Waiting for Deployments"
    
    deployments=("postgres" "redis" "pipeline-monitor" "grafana")
    
    for deployment in "${deployments[@]}"; do
        print_info "Waiting for $deployment..."
        kubectl rollout status deployment/$deployment -n healing-cicd --timeout=5m
        print_success "$deployment is ready"
    done
}

# Run database migrations
run_migrations() {
    print_header "Running Database Migrations"
    
    # Get pipeline-monitor pod name
    POD_NAME=$(kubectl get pods -n healing-cicd -l app=pipeline-monitor -o jsonpath='{.items[0].metadata.name}')
    
    print_info "Running migrations on pod: $POD_NAME"
    kubectl exec -n healing-cicd $POD_NAME -- python -c "
from app.models import Database
import asyncio

async def run():
    db = Database()
    await db.connect()
    print('Database initialized successfully')

asyncio.run(run())
"
    
    print_success "Migrations completed"
}

# Display access information
display_info() {
    print_header "Deployment Complete!"
    
    print_info "Access URLs:"
    
    # Get external IPs
    GRAFANA_IP=$(kubectl get svc grafana -n healing-cicd -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")
    MONITOR_IP=$(kubectl get svc pipeline-monitor -n healing-cicd -o jsonpath='{.status.loadBalancer.ingress[0].ip}' 2>/dev/null || echo "pending")
    
    echo ""
    echo "Pipeline Monitor API: http://${MONITOR_IP}:8000"
    echo "API Documentation: http://${MONITOR_IP}:8000/docs"
    echo "Grafana Dashboard: http://${GRAFANA_IP}:3000"
    echo "  Username: admin"
    echo "  Password: admin"
    echo ""
    
    print_info "To view logs:"
    echo "  kubectl logs -f deployment/pipeline-monitor -n healing-cicd"
    echo ""
    
    print_info "To scale deployment:"
    echo "  kubectl scale deployment/pipeline-monitor --replicas=3 -n healing-cicd"
    echo ""
    
    print_success "Deployment successful! 🎉"
}

# Rollback function
rollback() {
    print_header "Rolling Back Deployment"
    
    print_info "Rolling back all deployments..."
    
    kubectl rollout undo deployment/pipeline-monitor -n healing-cicd
    kubectl rollout undo deployment/postgres -n healing-cicd
    kubectl rollout undo deployment/redis -n healing-cicd
    kubectl rollout undo deployment/grafana -n healing-cicd
    
    print_success "Rollback completed"
}

# Main execution
main() {
    case "${1:-deploy}" in
        deploy)
            check_prerequisites
            build_images
            push_images
            create_secrets
            deploy_k8s
            wait_for_deployments
            run_migrations
            display_info
            ;;
        rollback)
            rollback
            ;;
        update)
            build_images
            push_images
            kubectl rollout restart deployment/pipeline-monitor -n healing-cicd
            wait_for_deployments
            print_success "Update completed"
            ;;
        logs)
            kubectl logs -f deployment/pipeline-monitor -n healing-cicd
            ;;
        status)
            kubectl get all -n healing-cicd
            ;;
        delete)
            print_info "Deleting all resources..."
            kubectl delete namespace healing-cicd
            print_success "All resources deleted"
            ;;
        *)
            echo "Usage: $0 {deploy|rollback|update|logs|status|delete}"
            exit 1
            ;;
    esac
}

main "$@"