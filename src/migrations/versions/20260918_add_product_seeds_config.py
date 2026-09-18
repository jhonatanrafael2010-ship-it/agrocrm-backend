"""Adiciona culture e seeds_per_ha na tabela products para calcular oportunidades de soja.

Revision ID: 20260918_seeds
Revises: 20260827_culture
Create Date: 2026-09-18
"""
from alembic import op
import sqlalchemy as sa


revision = '20260918_seeds'
down_revision = '20260827_culture'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('products', sa.Column('culture', sa.String(50), nullable=True))
    op.add_column('products', sa.Column('seeds_per_ha', sa.Integer, nullable=True))
    op.create_index('ix_products_culture', 'products', ['culture'])


def downgrade():
    op.drop_index('ix_products_culture', 'products')
    op.drop_column('products', 'seeds_per_ha')
    op.drop_column('products', 'culture')
