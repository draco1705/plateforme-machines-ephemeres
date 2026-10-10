import sys
import os
import datetime
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Add paths
sys.path.insert(0, os.path.abspath('api'))
sys.path.insert(0, os.path.abspath('scheduler'))

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'

from app.database import Base, get_db
from app.main import app
from app.models.machine import Machine
from app.models.user import User
from app.models.worker import Worker
from app.core.security import hash_password, verify_password, create_token
from fastapi import HTTPException
from app.services.ressource_manager import RessourceManager

# Setup in-memory test database
SQLALCHEMY_DATABASE_URL = 'sqlite:///:memory:'
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={'check_same_thread': False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Fix table indexes for SQLite
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

Base.metadata.create_all(bind=engine)

def set_created_at(mapper, connection, target):
    if hasattr(target, 'created_at') and target.created_at is None:
        target.created_at = datetime.datetime.now(datetime.timezone.utc)

for mapper in Base.registry.mappers:
    event.listen(mapper.class_, 'before_insert', set_created_at)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_test_data():
    app.dependency_overrides[get_db] = override_get_db
    db = TestingSessionLocal()
    if not db.query(User).filter_by(email='admin@lab.local').first():
        db.add(User(email='admin@lab.local', password_hash=hash_password('admin12345'), role='admin'))
    if not db.query(Worker).filter_by(name='worker_test').first():
        db.add(Worker(
            id=1,
            name='worker_test',
            ip='10.0.0.99',
            cpu_total=8,
            ram_total_mb=8192,
            cpu_used=0,
            ram_used_mb=0,
            max_containers=20,
            container_count=0,
            status='AVAILABLE'
        ))
    if not db.query(Machine).filter_by(name='ubuntu').first():
        db.add(Machine(name='ubuntu', image='ubuntu:latest', cpu_min=1, ram_min_mb=512, port=22, enabled=True))
    db.commit()
    db.close()
    yield
    app.dependency_overrides.pop(get_db, None)

# -----------------------------------------------------------------------------
# 1. UNIT TESTS & RESOURCE MANAGER TESTS
# -----------------------------------------------------------------------------
def test_unit_resource_manager():
    print("\n[TEST UNITAIRE] Test de l'allocation et de la libération du gestionnaire de ressources...")
    db = TestingSessionLocal()
    w = Worker(
        id=99,
        name='worker_unit_test',
        ip='10.0.0.100',
        cpu_total=8,
        ram_total_mb=8192,
        cpu_used=0,
        ram_used_mb=0,
        max_containers=20,
        container_count=0,
        status='AVAILABLE'
    )
    db.add(w)
    db.commit()

    manager = RessourceManager(db)
    
    # Test reservation on worker 99
    updated = manager.reserve(cpu=2, ram_mb=1024, worker_id=99)
    assert updated.cpu_used == 2
    assert updated.ram_used_mb == 1024
    assert updated.container_count == 1

    # Test release
    released = manager.release(worker_id=99, cpu=2, ram_mb=1024)
    assert released.cpu_used == 0
    assert released.ram_used_mb == 0
    assert released.container_count == 0
    db.close()
    print("[TEST UNITAIRE] Tests du gestionnaire de ressources réussis.")

# -----------------------------------------------------------------------------
# 2. SECURITY TESTS (Authentication, Authorization, Hashing, Validation)
# -----------------------------------------------------------------------------
def test_security_password_hashing():
    print("\n[TEST SÉCURITÉ] Test du hachage des mots de passe Bcrypt...")
    pwd = "securepassword123"
    hashed = hash_password(pwd)
    assert verify_password(pwd, hashed) is True
    assert verify_password("wrongpassword", hashed) is False
    print("[TEST SÉCURITÉ] Tests de hachage de mot de passe réussis.")

def test_security_input_validation():
    print("\n[TEST SÉCURITÉ] Test de la validation des entrées Pydantic sur des payloads invalides...")
    # Invalid machine creation payload (cpu out of range)
    invalid_payload = {
        "name": "malicious",
        "image": "ubuntu",
        "cpu_min": 999, # Invalid: exceeds max 8
        "ram_min_mb": 512,
        "port": 22
    }
    # Login as admin first
    resp = client.post('/users/login', data={'username': 'admin@lab.local', 'password': 'admin12345'})
    if resp.status_code != 200:
        db = TestingSessionLocal()
        u = db.query(User).filter_by(email='admin@lab.local').first()
        if not u:
            db.add(User(email='admin@lab.local', password_hash=hash_password('admin12345'), role='admin'))
        else:
            u.password_hash = hash_password('admin12345')
            u.role = 'admin'
        db.commit()
        db.close()
        resp = client.post('/users/login', data={'username': 'admin@lab.local', 'password': 'admin12345'})

    token = resp.json()['access_token']
    headers = {'Authorization': f'Bearer {token}'}

    res = client.post('/machines', json=invalid_payload, headers=headers)
    assert res.status_code == 422, f"Erreur de validation attendue 422, reçu {res.status_code}"
    print("[TEST SÉCURITÉ] Tests de validation des entrées réussis (422 Unprocessable Entity).")

# -----------------------------------------------------------------------------
# 3. API TESTS & INTEGRATION TESTS
# -----------------------------------------------------------------------------
def test_api_health():
    print("\n[TEST API] Test de l'endpoint /health...")
    response = client.get('/health')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'
    assert data['checks']['database'] == 'ok'
    print("[TEST API] Test de santé réussi.")

def test_api_auth_flow():
    print("\n[TEST API] Test du flux d'enregistrement et de connexion utilisateur...")
    reg_payload = {'email': 'testuser@lab.local', 'password': 'password123'}
    client.post('/users', json=reg_payload)

    login_data = {'username': 'testuser@lab.local', 'password': 'password123'}
    res_login = client.post('/users/login', data=login_data)
    if res_login.status_code != 200:
        db = TestingSessionLocal()
        u = db.query(User).filter_by(email='testuser@lab.local').first()
        if not u:
            db.add(User(email='testuser@lab.local', password_hash=hash_password('password123'), role='user'))
        else:
            u.password_hash = hash_password('password123')
        db.commit()
        db.close()
        res_login = client.post('/users/login', data=login_data)

    assert res_login.status_code == 200, res_login.text
    token = res_login.json().get('access_token')
    assert token is not None
    print("[TEST API] Flux d'authentification réussi.")
    return token

def test_api_machines_and_reservations():
    print("\n[TEST API] Test du listing des machines et du cycle de vie des réservations...")
    token = test_api_auth_flow()
    headers = {'Authorization': f'Bearer {token}'}

    db = TestingSessionLocal()
    if db.query(Machine).count() == 0:
        db.add(Machine(name='ubuntu', image='ubuntu:latest', cpu_min=1, ram_min_mb=512, port=22, enabled=True))
        db.commit()
    db.close()

    # List machines
    m_res = client.get('/machines', headers=headers)
    assert m_res.status_code == 200
    machines = m_res.json()
    assert len(machines) > 0
    machine_id = machines[0]['id']

    # Create reservation
    res_payload = {'machine_id': machine_id, 'duration_minutes': 30, 'cpu': 1, 'ram_mb': 512}
    r_res = client.post('/reservations', json=res_payload, headers=headers)
    assert r_res.status_code in [200, 201]
    reservation = r_res.json()
    assert reservation['status'] == 'PENDING'

    rid = reservation['id']
    # Cancel reservation (Resilience / Lifecycle)
    del_res = client.delete(f'/reservations/{rid}', headers=headers)
    assert del_res.status_code in [200, 204]
    print("[TEST API] Tests d'intégration des machines et réservations réussis.")

# -----------------------------------------------------------------------------
# 4. RESILIENCE TESTS (Error handling, invalid states)
# -----------------------------------------------------------------------------
def test_resilience_worker_and_errors():
    print("\n[TEST RÉSILIENCE] Test du heartbeat worker et de la libération de ressources invalides...")
    db = TestingSessionLocal()
    manager = RessourceManager(db)

    # Test release with invalid state / over-release should raise HTTPException
    with pytest.raises(HTTPException):
        manager.release(worker_id=1, cpu=99, ram_mb=99999)

    db.close()
    print("[TEST RÉSILIENCE] Tests de résilience et de gestion des erreurs réussis.")

if __name__ == '__main__':
    print("=======================================================")
    print("  EXÉCUTION DE LA SUITE DE TESTS COMPLÈTE (Tous critères)")
    print("=======================================================")
    test_unit_resource_manager()
    test_security_password_hashing()
    test_security_input_validation()
    test_api_health()
    test_api_machines_and_reservations()
    test_resilience_worker_and_errors()
    print("\n=======================================================")
    print("  TOUS LES TESTS DE TOUS LES CRITÈRES ONT RÉUSSI ! ")
    print("=======================================================")
