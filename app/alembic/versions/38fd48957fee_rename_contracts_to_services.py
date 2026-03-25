"""rename contracts to services

Revision ID: 38fd48957fee
Revises: b7c9e2f4a1d3
Create Date: 2026-03-08 20:22:33.789225

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '38fd48957fee'
down_revision = 'b7c9e2f4a1d3'
branch_labels = None
depends_on = None


def upgrade():
    # --- Rename tables ---
    op.rename_table("executable_contract", "service_definition")
    op.rename_table("file_contract_binding", "service_binding")

    # --- Rename columns in service_definition ---
    op.alter_column("service_definition", "contract_key", new_column_name="service_key")
    op.alter_column("service_definition", "schema_json", new_column_name="config_json")

    # --- Rename columns in service_binding ---
    op.alter_column("service_binding", "contract_id", new_column_name="service_id")

    # --- Rename columns in server_deployment ---
    op.alter_column("server_deployment", "contract_id", new_column_name="service_id")
    op.alter_column("server_deployment", "binding_id", new_column_name="service_binding_id")

    # --- Rename primary key constraints ---
    op.execute("ALTER INDEX executable_contract_pkey RENAME TO service_definition_pkey")
    op.execute("ALTER INDEX file_contract_binding_pkey RENAME TO service_binding_pkey")

    # --- Rename indexes ---
    op.execute("ALTER INDEX ix_executable_contract_id RENAME TO ix_service_definition_id")
    op.execute("ALTER INDEX ix_executable_contract_contract_key RENAME TO ix_service_definition_service_key")
    op.execute("ALTER INDEX ix_file_contract_binding_id RENAME TO ix_service_binding_id")

    # --- Rename unique constraints (implemented as unique indexes) ---
    op.execute(
        "ALTER INDEX _executable_contract_contract_key_version_uc "
        "RENAME TO _service_definition_service_key_version_uc"
    )
    op.execute(
        "ALTER INDEX _file_contract_binding_file_id_contract_id_uc "
        "RENAME TO _service_binding_file_id_service_id_uc"
    )

    # --- Rename foreign key constraints ---
    op.execute(
        "ALTER TABLE service_binding "
        "RENAME CONSTRAINT file_contract_binding_file_id_fkey "
        "TO service_binding_file_id_fkey"
    )
    op.execute(
        "ALTER TABLE service_binding "
        "RENAME CONSTRAINT file_contract_binding_contract_id_fkey "
        "TO service_binding_service_id_fkey"
    )
    op.execute(
        "ALTER TABLE server_deployment "
        "RENAME CONSTRAINT server_deployment_binding_id_fkey "
        "TO server_deployment_service_binding_id_fkey"
    )
    op.execute(
        "ALTER TABLE server_deployment "
        "RENAME CONSTRAINT fk_server_deployment_contract_id "
        "TO server_deployment_service_id_fkey"
    )

    # --- Rename partial unique indexes on server_deployment ---
    op.execute(
        "ALTER INDEX ix_server_deployment_binding_server "
        "RENAME TO ix_server_deployment_service_binding_server"
    )
    op.execute(
        "ALTER INDEX ix_server_deployment_contract_server "
        "RENAME TO ix_server_deployment_service_server"
    )


def downgrade():
    # --- Reverse partial unique index renames ---
    op.execute(
        "ALTER INDEX ix_server_deployment_service_server "
        "RENAME TO ix_server_deployment_contract_server"
    )
    op.execute(
        "ALTER INDEX ix_server_deployment_service_binding_server "
        "RENAME TO ix_server_deployment_binding_server"
    )

    # --- Reverse foreign key constraint renames ---
    op.execute(
        "ALTER TABLE server_deployment "
        "RENAME CONSTRAINT server_deployment_service_id_fkey "
        "TO fk_server_deployment_contract_id"
    )
    op.execute(
        "ALTER TABLE server_deployment "
        "RENAME CONSTRAINT server_deployment_service_binding_id_fkey "
        "TO server_deployment_binding_id_fkey"
    )
    op.execute(
        "ALTER TABLE service_binding "
        "RENAME CONSTRAINT service_binding_service_id_fkey "
        "TO file_contract_binding_contract_id_fkey"
    )
    op.execute(
        "ALTER TABLE service_binding "
        "RENAME CONSTRAINT service_binding_file_id_fkey "
        "TO file_contract_binding_file_id_fkey"
    )

    # --- Reverse unique constraint renames ---
    op.execute(
        "ALTER INDEX _service_binding_file_id_service_id_uc "
        "RENAME TO _file_contract_binding_file_id_contract_id_uc"
    )
    op.execute(
        "ALTER INDEX _service_definition_service_key_version_uc "
        "RENAME TO _executable_contract_contract_key_version_uc"
    )

    # --- Reverse index renames ---
    op.execute("ALTER INDEX ix_service_binding_id RENAME TO ix_file_contract_binding_id")
    op.execute("ALTER INDEX ix_service_definition_service_key RENAME TO ix_executable_contract_contract_key")
    op.execute("ALTER INDEX ix_service_definition_id RENAME TO ix_executable_contract_id")

    # --- Reverse primary key renames ---
    op.execute("ALTER INDEX service_binding_pkey RENAME TO file_contract_binding_pkey")
    op.execute("ALTER INDEX service_definition_pkey RENAME TO executable_contract_pkey")

    # --- Reverse column renames ---
    op.alter_column("server_deployment", "service_binding_id", new_column_name="binding_id")
    op.alter_column("server_deployment", "service_id", new_column_name="contract_id")
    op.alter_column("service_binding", "service_id", new_column_name="contract_id")
    op.alter_column("service_definition", "config_json", new_column_name="schema_json")
    op.alter_column("service_definition", "service_key", new_column_name="contract_key")

    # --- Reverse table renames ---
    op.rename_table("service_binding", "file_contract_binding")
    op.rename_table("service_definition", "executable_contract")
