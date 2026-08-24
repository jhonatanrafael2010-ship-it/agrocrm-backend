"""Add products and sales tables

Revision ID: 20260824_sales
Revises: 20260527_update_users_table
Create Date: 2026-08-24

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '20260824_sales'
down_revision = '20260527_update_users'
branch_labels = None
depends_on = None


def upgrade():
    # Tabela de Produtos
    op.create_table('products',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('default_unit', sa.String(length=20), nullable=False),
        sa.Column('active', sa.Boolean(), server_default='1', nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_products_name'), 'products', ['name'], unique=False)
    op.create_index(op.f('ix_products_category'), 'products', ['category'], unique=False)

    # Tabela de Vendas
    op.create_table('sales',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('consultant_id', sa.Integer(), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=False),
        sa.Column('value', sa.Float(), nullable=True),
        sa.Column('period_type', sa.String(length=20), nullable=False),
        sa.Column('period_year', sa.String(length=10), nullable=False),
        sa.Column('sale_date', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ),
        sa.ForeignKeyConstraint(['consultant_id'], ['consultants.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sales_client_id'), 'sales', ['client_id'], unique=False)
    op.create_index(op.f('ix_sales_product_id'), 'sales', ['product_id'], unique=False)
    op.create_index(op.f('ix_sales_consultant_id'), 'sales', ['consultant_id'], unique=False)
    op.create_index(op.f('ix_sales_period_type'), 'sales', ['period_type'], unique=False)
    op.create_index(op.f('ix_sales_period_year'), 'sales', ['period_year'], unique=False)

    # Seed de produtos iniciais
    products_data = [
        # Sementes
        ('AS 1868 PRO4', 'Semente', 'Sacas'),
        ('AS 1820 PRO4', 'Semente', 'Sacas'),
        ('AS 1877 PRO4', 'Semente', 'Sacas'),
        ('AS 1838 PRO4', 'Semente', 'Sacas'),
        # Fertilizantes
        ('MAP', 'Fertilizante', 'Ton'),
        ('20-00-20', 'Fertilizante', 'Ton'),
        ('Super Simples', 'Fertilizante', 'Ton'),
        ('Super Triplo', 'Fertilizante', 'Ton'),
        ('Sulfato De Amônio', 'Fertilizante', 'Ton'),
        ('Uréia', 'Fertilizante', 'Ton'),
        # Biológicos
        ('Bioma Brady Liq.', 'Biológico', 'L'),
        ('Bioma Mais', 'Biológico', 'L'),
        ('Bioma Mais Energy', 'Biológico', 'L'),
        ('Nema Protection', 'Biológico', 'L'),
        ('Trich Protection', 'Biológico', 'L'),
        ('Bioma Phos', 'Biológico', 'L'),
        ('Bioma Hydratus', 'Biológico', 'L'),
        ('FX Protection', 'Biológico', 'L'),
        ('Vector Protection', 'Biológico', 'L'),
        ('Laphy Protection', 'Biológico', 'Kg'),
        ('Looper Protection', 'Biológico', 'Kg'),
        ('BT Protection', 'Biológico', 'L'),
        ('Protection', 'Biológico', 'Kg'),
        # Nutrição Foliar
        ('Flex Manganês SS 26', 'Nutrição Foliar', 'Kg'),
        ('Multicomoni (10-1-1)', 'Nutrição Foliar', 'L'),
        ('Manganês Ultra', 'Nutrição Foliar', 'Kg'),
        ('Magnésio Ultra', 'Nutrição Foliar', 'Kg'),
        ('Octaborato de Sódio', 'Nutrição Foliar', 'Kg'),
        ('MAP Purificado', 'Nutrição Foliar', 'Kg'),
        ('Ac. Bórico', 'Nutrição Foliar', 'Kg'),
        ('Sugar +', 'Nutrição Foliar', 'Kg'),
        ('Gold Mix', 'Nutrição Foliar', 'Kg'),
        ('New Max', 'Nutrição Foliar', 'L'),
    ]

    products_table = sa.table('products',
        sa.column('name', sa.String),
        sa.column('category', sa.String),
        sa.column('default_unit', sa.String),
        sa.column('active', sa.Boolean),
    )

    op.bulk_insert(products_table, [
        {'name': name, 'category': category, 'default_unit': unit, 'active': True}
        for name, category, unit in products_data
    ])


def downgrade():
    op.drop_index(op.f('ix_sales_period_year'), table_name='sales')
    op.drop_index(op.f('ix_sales_period_type'), table_name='sales')
    op.drop_index(op.f('ix_sales_consultant_id'), table_name='sales')
    op.drop_index(op.f('ix_sales_product_id'), table_name='sales')
    op.drop_index(op.f('ix_sales_client_id'), table_name='sales')
    op.drop_table('sales')

    op.drop_index(op.f('ix_products_category'), table_name='products')
    op.drop_index(op.f('ix_products_name'), table_name='products')
    op.drop_table('products')
