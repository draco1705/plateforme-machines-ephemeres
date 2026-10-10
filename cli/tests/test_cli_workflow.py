import os
import sys
from datetime import UTC, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath("api"))

from app.core.security import hash_password
from app.database import Base, get_db
from app.main import app
from app.models.machine import Machine
from app.models.user import User
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from cli.labctl.main import main

SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
for table in Base.metadata.sorted_tables:
    if table.name == 'users':
        indexes_to_keep = set()
        for idx in table.indexes:
            if idx.name not in [i.name for i in indexes_to_keep]:
                indexes_to_keep.add(idx)
        table.indexes = indexes_to_keep
    for col in table.columns:
        if col.server_default is not None:
            col.server_default = None

from sqlalchemy import event


def set_created_at(mapper, connection, target):
    if hasattr(target, "created_at") and getattr(target, "created_at", None) is None:
        target.created_at = datetime.now(UTC)

for mapper in Base.registry.mappers:
    event.listen(mapper.class_, "before_insert", set_created_at)

Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

test_client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_data():
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    if not db.query(User).filter_by(email="user@lab.local").first():
        db.add(User(email="user@lab.local", password_hash=hash_password("user12345"), role="user"))
    if not db.query(Machine).filter_by(name="kali").first():
        db.add(Machine(name="kali", image="kalilinux/kali-rolling", cpu_min=1, ram_min_mb=512, port=22, enabled=True))
    db.commit()
    db.close()
    yield
    app.dependency_overrides.pop(get_db, None)

def mock_requests_post(url, **kwargs):
    path = "/" + "/".join(url.split("/")[3:])
    headers = kwargs.get("headers", {})
    json_data = kwargs.get("json")
    data = kwargs.get("data")
    resp = test_client.post(path, json=json_data, data=data, headers=headers)
    m = MagicMock()
    m.status_code = resp.status_code
    m.json.return_value = resp.json()
    m.text = resp.text
    return m

def mock_requests_get(url, **kwargs):
    path = "/" + "/".join(url.split("/")[3:])
    headers = kwargs.get("headers", {})
    resp = test_client.get(path, headers=headers)
    m = MagicMock()
    m.status_code = resp.status_code
    m.json.return_value = resp.json()
    m.text = resp.text
    return m

def mock_requests_delete(url, **kwargs):
    path = "/" + "/".join(url.split("/")[3:])
    headers = kwargs.get("headers", {})
    resp = test_client.delete(path, headers=headers)
    m = MagicMock()
    m.status_code = resp.status_code
    m.text = resp.text
    return m

def test_cli_full_lifecycle(tmp_path, monkeypatch):
    token_file = str(tmp_path / ".labhacker_token")
    monkeypatch.setattr("cli.labctl.main.TOKEN_FILE", token_file)

    with patch("requests.post", side_effect=mock_requests_post), \
         patch("requests.get", side_effect=mock_requests_get), \
         patch("requests.delete", side_effect=mock_requests_delete):

        # 1. Login
        sys.argv = ["labctl", "login", "user@lab.local", "user12345"]
        main()
        assert os.path.exists(token_file)

        # 2. List machines
        sys.argv = ["labctl", "machines"]
        main()

        # 3. Create machine template
        sys.argv = ["labctl", "create-machine", "--name", "debian-custom", "--image", "debian:12", "--cpu", "1", "--ram", "512", "--port", "80"]
        main()

        # 4. Reserve using machine name (kali)
        sys.argv = ["labctl", "reserve", "--machine", "kali", "--cpu", "1", "--ram", "512", "--duration", "30"]
        main()

        # 5. List reservations
        sys.argv = ["labctl", "list"]
        main()

        # 6. Status of reservation 1
        sys.argv = ["labctl", "status", "1"]
        main()

        # 7. Delete reservation 1
        sys.argv = ["labctl", "delete", "1"]
        main()

        # 8. Logout
        sys.argv = ["labctl", "logout"]
        main()
        assert not os.path.exists(token_file)
