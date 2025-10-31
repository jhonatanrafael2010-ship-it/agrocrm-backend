"""merge latitude migration heads

Revision ID: 9182649f4e64
Revises: 9ee7ef52969d, manual_add_lat_long_visit
Create Date: 2025-10-31 10:35:33.747273

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9182649f4e64'
down_revision = ('9ee7ef52969d', 'manual_add_lat_long_visit')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
