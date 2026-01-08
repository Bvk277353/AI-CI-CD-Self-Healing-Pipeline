# Demo Application

This is a simple FastAPI application used to demonstrate the self-healing capabilities of the AI-Powered CI/CD Pipeline.

## Purpose

The demo app intentionally includes various scenarios that can trigger pipeline failures, allowing the self-healing system to demonstrate its capabilities.

## Features

- **Health Check Endpoints**: `/` and `/health`
- **CRUD Operations**: Basic item creation and retrieval
- **Test Suite**: Comprehensive tests including flaky tests

## Running Locally

```bash
# Install dependencies
pip install -r requirements.txt

# Run the application
uvicorn app:app --host 0.0.0.0 --port 8080

# Run tests
pytest tests/ -v
```

## API Endpoints

### GET /
Health check endpoint
```json
{
  "status": "healthy",
  "message": "Demo app is running"
}
```

### GET /health
Kubernetes health check
```json
{
  "status": "ok"
}
```

### POST /items/
Create a new item
```json
{
  "name": "Test Item",
  "value": 42
}
```

### GET /items/{item_id}
Get an item by ID

## Testing

The test suite includes:
- Unit tests
- Integration tests
- Performance tests
- Flaky tests (for demonstration)

Run tests:
```bash
pytest tests/ -v --cov=./ --cov-report=html
```

## Docker

Build and run with Docker:
```bash
docker build -t demo-app .
docker run -p 8080:8080 demo-app
```

## Self-Healing Scenarios

This app is designed to test the following healing scenarios:

1. **Missing Dependencies**: Import new packages without adding to requirements.txt
2. **Flaky Tests**: Tests that fail intermittently
3. **Test Timeouts**: Long-running tests that exceed timeouts
4. **Deployment Issues**: Code that causes crashes or high error rates

## License

MIT License - Part of AI Self-Healing CI/CD Pipeline Project