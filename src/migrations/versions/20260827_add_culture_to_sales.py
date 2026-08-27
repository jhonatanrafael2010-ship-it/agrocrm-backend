"""Add culture column to sales table

Revision ID: 20260827_culture
Revises: 20260824_sales
Create Date: 2026-08-27

"""
from alembic import op
import sqlalchemy as sa


revision = '20260827_culture'
down_revision = '20260824_sales'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('sales', sa.Column('culture', sa.String(length=50), nullable=True))
    op.create_index(op.f('ix_sales_culture'), 'sales', ['culture'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_sales_culture'), table_name='sales')
    op.drop_column('sales', 'culture')
