# AI-Powered Self-Healing CI/CD Pipeline – Project Context

## Author
Bala Vardhan Kumar Doupati  
Final Year B.Tech – CSE (AI & ML)

## Project Goal
This project is NOT a single application.
It is a **generic backend CI/CD pipeline platform** that can:
- Monitor GitHub Actions workflows
- Predict pipeline failures using ML
- Detect common CI/CD issues (flaky tests, dependency errors, version mismatch, install failures)
- Auto-heal pipelines by applying fixes
- Re-run workflows
- Expose metrics via Prometheus
- Visualize pipeline health via Grafana
- Work with ANY application by training a different ML model

---

## High-Level Architecture
- GitHub Actions → CI/CD execution
- Pipeline Monitor (FastAPI)
- ML Failure Predictor (scikit-learn models)
- Healing Engine (rule + ML assisted)
- Redis (state/cache)
- PostgreSQL (metadata, logs)
- Prometheus (metrics)
- Grafana (dashboards)
- Docker Compose (local orchestration)

---

## Current Folder Structure (Final)
<PASTE YOUR FINAL STRUCTURE HERE>

---

## Services and Ports
- Pipeline Monitor: http://localhost:8000
- Demo App: http://localhost:8080
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Redis: 6379
- Redis Exporter: 9121

---

## Completed Milestones
- [x] Dockerized all services
- [x] ML model trained and loaded
- [x] Pipeline Monitor running
- [x] GitHub workflow polling
- [x] Prometheus metrics exposed
- [x] Grafana dashboards connected
- [x] Redis + Redis Exporter integrated
- [x] Demo app metrics exposed

---

## Known Fixes Applied
- Prometheus metrics via `prometheus_fastapi_instrumentator`
- Redis metrics via `redis_exporter`
- Docker network DNS fixes
- GitHub API safety checks (empty runs)
- Sklearn version mismatch tolerated
- Metrics endpoints fixed (/metrics)

---

## How to Start Project
```bash
docker compose up -d

