"""add culture and variety fields to Visit"""

from alembic import op
import sqlalchemy as sa

# Revisões
revision = '97f0d2627e3c'
down_revision = '7007903180aa'
branch_labels = None
depends_on = None


def upgrade():
    # Apenas adiciona as novas colunas, sem remover ou alterar constraints
    with op.batch_alter_table('visits', schema=None) as batch_op:
        batch_op.add_column(sa.Column('culture', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('variety', sa.String(length=200), nullable=True))


def downgrade():
    # Remove as colunas se for necessário reverter
    with op.batch_alter_table('visits', schema=None) as batch_op:
        batch_op.drop_column('variety')
        batch_op.drop_column('culture')
