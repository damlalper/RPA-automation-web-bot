"""Integration tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.database.connection import init_db, get_engine
from src.database.models import Base


@pytest.fixture(scope="module")
def client():
    """Create test client with test database."""
    # Use in-memory SQLite for tests
    import os
    os.environ["DATABASE_URL"] = "sqlite:///./test_data/test.db"

    # Create tables
    init_db()

    with TestClient(app) as c:
        yield c

    # Cleanup
    engine = get_engine()
    Base.metadata.drop_all(bind=engine)


class TestHealthEndpoints:
    """Tests for health endpoints."""

    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "timestamp" in data
        assert "components" in data

    def test_liveness_probe(self, client):
        """Test liveness probe."""
        response = client.get("/api/health/live")

        assert response.status_code == 200
        assert response.json()["status"] == "alive"

    def test_readiness_probe(self, client):
        """Test readiness probe."""
        response = client.get("/api/health/ready")

        assert response.status_code == 200
        assert response.json()["status"] == "ready"

    def test_system_info(self, client):
        """Test system info endpoint."""
        response = client.get("/api/info")

        assert response.status_code == 200
        data = response.json()
        assert "app_name" in data
        assert "version" in data


class TestTaskEndpoints:
    """Tests for task endpoints."""

    def test_create_task(self, client):
        """Test creating a task."""
        task_data = {
            "name": "Test Task",
            "target_url": "https://example.com",
            "task_type": "scrape",
            "priority": 5,
        }

        response = client.post("/api/tasks", json=task_data)

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Test Task"
        assert data["target_url"] == "https://example.com"
        assert data["status"] == "pending"
        assert data["priority"] == 5

    def test_list_tasks(self, client):
        """Test listing tasks."""
        response = client.get("/api/tasks")

        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "total" in data
        assert "page" in data

    def test_get_task(self, client):
        """Test getting a specific task."""
        # First create a task
        task_data = {
            "name": "Get Test",
            "target_url": "https://example.com",
        }
        create_response = client.post("/api/tasks", json=task_data)
        task_id = create_response.json()["id"]

        # Get the task
        response = client.get(f"/api/tasks/{task_id}")

        assert response.status_code == 200
        assert response.json()["id"] == task_id

    def test_get_nonexistent_task(self, client):
        """Test getting non-existent task."""
        response = client.get("/api/tasks/nonexistent-id")

        assert response.status_code == 404

    def test_update_task(self, client):
        """Test updating a task."""
        # Create task
        task_data = {
            "name": "Update Test",
            "target_url": "https://example.com",
        }
        create_response = client.post("/api/tasks", json=task_data)
        task_id = create_response.json()["id"]

        # Update task
        update_data = {"priority": 10}
        response = client.put(f"/api/tasks/{task_id}", json=update_data)

        assert response.status_code == 200
        assert response.json()["priority"] == 10

    def test_cancel_task(self, client):
        """Test cancelling a task."""
        # Create task
        task_data = {
            "name": "Cancel Test",
            "target_url": "https://example.com",
        }
        create_response = client.post("/api/tasks", json=task_data)
        task_id = create_response.json()["id"]

        # Cancel task
        response = client.post(f"/api/tasks/{task_id}/cancel")

        assert response.status_code == 200
        assert response.json()["status"] == "cancelled"

    def test_delete_task(self, client):
        """Test deleting a task."""
        # Create task
        task_data = {
            "name": "Delete Test",
            "target_url": "https://example.com",
        }
        create_response = client.post("/api/tasks", json=task_data)
        task_id = create_response.json()["id"]

        # Delete task
        response = client.delete(f"/api/tasks/{task_id}")

        assert response.status_code == 204

        # Verify deleted
        get_response = client.get(f"/api/tasks/{task_id}")
        assert get_response.status_code == 404

    def test_task_stats(self, client):
        """Test task statistics endpoint."""
        response = client.get("/api/tasks/stats")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "by_status" in data
        assert "success_rate" in data


class TestMetricsEndpoints:
    """Tests for metrics endpoints."""

    def test_metrics_summary(self, client):
        """Test metrics summary endpoint."""
        response = client.get("/api/metrics/summary")

        assert response.status_code == 200
        data = response.json()
        assert "tasks" in data
        assert "proxies" in data
        assert "performance" in data

    def test_proxy_metrics(self, client):
        """Test proxy metrics endpoint."""
        response = client.get("/api/metrics/proxies")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "healthy" in data

    def test_proxy_list(self, client):
        """Test proxy list endpoint."""
        response = client.get("/api/metrics/proxies/list")

        assert response.status_code == 200
        data = response.json()
        assert "proxies" in data
        assert "count" in data
