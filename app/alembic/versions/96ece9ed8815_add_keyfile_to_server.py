"""Add keyfile to server

Revision ID: 96ece9ed8815
Revises: 7d8ca5f66e5f
Create Date: 2022-08-31 04:47:42.489617

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '96ece9ed8815'
down_revision = '7d8ca5f66e5f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('server', schema=None) as batch_op:
        batch_op.add_column(sa.Column('key_filename', sa.String(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('server', schema=None) as batch_op:
        batch_op.drop_column('key_filename')

    # ### end Alembic commands ###