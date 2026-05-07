"""Add visit_purpose column to visits table

Revision ID: 20260506_visit_purpose
Revises: add_client_region_20260425
Create Date: 2026-05-06
"""
from alembic import op
import sqlalchemy as sa


revision = '20260506_visit_purpose'
down_revision = 'add_client_region_20260425'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('visits', sa.Column('visit_purpose', sa.String(50), nullable=True))


def downgrade():
    op.drop_column('visits', 'visit_purpose')
