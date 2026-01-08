"""
Test suite for demo application
"""

import pytest
from fastapi.testclient import TestClient
from app import app

client = TestClient(app)

def test_read_root():
    """Test root endpoint"""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

def test_health_check():
    """Test health endpoint"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_create_item():
    """Test item creation"""
    response = client.post(
        "/items/",
        json={"name": "Test Item", "value": 42}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Test Item"
    assert data["value"] == 42

def test_read_item():
    """Test reading an item"""
    response = client.get("/items/1")
    assert response.status_code == 200
    assert response.json()["id"] == 1

def test_read_nonexistent_item():
    """Test reading a non-existent item"""
    response = client.get("/items/999")
    assert response.status_code == 404

@pytest.mark.timeout(10)
def test_performance():
    """Test response time"""
    import time
    start = time.time()
    response = client.get("/")
    duration = time.time() - start
    assert duration < 1.0  # Should respond in less than 1 second
    assert response.status_code == 200