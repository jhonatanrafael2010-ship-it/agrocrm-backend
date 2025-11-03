"""add latitude and longitude columns to visits table"""

from alembic import op
import sqlalchemy as sa

# Revisões
revision = 'add_lat_lon_visits'
down_revision = None  # 👈 primeira migração, não há anterior
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('visits', schema=None) as batch_op:
        batch_op.add_column(sa.Column('latitude', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('longitude', sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('visits', schema=None) as batch_op:
        batch_op.drop_column('longitude')
        batch_op.drop_column('latitude')
