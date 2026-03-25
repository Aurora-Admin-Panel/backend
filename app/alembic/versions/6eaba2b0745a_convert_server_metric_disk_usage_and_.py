"""Convert server_metric, disk_usage and network_counter to hypertable

Revision ID: 6eaba2b0745a
Revises: 492e2ac71b0a
Create Date: 2025-08-28 13:43:25.532935

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "6eaba2b0745a"
down_revision = "492e2ac71b0a"
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
            CREATE INDEX IF NOT EXISTS server_metric_sid_time_desc ON server_metric (server_id, time DESC);
            ALTER TABLE server_metric SET (
                timescaledb.compress,
                timescaledb.compress_orderby = 'time DESC',
                timescaledb.compress_segmentby = 'server_id'
            );
            SELECT add_reorder_policy('server_metric', 'server_metric_sid_time_desc');
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
            CREATE INDEX IF NOT EXISTS disk_usage_sid_time_desc ON disk_usage (server_id, time DESC);
            ALTER TABLE disk_usage SET (
                timescaledb.compress,
                timescaledb.compress_orderby = 'time DESC',
                timescaledb.compress_segmentby = 'server_id, mount'
            );
            SELECT add_reorder_policy('disk_usage', 'disk_usage_sid_time_desc');
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
            CREATE INDEX IF NOT EXISTS network_counter_sid_time_desc ON network_counter (server_id, time DESC);
            CREATE INDEX IF NOT EXISTS network_counter_sid_iface_time_desc ON network_counter (server_id, iface, time DESC);
            ALTER TABLE network_counter SET (
                timescaledb.compress,
                timescaledb.compress_orderby = 'time DESC',
                timescaledb.compress_segmentby = 'server_id, iface'
            );
            SELECT add_reorder_policy('network_counter', 'network_counter_sid_iface_time_desc');
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
            DROP INDEX IF EXISTS server_metric_sid_time_desc;
            DROP INDEX IF EXISTS disk_usage_sid_time_desc;
            DROP INDEX IF EXISTS network_counter_sid_time_desc;
            DROP INDEX IF EXISTS network_counter_sid_iface_time_desc;
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
        sa.PrimaryKeyConstraint("server_id", "mount", "time"),
    )

    op.create_table(
        "network_counter",
        sa.Column("time", postgresql.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("server_id", sa.Integer(), nullable=False),
        sa.Column("iface", sa.String(), nullable=False),
        sa.Column("rx_bytes_total", sa.BigInteger(), nullable=False),
        sa.Column("tx_bytes_total", sa.BigInteger(), nullable=False),
        sa.ForeignKeyConstraint(["server_id"], ["server.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("server_id", "iface", "time"),
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
        sa.Column("swap_used_pct", sa.Float(), nullable=True),
        sa.Column("net_rx_bps", sa.Float(), nullable=True),
        sa.Column("net_tx_bps", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["server_id"], ["server.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("server_id", "time"),
    )
