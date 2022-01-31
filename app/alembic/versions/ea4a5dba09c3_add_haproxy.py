"""add haproxy

Revision ID: ea4a5dba09c3
Revises: af5c2cb0d36b
Create Date: 2022-01-30 17:08:01.575581

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ea4a5dba09c3'
down_revision = 'af5c2cb0d36b'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE methodenum ADD VALUE IF NOT EXISTS 'HAPROXY'")


def downgrade():
    pass
