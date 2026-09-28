"""move worker capacity to resources"""
revision = 'c8a1131043aa'
down_revision = 'b30834eec83e'
branch_labels = None
depends_on = None
from alembic import op
import sqlalchemy as sa
import uuid

def upgrade():
    bind = op.get_bind()
    metadata = sa.MetaData()
    workers = sa.Table('workers', metadata, autoload_with=bind)
    resources = sa.Table('resources', metadata, autoload_with=bind)
    existing = {
        (row.worker_id, getattr(row.resource_type, 'value', row.resource_type))
        for row in bind.execute(sa.select(resources.c.worker_id, resources.c.resource_type))
    }
    resource_columns = (
        ('CPU', 'total_cpu'),
        ('RAM_MB', 'total_ram_mb'),
        ('CONTAINER_SLOT', 'max_containers'),
    )
    for worker in bind.execute(sa.select(workers)):
        for resource_type, column_name in resource_columns:
            if (worker.id, resource_type) not in existing:
                bind.execute(resources.insert().values(
                    id=str(uuid.uuid4()) if bind.dialect.name == 'sqlite' else uuid.uuid4(), worker_id=worker.id,
                    resource_type=resource_type,
                    total_capacity=getattr(worker, column_name),
                    allocated_capacity=0, status='AVAILABLE',
                ))
    op.drop_column('workers', 'total_ram_mb')
    op.drop_column('workers', 'max_containers')
    op.drop_column('workers', 'total_cpu')

def downgrade():
    op.add_column('workers', sa.Column('total_cpu', sa.INTEGER(), nullable=False, server_default='0'))
    op.add_column('workers', sa.Column('max_containers', sa.INTEGER(), nullable=False, server_default='0'))
    op.add_column('workers', sa.Column('total_ram_mb', sa.INTEGER(), nullable=False, server_default='0'))
    bind = op.get_bind()
    metadata = sa.MetaData()
    workers = sa.Table('workers', metadata, autoload_with=bind)
    resources = sa.Table('resources', metadata, autoload_with=bind)
    column_for_type = {'CPU': 'total_cpu', 'RAM_MB': 'total_ram_mb', 'CONTAINER_SLOT': 'max_containers'}
    for resource in bind.execute(sa.select(resources)):
        resource_type = getattr(resource.resource_type, 'value', resource.resource_type)
        if resource_type in column_for_type:
            bind.execute(workers.update().where(workers.c.id == resource.worker_id).values(
                **{column_for_type[resource_type]: resource.total_capacity}
            ))
