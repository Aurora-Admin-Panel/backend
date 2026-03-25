"""add realm

Revision ID: af5c2cb0d36b
Revises: 154b3bb64ffa
Create Date: 2022-01-09 21:49:52.670053

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'af5c2cb0d36b'
down_revision = '154b3bb64ffa'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TYPE methodenum ADD VALUE IF NOT EXISTS 'REALM'")


def downgrade():
    pass
