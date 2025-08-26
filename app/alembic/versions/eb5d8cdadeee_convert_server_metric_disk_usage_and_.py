"""Convert server_metric, disk_usage and network_counter to hypertable

Revision ID: eb5d8cdadeee
Revises: 82e1de08b245
Create Date: 2025-08-26 23:26:09.733220

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "eb5d8cdadeee"
down_revision = "82e1de08b245"
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    conn.execute(
        text("""
            SELECT create_hypertable('server_metric', 'time',
                partitioning_column => 'server_id',
                number_partitions => 4,
                chunk_time_interval => INTERVAL '1 day',
                if_not_exists => TRUE,
                migrate_data => TRUE
            );
            ALTER TABLE server_metric SET (
                timescaledb.compress,
                timescaledb.compress_orderby = 'time DESC',
                timescaledb.compress_segmentby = 'server_id'
            );
            SELECT add_compression_policy('server_metric', INTERVAL '7 days');
            SELECT add_retention_policy('server_metric', INTERVAL '120 days');
        """)
    )
    conn.execute(
        text("""
            SELECT create_hypertable('disk_usage', 'time',
                partitioning_column => 'server_id',
                number_partitions => 4,
                chunk_time_interval => INTERVAL '1 day',
                if_not_exists => TRUE,
                migrate_data => TRUE
            );
            ALTER TABLE disk_usage SET (
                timescaledb.compress,
                timescaledb.compress_orderby = 'time DESC',
                timescaledb.compress_segmentby = 'server_id'
            );
            SELECT add_compression_policy('disk_usage', INTERVAL '7 days');
            SELECT add_retention_policy('disk_usage', INTERVAL '120 days');
            """)
    )
    conn.execute(
        text("""
            SELECT create_hypertable('network_counter', 'time',
                partitioning_column => 'server_id',
                number_partitions => 4,
                chunk_time_interval => INTERVAL '1 day',
                if_not_exists => TRUE,
                migrate_data => TRUE
            );
            ALTER TABLE network_counter SET (
                timescaledb.compress,
                timescaledb.compress_orderby = 'time DESC',
                timescaledb.compress_segmentby = 'server_id'
            );
            SELECT add_compression_policy('network_counter', INTERVAL '7 days');
            SELECT add_retention_policy('network_counter', INTERVAL '120 days');
            """)
    )


def downgrade():
    conn = op.get_bind()
    conn.execute(
        text("""
            SELECT remove_retention_policy('server_metric', if_exists => true);
            SELECT remove_compression_policy('server_metric', if_exists => true);
            SELECT remove_retention_policy('disk_usage', if_exists => true);
            SELECT remove_compression_policy('disk_usage', if_exists => true);
            SELECT remove_retention_policy('network_counter', if_exists => true);
            SELECT remove_compression_policy('network_counter', if_exists => true);
            DROP TABLE server_metric CASCADE;
            DROP TABLE disk_usage CASCADE;
            DROP TABLE network_counter CASCADE;
        """)
    )

    op.create_table(
        "disk_usage",
        sa.Column("time", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("mount", sa.String(), nullable=False),
        sa.Column("used_bytes", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["server_id"], ["server.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("server_id", "time"),
    )
    with op.batch_alter_table("disk_usage", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_disk_usage_mount"), ["mount"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_disk_usage_server_id"), ["server_id"], unique=False
        )
        batch_op.create_index(batch_op.f("ix_disk_usage_time"), ["time"], unique=False)

    op.create_table(
        "network_counter",
        sa.Column("time", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("iface", sa.String(), nullable=False),
        sa.Column("rx_bytes_total", sa.BigInteger(), nullable=False),
        sa.Column("tx_bytes_total", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["server_id"], ["server.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("server_id", "time", "iface"),
    )
    with op.batch_alter_table("network_counter", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_network_counter_iface"), ["iface"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_network_counter_server_id"), ["server_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_network_counter_time"), ["time"], unique=False
        )

    op.create_table(
        "server_metric",
        sa.Column("time", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("is_online", sa.Boolean(), nullable=False),
        sa.Column("cpu_util_pct", sa.Float(), nullable=False),
        sa.Column("load_1m", sa.Float(), nullable=False),
        sa.Column("load_5m", sa.Float(), nullable=False),
        sa.Column("load_15m", sa.Float(), nullable=False),
        sa.Column("mem_used_bytes", sa.BigInteger(), nullable=False),
        sa.Column("swap_used_bytes", sa.BigInteger(), nullable=False),
        sa.Column("fs_root_used_bytes", sa.BigInteger(), nullable=False),
        sa.Column("mem_used_pct", sa.Float(), nullable=True),
        sa.Column("fs_root_used_pct", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["server_id"], ["server.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("server_id", "time"),
    )
    with op.batch_alter_table("server_metric", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_server_metric_server_id"), ["server_id"], unique=False
        )
        batch_op.create_index(
            batch_op.f("ix_server_metric_time"), ["time"], unique=False
        )
