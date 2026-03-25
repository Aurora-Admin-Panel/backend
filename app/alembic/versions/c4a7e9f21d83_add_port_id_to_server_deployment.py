"""add port_id to server_deployment

Revision ID: c4a7e9f21d83
Revises: 38fd48957fee
Create Date: 2026-03-08 22:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "c4a7e9f21d83"
down_revision = "38fd48957fee"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add port_id column (nullable FK to port.id)
    op.add_column(
        "server_deployment",
        sa.Column("port_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "server_deployment_port_id_fkey",
        "server_deployment",
        "port",
        ["port_id"],
        ["id"],
    )

    # 2. Partial unique index: one active deployment per port
    op.execute(
        "CREATE UNIQUE INDEX ix_server_deployment_port_id_active "
        "ON server_deployment (port_id) "
        "WHERE is_active = true AND port_id IS NOT NULL"
    )


def downgrade():
    # Drop partial unique index
    op.execute("DROP INDEX IF EXISTS ix_server_deployment_port_id_active")

    # Drop FK and column
    op.drop_constraint(
        "server_deployment_port_id_fkey",
        "server_deployment",
        type_="foreignkey",
    )
    op.drop_column("server_deployment", "port_id")
