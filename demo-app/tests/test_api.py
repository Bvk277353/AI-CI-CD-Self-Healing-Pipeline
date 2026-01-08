"""
API integration tests
"""

import pytest
from fastapi.testclient import TestClient
import random
import time

from app import app

client = TestClient(app)


class TestItemAPI:
    """Test Item API endpoints"""
    
    def test_create_multiple_items(self):
        """Test creating multiple items"""
        items = [
            {"name": f"Item {i}", "value": i * 10}
            for i in range(5)
        ]
        
        for item_data in items:
            response = client.post("/items/", json=item_data)
            assert response.status_code == 200
    
    def test_item_validation(self):
        """Test item data validation"""
        # Missing required field
        response = client.post("/items/", json={"name": "Test"})
        assert response.status_code == 422
        
        # Wrong type
        response = client.post("/items/", json={"name": 123, "value": "abc"})
        assert response.status_code == 422
    
    def test_read_item_boundary(self):
        """Test reading items at boundary values"""
        # Valid item
        response = client.get("/items/1")
        assert response.status_code == 200
        
        # Boundary: item 100
        response = client.get("/items/100")
        assert response.status_code == 200
        
        # Beyond boundary
        response = client.get("/items/101")
        assert response.status_code == 404


class TestHealthEndpoints:
    """Test health and monitoring endpoints"""
    
    def test_root_endpoint_format(self):
        """Test root endpoint response format"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, dict)
        assert "status" in data
        assert "message" in data
    
    def test_health_endpoint_reliability(self):
        """Test health endpoint is always available"""
        for _ in range(10):
            response = client.get("/health")
            assert response.status_code == 200
            assert response.json()["status"] == "ok"


class TestPerformance:
    """Performance tests"""
    
    @pytest.mark.timeout(5)
    def test_concurrent_requests(self):
        """Test handling concurrent requests"""
        import concurrent.futures
        
        def make_request():
            return client.get("/")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(20)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]
        
        assert all(r.status_code == 200 for r in results)
    
    @pytest.mark.timeout(10)
    def test_response_time_consistency(self):
        """Test that response times are consistent"""
        times = []
        
        for _ in range(10):
            start = time.time()
            response = client.get("/")
            duration = time.time() - start
            times.append(duration)
            assert response.status_code == 200
        
        avg_time = sum(times) / len(times)
        assert avg_time < 0.5  # Average should be under 500ms


class TestErrorHandling:
    """Test error handling"""
    
    def test_invalid_route(self):
        """Test accessing invalid route"""
        response = client.get("/invalid/route")
        assert response.status_code == 404
    
    def test_invalid_method(self):
        """Test using invalid HTTP method"""
        response = client.delete("/items/1")
        assert response.status_code == 405


# Flaky test for demonstration
@pytest.mark.flaky(reruns=3, reruns_delay=1)
def test_sometimes_fails():
    """
    This test intentionally fails sometimes to demonstrate flaky test handling
    The self-healing pipeline should detect this and add retry logic
    """
    if random.random() < 0.3:  # 30% chance of failure
        pytest.fail("Simulated flaky test failure")
    assert True
