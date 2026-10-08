"""Adiciona client_id na tabela plantings para suportar ciclos sem talhão.

Revision ID: 20261008_planting_client
Revises: 20260918_seeds
Create Date: 2026-10-08
"""
from alembic import op
import sqlalchemy as sa


revision = '20261008_planting_client'
down_revision = '20260918_seeds'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('plantings', sa.Column('client_id', sa.Integer, nullable=True))
    op.create_index('ix_plantings_client_id', 'plantings', ['client_id'])
    op.create_foreign_key('fk_plantings_client_id', 'plantings', 'clients', ['client_id'], ['id'])


def downgrade():
    op.drop_constraint('fk_plantings_client_id', 'plantings', type_='foreignkey')
    op.drop_index('ix_plantings_client_id', 'plantings')
    op.drop_column('plantings', 'client_id')
