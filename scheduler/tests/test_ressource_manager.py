import os
import sys

os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

sys.path.insert(0, os.path.abspath('scheduler'))

from app.database import Base
from app.models.worker import Worker
from app.services.ressource_manager import RessourceError, RessourceManager

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

Base.metadata.create_all(bind=engine)

@pytest.fixture(autouse=True)
def setup_db():
    yield

def test_resource_manager_allocation_and_release():
    db = TestingSessionLocal()
    
    # 1. Add a worker
    worker = Worker(
        id=1,
        name='worker-test',
        ip='192.168.1.50',
        cpu_total=4,
        ram_total_mb=4096,
        cpu_used=0,
        ram_used_mb=0,
        max_containers=2,
        container_count=0,
        status='AVAILABLE'
    )
    db.add(worker)
    db.commit()

    manager = RessourceManager(db)

    # 2. Select worker & reserve resources
    selected = manager.select_worker(cpu=2, ram_mb=2048)
    assert selected is not None
    assert selected.id == 1

    updated_worker = manager.reserve(cpu=2, ram_mb=2048, worker_id=selected.id)
    assert updated_worker.cpu_used == 2
    assert updated_worker.ram_used_mb == 2048
    assert updated_worker.container_count == 1
    assert updated_worker.status == 'AVAILABLE'

    # 3. Reserve remaining capacity to trigger BUSY status
    updated_worker2 = manager.reserve(cpu=2, ram_mb=2048, worker_id=selected.id)
    assert updated_worker2.cpu_used == 4
    assert updated_worker2.ram_used_mb == 4096
    assert updated_worker2.container_count == 2
    assert updated_worker2.status == 'BUSY'

    # 4. Try reserving when full (should raise error)
    with pytest.raises(Exception):  # noqa: B017
        manager.reserve(cpu=1, ram_mb=512, worker_id=selected.id)

    # 5. Release resources
    released_worker = manager.release(worker_id=selected.id, cpu=2, ram_mb=2048)
    assert released_worker.cpu_used == 2
    assert released_worker.ram_used_mb == 2048
    assert released_worker.container_count == 1
    assert released_worker.status == 'AVAILABLE'

    db.close()
    print("Resource Manager tests passed successfully.")
