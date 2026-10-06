import sys
import os
import datetime

sys.path.insert(0, os.path.abspath('api'))

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
    # Add admin user as well for admin tests
    admin_user = User(email='admin@lab.local', password_hash='$2b$12$EixZaYVK1fsbw1ZfbX3OXePaWxn96p36WQoeG6Lruj3vjPGga31lW', role='admin')
    db.add(admin_user)
    w = Worker(name='worker_test', ip='10.0.0.99', cpu_total=8, ram_total_mb=8192, cpu_used=0, ram_used_mb=0, max_containers=20, container_count=0, status='AVAILABLE')
    db.add(w)
    m = Machine(name='ubuntu', image='ubuntu:latest', cpu_min=1, ram_min_mb=512, port=22, enabled=True)
    db.add(m)
    db.commit()
    db.close()

def test_health():
    response = client.get('/health')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'
    assert data['checks']['database'] == 'ok'
    print('Health check passed.')

def test_register_and_login():
    # Test Register
    reg_payload = {'email': 'user@test.com', 'password': 'password123'}
    response = client.post('/users', json=reg_payload)
    assert response.status_code in [200, 201], response.text
    data = response.json()
    assert data['email'] == reg_payload['email']
    print('Register test passed.')

    # Test Login
    login_data = {'username': 'user@test.com', 'password': 'password123'}
    response = client.post('/users/login', data=login_data)
    assert response.status_code in [200, 201], response.text
    token_data = response.json()
    assert 'access_token' in token_data
    print('Login test passed.')
    return token_data['access_token']

def test_instances_machines():
    login_data = {'username': 'admin@lab.local', 'password': 'admin12345'}
    # Login admin
    resp = client.post('/users/login', data=login_data)
    if resp.status_code != 200:
        # Create admin user if not exists via DB or registration
        db = TestingSessionLocal()
        if not db.query(User).filter_by(email='admin@lab.local').first():
            from app.core.security import hash_password
            db.add(User(email='admin@lab.local', password_hash=hash_password('admin12345'), role='admin'))
            db.commit()
        db.close()
        resp = client.post('/users/login', data=login_data)
    
    token = resp.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    # List machines
    response = client.get('/machines', headers=headers)
    assert response.status_code == 200
    machines = response.json()
    assert len(machines) > 0
    print('Instance/Machine test passed.')

def test_worker():
    # Register worker
    worker_payload = {
        'id': 'worker-1',
        'name': 'worker-1',
        'ip': '192.168.56.11',
        'cpu_total': 4,
        'ram_total_mb': 4096,
        'max_containers': 10
    }
    response = client.post('/workers/register', json=worker_payload)
    assert response.status_code in [200, 201], response.text
    
    # Heartbeat
    heartbeat_payload = {
        'name': 'worker-1',
        'cpu_used': 2,
        'ram_used_mb': 1024
    }
    response = client.post('/workers/heartbeat', json=heartbeat_payload)
    assert response.status_code in [200, 204], response.text
    print('Worker test passed.')

def test_reservation():
    # Register & Login user
    reg_payload = {'email': 'res_user@test.com', 'password': 'password123'}
    client.post('/users', json=reg_payload)
    resp = client.post('/users/login', data={'username': 'res_user@test.com', 'password': 'password123'})
    token = resp.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    # Get machines
    m_resp = client.get('/machines', headers=headers)
    machines = m_resp.json()
    machine_id = machines[0]['id']

    # Create reservation
    res_data = {'machine_id': machine_id, 'duration_minutes': 60, 'cpu': 1, 'ram_mb': 512}
    response = client.post('/reservations', json=res_data, headers=headers)
    assert response.status_code in [200, 201], response.text
    reservation = response.json()
    assert reservation['status'] == 'PENDING'
    
    rid = reservation['id']
    # Cancel reservation
    del_resp = client.delete(f'/reservations/{rid}', headers=headers)
    assert del_resp.status_code in [200, 204], del_resp.text
    print('Reservation test passed.')

def run_all():
    setup_db()
    print('Running complete API test suite...')
    test_health()
    test_register_and_login()
    test_instances_machines()
    test_worker()
    test_reservation()
    print('ALL API TESTS PASSED SUCCESSFULLY!')

if __name__ == '__main__':
    run_all()
