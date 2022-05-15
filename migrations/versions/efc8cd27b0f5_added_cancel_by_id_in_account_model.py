"""Added cancel by id in account model

Revision ID: efc8cd27b0f5
Revises: 2444f4d6d3a4
Create Date: 2022-05-04 20:04:15.571000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'efc8cd27b0f5'
down_revision = '2444f4d6d3a4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('tracker_accounts', sa.Column('cancelled_by_id', sa.Integer(), nullable=True))
    op.alter_column('tracker_accounts', 'amount',
               existing_type=postgresql.DOUBLE_PRECISION(precision=53),
               nullable=False)
    op.alter_column('tracker_accounts', 'formats',
               existing_type=sa.VARCHAR(length=255),
               nullable=False)
    op.create_foreign_key(None, 'tracker_accounts', 'staff_account', ['cancelled_by_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'tracker_accounts', type_='foreignkey')
    op.alter_column('tracker_accounts', 'formats',
               existing_type=sa.VARCHAR(length=255),
               nullable=True)
    op.alter_column('tracker_accounts', 'amount',
               existing_type=postgresql.DOUBLE_PRECISION(precision=53),
               nullable=True)
    op.drop_column('tracker_accounts', 'cancelled_by_id')
    # ### end Alembic commands ###
