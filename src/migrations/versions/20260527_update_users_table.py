"""Update users table for login system

Revision ID: 20260527_update_users
Revises: 20260506_visit_purpose
Create Date: 2026-05-27
"""
from alembic import op
import sqlalchemy as sa


revision = '20260527_update_users'
down_revision = '20260506_visit_purpose'
branch_labels = None
depends_on = None


def upgrade():
    # Verifica se a tabela users existe
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    tables = inspector.get_table_names()

    if 'users' not in tables:
        # Cria tabela users do zero
        op.create_table(
            'users',
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('username', sa.String(50), unique=True, nullable=False, index=True),
            sa.Column('password_hash', sa.String(255), nullable=False),
            sa.Column('consultant_id', sa.Integer, sa.ForeignKey('consultants.id'), nullable=True),
            sa.Column('is_admin', sa.Boolean, default=False, nullable=False),
            sa.Column('active', sa.Boolean, default=True, nullable=False),
            sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=False),
        )
    else:
        # Tabela existe, adiciona novas colunas
        columns = [c['name'] for c in inspector.get_columns('users')]

        if 'username' not in columns:
            op.add_column('users', sa.Column('username', sa.String(50), nullable=True))

        if 'consultant_id' not in columns:
            op.add_column('users', sa.Column('consultant_id', sa.Integer, nullable=True))

        if 'is_admin' not in columns:
            op.add_column('users', sa.Column('is_admin', sa.Boolean, server_default='0', nullable=False))

        if 'active' not in columns:
            op.add_column('users', sa.Column('active', sa.Boolean, server_default='1', nullable=False))

        if 'created_at' not in columns:
            op.add_column('users', sa.Column('created_at', sa.DateTime, server_default=sa.func.now(), nullable=True))

        # Torna email nullable (para permitir novos usuários sem email)
        if 'email' in columns:
            op.alter_column('users', 'email', nullable=True)

        # Tenta criar índice em username se não existir
        try:
            op.create_index('ix_users_username', 'users', ['username'], unique=True)
        except Exception:
            pass  # Índice já existe


def downgrade():
    # Remove colunas adicionadas
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    if 'users' in inspector.get_table_names():
        columns = [c['name'] for c in inspector.get_columns('users')]

        if 'consultant_id' in columns:
            op.drop_column('users', 'consultant_id')
        if 'is_admin' in columns:
            op.drop_column('users', 'is_admin')
        if 'active' in columns:
            op.drop_column('users', 'active')
