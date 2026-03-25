"""Add timescaledb extension

Revision ID: fe1c7deaaef2
Revises: ee7c03c63dfa
Create Date: 2025-08-26 21:46:31.276297

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "fe1c7deaaef2"
down_revision = "ee7c03c63dfa"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute("CREATE EXTENSION IF NOT EXISTS timescaledb;")


def downgrade():
    conn = op.get_bind()
    conn.execute("DROP EXTENSION IF EXISTS timescaledb;")
