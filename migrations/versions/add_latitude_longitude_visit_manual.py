"""add latitude and longitude columns to Visit safely"""

from alembic import op
import sqlalchemy as sa

# Revisão
revision = "manual_add_lat_long_visit"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # 🧭 adiciona latitude e longitude somente se não existirem
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    columns = [col["name"] for col in inspector.get_columns("visits")]

    if "latitude" not in columns:
        with op.batch_alter_table("visits", schema=None) as batch_op:
            batch_op.add_column(sa.Column("latitude", sa.Float(), nullable=True))
            print("✅ Coluna latitude adicionada em visits")

    if "longitude" not in columns:
        with op.batch_alter_table("visits", schema=None) as batch_op:
            batch_op.add_column(sa.Column("longitude", sa.Float(), nullable=True))
            print("✅ Coluna longitude adicionada em visits")


def downgrade():
    # 🔙 remove colunas caso precise reverter
    with op.batch_alter_table("visits", schema=None) as batch_op:
        batch_op.drop_column("latitude")
        batch_op.drop_column("longitude")
