"""add executable contract table

Revision ID: 2d91d4b3a7b1
Revises: 755615b034b5
Create Date: 2026-02-25 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "2d91d4b3a7b1"
down_revision = "755615b034b5"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "executable_contract",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("contract_key", sa.String(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("schema_json", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "contract_key",
            "version",
            name="_executable_contract_contract_key_version_uc",
        ),
    )
    op.create_index(op.f("ix_executable_contract_id"), "executable_contract", ["id"], unique=False)
    op.create_index(
        op.f("ix_executable_contract_contract_key"),
        "executable_contract",
        ["contract_key"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_executable_contract_contract_key"), table_name="executable_contract")
    op.drop_index(op.f("ix_executable_contract_id"), table_name="executable_contract")
    op.drop_table("executable_contract")

