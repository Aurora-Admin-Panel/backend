"""add deployment source support

Revision ID: b7c9e2f4a1d3
Revises: a3f8c1d2e4b5
Create Date: 2026-03-08 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b7c9e2f4a1d3"
down_revision = "a3f8c1d2e4b5"
branch_labels = None
depends_on = None


def upgrade():
    # 1. Add is_builtin to executable_contract
    op.add_column(
        "executable_contract",
        sa.Column("is_builtin", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # 2. Add contract_id FK to server_deployment
    op.add_column(
        "server_deployment",
        sa.Column("contract_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_server_deployment_contract_id",
        "server_deployment",
        "executable_contract",
        ["contract_id"],
        ["id"],
    )

    # 3. Make binding_id nullable
    op.alter_column(
        "server_deployment",
        "binding_id",
        existing_type=sa.Integer(),
        nullable=True,
    )

    # 4. Drop existing unique constraint and create partial unique indexes
    op.drop_constraint(
        "_server_deployment_binding_id_server_id_uc",
        "server_deployment",
        type_="unique",
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_server_deployment_binding_server "
        "ON server_deployment (binding_id, server_id) "
        "WHERE binding_id IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX ix_server_deployment_contract_server "
        "ON server_deployment (contract_id, server_id) "
        "WHERE contract_id IS NOT NULL"
    )


def downgrade():
    # Drop partial unique indexes
    op.execute("DROP INDEX IF EXISTS ix_server_deployment_contract_server")
    op.execute("DROP INDEX IF EXISTS ix_server_deployment_binding_server")

    # Delete rows with null binding_id before restoring NOT NULL
    op.execute("DELETE FROM server_deployment WHERE binding_id IS NULL")

    # Restore unique constraint
    op.create_unique_constraint(
        "_server_deployment_binding_id_server_id_uc",
        "server_deployment",
        ["binding_id", "server_id"],
    )

    # Make binding_id NOT NULL again
    op.alter_column(
        "server_deployment",
        "binding_id",
        existing_type=sa.Integer(),
        nullable=False,
    )

    # Drop contract_id FK and column
    op.drop_constraint(
        "fk_server_deployment_contract_id",
        "server_deployment",
        type_="foreignkey",
    )
    op.drop_column("server_deployment", "contract_id")

    # Drop is_builtin
    op.drop_column("executable_contract", "is_builtin")
