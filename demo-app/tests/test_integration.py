"""
Integration tests
"""

import pytest
from fastapi.testclient import TestClient

from app import app

client = TestClient(app)


@pytest.fixture
def sample_items():
    """Fixture to create sample items"""
    items = []
    for i in range(3):
        response = client.post("/items/", json={
            "name": f"Sample Item {i}",
            "value": i * 100
        })
        items.append(response.json())
    return items


class TestIntegration:
    """Integration tests"""
    
    def test_full_item_lifecycle(self):
        """Test complete item creation and retrieval"""
        # Create
        create_response = client.post("/items/", json={
            "name": "Integration Test Item",
            "value": 999
        })
        assert create_response.status_code == 200
        created_item = create_response.json()
        
        # Read
        item_id = created_item["id"]
        read_response = client.get(f"/items/{item_id}")
        assert read_response.status_code == 200
        read_item = read_response.json()
        assert read_item["id"] == item_id
    
    def test_api_workflow(self, sample_items):
        """Test typical API workflow"""
        # Verify items were created
        assert len(sample_items) == 3
        
        # Retrieve each item
        for item in sample_items:
            response = client.get(f"/items/{item['id']}")
            assert response.status_code == 200
    
    def test_health_after_operations(self, sample_items):
        """Test that health remains good after operations"""
        # Perform various operations
        for _ in range(5):
            client.post("/items/", json={"name": "Test", "value": 1})
        
        # Check health
        health_response = client.get("/health")
        assert health_response.status_code == 200
        assert health_response.json()["status"] == "ok"


@pytest.mark.slow
class TestStressTests:
    """Stress tests (marked as slow)"""
    
    @pytest.mark.timeout(30)
    def test_many_requests(self):
        """Test handling many sequential requests"""
        for i in range(100):
            response = client.post("/items/", json={
                "name": f"Stress Test Item {i}",
                "value": i
            })
            assert response.status_code == 200
    
    @pytest.mark.timeout(20)
    def test_large_payload(self):
        """Test handling large payloads"""
        large_name = "A" * 1000
        response = client.post("/items/", json={
            "name": large_name,
            "value": 42
        })
        assert response.status_code == 200


# Configuration for pytest
def pytest_configure(config):
    """Pytest configuration"""
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "flaky: marks tests as flaky"
    )