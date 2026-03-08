"""add deployment tables

Revision ID: a3f8c1d2e4b5
Revises: 2d91d4b3a7b1
Create Date: 2026-03-08 00:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "a3f8c1d2e4b5"
down_revision = "2d91d4b3a7b1"
branch_labels = None
depends_on = None


def upgrade():
    # --- file_contract_binding ---
    op.create_table(
        "file_contract_binding",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("contract_id", sa.Integer(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.ForeignKeyConstraint(["file_id"], ["file.id"]),
        sa.ForeignKeyConstraint(["contract_id"], ["executable_contract.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "file_id",
            "contract_id",
            name="_file_contract_binding_file_id_contract_id_uc",
        ),
    )
    op.create_index(
        op.f("ix_file_contract_binding_id"),
        "file_contract_binding",
        ["id"],
        unique=False,
    )

    # --- server_deployment ---
    deployment_status = postgresql.ENUM(
        "pending", "deploying", "deployed", "failed", "stopped", "removing",
        name="deploymentstatusenum",
        create_type=False,
    )
    deployment_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "server_deployment",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("binding_id", sa.Integer(), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("values_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column(
            "status",
            deployment_status,
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
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
        sa.ForeignKeyConstraint(["binding_id"], ["file_contract_binding.id"]),
        sa.ForeignKeyConstraint(["server_id"], ["server.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "binding_id",
            "server_id",
            name="_server_deployment_binding_id_server_id_uc",
        ),
    )
    op.create_index(
        op.f("ix_server_deployment_id"),
        "server_deployment",
        ["id"],
        unique=False,
    )

    # --- deployment_log ---
    action_enum = postgresql.ENUM(
        "deploy", "redeploy", "stop", "start", "remove",
        name="deploymentactionenum",
        create_type=False,
    )
    action_enum.create(op.get_bind(), checkfirst=True)

    log_status_enum = postgresql.ENUM(
        "pending", "running", "success", "failed",
        name="deploymentlogstatusenum",
        create_type=False,
    )
    log_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "deployment_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("deployment_id", sa.Integer(), nullable=False),
        sa.Column("action", action_enum, nullable=False),
        sa.Column(
            "status",
            log_status_enum,
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("plan_json", sa.JSON(), nullable=True),
        sa.Column("output", sa.Text(), nullable=True),
        sa.Column("task_id", sa.String(), nullable=True),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            postgresql.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("finished_at", postgresql.TIMESTAMP(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["deployment_id"], ["server_deployment.id"]),
        sa.ForeignKeyConstraint(["created_by_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_deployment_log_id"),
        "deployment_log",
        ["id"],
        unique=False,
    )


def downgrade():
    op.drop_index(op.f("ix_deployment_log_id"), table_name="deployment_log")
    op.drop_table("deployment_log")

    op.drop_index(op.f("ix_server_deployment_id"), table_name="server_deployment")
    op.drop_table("server_deployment")

    op.drop_index(op.f("ix_file_contract_binding_id"), table_name="file_contract_binding")
    op.drop_table("file_contract_binding")

    # Drop enum types
    sa.Enum(name="deploymentlogstatusenum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="deploymentactionenum").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="deploymentstatusenum").drop(op.get_bind(), checkfirst=True)
