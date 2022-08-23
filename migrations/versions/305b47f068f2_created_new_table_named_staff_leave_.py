"""created new table named staff_leave_used_quota for colled used leave day and quota day of each leave type in each person

Revision ID: 305b47f068f2
Revises: 2e16f22e6508
Create Date: 2022-08-22 10:53:02.680121

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '305b47f068f2'
down_revision = '2e16f22e6508'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('staff_leave_used_quota',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('leave_type_id', sa.Integer(), nullable=True),
    sa.Column('staff_account_id', sa.Integer(), nullable=True),
    sa.Column('used_days', sa.Float(), nullable=True),
    sa.Column('quota_days', sa.Float(), nullable=True),
    sa.ForeignKeyConstraint(['leave_type_id'], ['staff_leave_types.id'], ),
    sa.ForeignKeyConstraint(['staff_account_id'], ['staff_account.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('staff_leave_used_quota')
    # ### end Alembic commands ###
