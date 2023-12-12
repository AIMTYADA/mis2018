"""Added harddisk, capacity, and note in ProcurementInfoComputer model

Revision ID: 09d35aa25943
Revises: 309b8b2e627e
Create Date: 2023-12-12 16:00:48.055413

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '09d35aa25943'
down_revision = '309b8b2e627e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('procurement_info_computers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('harddisk', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('capacity', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('note', sa.String(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('procurement_info_computers', schema=None) as batch_op:
        batch_op.drop_column('note')
        batch_op.drop_column('capacity')
        batch_op.drop_column('harddisk')

    # ### end Alembic commands ###
