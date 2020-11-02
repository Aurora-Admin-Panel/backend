"""Remove remote_address and remote_port

Revision ID: 9f2851c635ee
Revises: 839d89c468af
Create Date: 2020-11-02 04:21:18.441896

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f2851c635ee'
down_revision = '839d89c468af'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('port_forward_rule', schema=None) as batch_op:
        batch_op.drop_column('type')
        batch_op.drop_column('remote_port')
        batch_op.drop_column('remote_ip')
        batch_op.drop_column('remote_address')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('port_forward_rule', schema=None) as batch_op:
        batch_op.add_column(sa.Column('remote_address', sa.VARCHAR(), nullable=False))
        batch_op.add_column(sa.Column('remote_ip', sa.VARCHAR(), nullable=True))
        batch_op.add_column(sa.Column('remote_port', sa.INTEGER(), nullable=False))
        batch_op.add_column(sa.Column('type', sa.VARCHAR(), nullable=True))

    # ### end Alembic commands ###
