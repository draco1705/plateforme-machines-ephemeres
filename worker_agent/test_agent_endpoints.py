import pytest
from fastapi.testclient import TestClient
from worker_agent.agent import app

client = TestClient(app)

def test_agent_root():
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "worker" in data
    assert "ip" in data
    assert "port" in data

def test_agent_health():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "docker" in data

def test_agent_status():
    response = client.get("/status")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert "cpu_total" in data
    assert "ram_total_mb" in data
    assert "max_containers" in data

def test_container_validation():
    # Invalid CPU
    payload = {
        "reservation_id": 1,
        "image": "alpine:latest",
        "cpu": 0,
        "ram_mb": 512
    }
    response = client.post("/containers", json=payload)
    assert response.status_code == 422
