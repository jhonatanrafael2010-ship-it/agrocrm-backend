"""add region to clients

Revision ID: add_client_region_20260425
Revises: add_agent_decision_log_20260417
Create Date: 2026-04-25
"""

from alembic import op
import sqlalchemy as sa


revision = "add_client_region_20260425"
down_revision = "add_agent_decision_log_20260417"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("clients", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("region", sa.String(length=100), nullable=True)
        )
        batch_op.create_index(
            batch_op.f("ix_clients_region"),
            ["region"],
            unique=False,
        )


def downgrade():
    with op.batch_alter_table("clients", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_clients_region"))
        batch_op.drop_column("region")
