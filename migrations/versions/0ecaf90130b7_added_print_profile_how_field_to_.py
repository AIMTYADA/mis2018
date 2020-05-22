"""added print profile how field to receipt model

Revision ID: 0ecaf90130b7
Revises: 43d55755cca4
Create Date: 2020-03-10 13:57:41.734137

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0ecaf90130b7'
down_revision = '43d55755cca4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('comhealth_test_receipts', sa.Column('print_profile_how', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('comhealth_test_receipts', 'print_profile_how')
    # ### end Alembic commands ###
