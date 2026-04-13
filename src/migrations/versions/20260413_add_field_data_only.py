"""add field_data only

Revision ID: add_field_data_only_20260413
Revises:
Create Date: 2026-04-13
"""

from alembic import op
import sqlalchemy as sa

revision = "add_field_data_only_20260413"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'field_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('consultant_id', sa.Integer(), nullable=True),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('property_id', sa.Integer(), nullable=True),
        sa.Column('plot_id', sa.Integer(), nullable=True),
        sa.Column('culture', sa.String(length=120), nullable=True),
        sa.Column('variety', sa.String(length=200), nullable=True),
        sa.Column('category', sa.String(length=80), nullable=False),
        sa.Column('category_extra', sa.String(length=120), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('source', sa.String(length=30), server_default='bot', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id']),
        sa.ForeignKeyConstraint(['consultant_id'], ['consultants.id']),
        sa.ForeignKeyConstraint(['plot_id'], ['plots.id']),
        sa.ForeignKeyConstraint(['property_id'], ['properties.id']),
        sa.PrimaryKeyConstraint('id')
    )

    with op.batch_alter_table('field_data', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_field_data_category'), ['category'], unique=False)
        batch_op.create_index(batch_op.f('ix_field_data_client_id'), ['client_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_field_data_consultant_id'), ['consultant_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_field_data_culture'), ['culture'], unique=False)
        batch_op.create_index(batch_op.f('ix_field_data_plot_id'), ['plot_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_field_data_property_id'), ['property_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_field_data_source'), ['source'], unique=False)
        batch_op.create_index(batch_op.f('ix_field_data_variety'), ['variety'], unique=False)


def downgrade():
    with op.batch_alter_table('field_data', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_field_data_variety'))
        batch_op.drop_index(batch_op.f('ix_field_data_source'))
        batch_op.drop_index(batch_op.f('ix_field_data_property_id'))
        batch_op.drop_index(batch_op.f('ix_field_data_plot_id'))
        batch_op.drop_index(batch_op.f('ix_field_data_culture'))
        batch_op.drop_index(batch_op.f('ix_field_data_consultant_id'))
        batch_op.drop_index(batch_op.f('ix_field_data_client_id'))
        batch_op.drop_index(batch_op.f('ix_field_data_category'))

    op.drop_table('field_data')