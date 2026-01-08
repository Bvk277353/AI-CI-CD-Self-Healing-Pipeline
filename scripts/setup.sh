#!/bin/bash

# AI-Powered Self-Healing CI/CD Pipeline Setup Script
# This script sets up the complete project automatically

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Functions
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

print_warning() {
    echo -e "${YELLOW}⚠ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ $1${NC}"
}

check_command() {
    if command -v $1 &> /dev/null; then
        print_success "$1 is installed"
        return 0
    else
        print_error "$1 is not installed"
        return 1
    fi
}

# Banner
clear
echo -e "${BLUE}"
cat << "EOF"
    _    ___       ____       _  __      _   _            _ _             
   / \  |_ _|     / ___|  ___| |/ _|    | | | | ___  __ _| (_)_ __   __ _ 
  / _ \  | |_____\___ \ / _ \ | |_ ____| |_| |/ _ \/ _` | | | '_ \ / _` |
 / ___ \ | |_____|___) |  __/ |  _|____|  _  |  __/ (_| | | | | | | (_| |
/_/   \_\___|    |____/ \___|_|_|      |_| |_|\___|\__,_|_|_|_| |_|\__, |
                                                                     |___/ 
   ____ ___    ____ ____    ____  _            _ _            
  / ___|_ _|  / ___|  _ \  |  _ \(_)_ __   ___| (_)_ __   ___ 
 | |    | |  | |   | | | | | |_) | | '_ \ / _ \ | | '_ \ / _ \
 | |___ | |  | |___| |_| | |  __/| | |_) |  __/ | | | | |  __/
  \____|___|  \____|____/  |_|   |_| .__/ \___|_|_|_| |_|\___|
                                   |_|                         
EOF
echo -e "${NC}"

print_header "Checking Prerequisites"

# Check required software
MISSING_DEPS=0

if ! check_command "git"; then
    MISSING_DEPS=1
fi

if ! check_command "docker"; then
    MISSING_DEPS=1
fi

if ! check_command "docker-compose"; then
    MISSING_DEPS=1
fi

if ! check_command "python3"; then
    MISSING_DEPS=1
fi

if ! check_command "pip3"; then
    MISSING_DEPS=1
fi

if [ $MISSING_DEPS -eq 1 ]; then
    print_error "Please install missing dependencies before continuing"
    exit 1
fi

print_success "All prerequisites installed!"

# Create directory structure
print_header "Creating Project Structure"

mkdir -p pipeline-monitor/app
mkdir -p ml-models/models
mkdir -p demo-app/{tests,app}
mkdir -p kubernetes
mkdir -p monitoring/{grafana/{dashboards,datasources},prometheus}
mkdir -p scripts
mkdir -p nginx
mkdir -p .github/workflows

print_success "Project structure created"

# Create .env file if it doesn't exist
print_header "Configuring Environment"

if [ ! -f .env ]; then
    print_info "Creating .env file..."
    cat > .env << 'EOF'
# GitHub Configuration
GITHUB_TOKEN=your_github_token_here
GITHUB_REPO=username/repo-name

# Database Configuration
DATABASE_URL=postgresql://cicd_user:secure_password@postgres:5432/cicd_healing

# Redis Configuration
REDIS_URL=redis://redis:6379/0

# Docker Configuration
DOCKER_USERNAME=your_dockerhub_username
DOCKER_PASSWORD=your_dockerhub_password

# Slack Notifications (Optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
EOF
    print_warning "Please edit .env file and add your credentials"
    print_info "You'll need:"
    echo "  1. GitHub Personal Access Token"
    echo "  2. GitHub Repository name (username/repo)"
    echo "  3. Docker Hub credentials"
    echo "  4. (Optional) Slack webhook URL"
else
    print_success ".env file already exists"
fi

# Create requirements.txt files
print_header "Creating Requirements Files"

cat > pipeline-monitor/requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
sqlalchemy==2.0.23
asyncpg==0.29.0
alembic==1.12.1
python-multipart==0.0.6
python-dotenv==1.0.0
httpx==0.25.1
PyGithub==2.1.1
redis==5.0.1
celery==5.3.4
prometheus-client==0.19.0
scikit-learn==1.3.2
tensorflow==2.15.0
pandas==2.1.3
numpy==1.26.2
joblib==1.3.2
psycopg2-binary==2.9.9
EOF

cat > demo-app/requirements.txt << 'EOF'
fastapi==0.104.1
uvicorn[standard]==0.24.0
pydantic==2.5.0
pytest==7.4.3
pytest-cov==4.1.0
pytest-timeout==2.2.0
pytest-rerunfailures==12.0
httpx==0.25.1
EOF

cat > ml-models/requirements.txt << 'EOF'
scikit-learn==1.3.2
tensorflow==2.15.0
pandas==2.1.3
numpy==1.26.2
joblib==1.3.2
matplotlib==3.8.2
seaborn==0.13.0
EOF

print_success "Requirements files created"

# Create Dockerfiles
print_header "Creating Docker Configuration"

cat > pipeline-monitor/Dockerfile << 'EOF'
FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    git curl && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
EOF

cat > demo-app/Dockerfile << 'EOF'
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8080"]
EOF

print_success "Dockerfiles created"

# Create database init script
cat > scripts/init_db.sql << 'EOF'
CREATE TABLE IF NOT EXISTS pipeline_runs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) UNIQUE NOT NULL,
    repo VARCHAR(255) NOT NULL,
    status VARCHAR(50) NOT NULL,
    conclusion VARCHAR(50),
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS failure_logs (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL,
    error_type VARCHAR(100) NOT NULL,
    error_message TEXT,
    stack_trace TEXT,
    severity VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS healing_actions (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255) NOT NULL,
    action_type VARCHAR(100) NOT NULL,
    success BOOLEAN NOT NULL,
    details JSONB,
    changes_made TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (run_id) REFERENCES pipeline_runs(run_id)
);

CREATE TABLE IF NOT EXISTS metrics (
    id SERIAL PRIMARY KEY,
    run_id VARCHAR(255),
    metric_name VARCHAR(100) NOT NULL,
    metric_value FLOAT NOT NULL,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_pipeline_runs_status ON pipeline_runs(status, conclusion);
CREATE INDEX idx_failure_logs_error_type ON failure_logs(error_type);
CREATE INDEX idx_healing_actions_success ON healing_actions(success);
EOF

print_success "Database scripts created"

# Create Prometheus configuration
cat > monitoring/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

scrape_configs:
  - job_name: 'pipeline-monitor'
    static_configs:
      - targets: ['pipeline-monitor:8000']
  
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
EOF

print_success "Prometheus configuration created"

# Create .gitignore
cat > .gitignore << 'EOF'
# Environment
.env
*.env

# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
ENV/
env/

# ML Models
ml-models/models/*.pkl
ml-models/models/*.h5

# IDE
.vscode/
.idea/
*.swp
*.swo

# Docker
*.log

# Database
*.db
*.sqlite

# OS
.DS_Store
Thumbs.db
EOF

print_success ".gitignore created"

# Install Python packages locally (optional)
print_header "Setting Up Python Environment"

read -p "Do you want to create a Python virtual environment? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    python3 -m venv venv
    source venv/bin/activate
    pip install --upgrade pip
    pip install -r pipeline-monitor/requirements.txt
    print_success "Python virtual environment created and activated"
fi

# Docker setup
print_header "Starting Docker Services"

read -p "Do you want to start Docker services now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Building Docker images..."
    docker-compose build
    
    print_info "Starting services..."
    docker-compose up -d
    
    sleep 10  # Wait for services to start
    
    print_info "Checking service status..."
    docker-compose ps
    
    print_success "Docker services started!"
    print_info "Services available at:"
    echo "  - Pipeline Monitor: http://localhost:8000"
    echo "  - Grafana: http://localhost:3000 (admin/admin)"
    echo "  - Prometheus: http://localhost:9090"
    echo "  - Demo App: http://localhost:8080"
fi

# Train ML models
print_header "ML Model Training"

read -p "Do you want to train ML models now? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    print_info "Training models (this may take a few minutes)..."
    docker-compose run --rm ml-trainer || print_warning "Model training will be done later"
fi

# Summary
print_header "Setup Complete!"

print_success "Project setup completed successfully!"
print_info "\nNext Steps:"
echo "1. Edit .env file with your credentials:"
echo "   - GitHub Token (get from: https://github.com/settings/tokens)"
echo "   - GitHub Repository name"
echo "   - Docker Hub credentials"
echo ""
echo "2. Copy workflow file to your repository:"
echo "   cp github-actions/self-healing-pipeline.yml .github/workflows/"
echo ""
echo "3. Initialize Git (if not already):"
echo "   git init"
echo "   git add ."
echo "   git commit -m 'Initial commit: AI Self-Healing CI/CD Pipeline'"
echo ""
echo "4. Push to GitHub:"
echo "   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git"
echo "   git push -u origin main"
echo ""
echo "5. View services:"
echo "   - Pipeline Monitor API: http://localhost:8000/docs"
echo "   - Grafana Dashboard: http://localhost:3000"
echo "   - Prometheus Metrics: http://localhost:9090"
echo ""
echo "6. Test the system:"
echo "   bash scripts/test_healing.sh"
echo ""

print_info "For detailed documentation, check docs/SETUP.md"
print_info "For troubleshooting, check docs/TROUBLESHOOTING.md"

echo -e "\n${GREEN}🎉 Happy coding!${NC}\n"
