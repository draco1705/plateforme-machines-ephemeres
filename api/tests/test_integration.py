import sys
import os
import datetime
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import Base, get_db
from app.models.worker import Worker
from app.models.machine import Machine
from app.models.user import User
from app.models.reservation import Reservation
from app.models.reservation_event import ReservationEvent

SQLALCHEMY_DATABASE_URL = 'sqlite:///:memory:'
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={'check_same_thread': False},
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

def set_created_at(mapper, connection, target):
    if hasattr(target, 'created_at') and getattr(target, 'created_at') is None:
        target.created_at = datetime.datetime.now(datetime.timezone.utc)

for mapper in Base.registry.mappers:
    event.listen(mapper.class_, 'before_insert', set_created_at)

Base.metadata.create_all(bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

def setup_db():
    db = TestingSessionLocal()
    w = Worker(name='worker_test', ip='10.0.0.99', cpu_total=8, ram_total_mb=8192, cpu_used=0, ram_used_mb=0, max_containers=20, container_count=0, status='AVAILABLE')
    db.add(w)
    m = Machine(name='ubuntu', image='ubuntu:latest', cpu_min=1, ram_min_mb=512, port=22, enabled=True)
    db.add(m)
    db.commit()
    db.close()

def test_integration():
    setup_db()
    print('Testing API integration with Resource Manager & DB...')
    
    print('Registering user...')
    response = client.post('/users', json={'email': 'user@test.com', 'password': 'password123'})
    assert response.status_code in [200, 201], response.text
    
    print('Logging in user...')
    response = client.post('/users/login', data={'username': 'user@test.com', 'password': 'password123'})
    assert response.status_code in [200, 201], response.text
    token = response.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}
    
    print('Fetching machines...')
    response = client.get('/machines', headers=headers)
    assert response.status_code in [200, 201], response.text
    machines = response.json()
    assert len(machines) > 0
    machine_id = machines[0]['id']
    
    print('Creating reservation...')
    res_data = {'machine_id': machine_id, 'duration_minutes': 60, 'cpu': 2, 'ram_mb': 1024}
    response = client.post('/reservations', json=res_data, headers=headers)
    assert response.status_code in [200, 201], response.text
    reservation = response.json()
    assert reservation['status'] == 'PENDING'
    print('Reservation created successfully:', reservation['id'])
    
    print('ALL INTEGRATION TESTS PASSED: Tasks 1-12 properly connect to Tasks 9-13!')

if __name__ == '__main__':
    test_integration()
