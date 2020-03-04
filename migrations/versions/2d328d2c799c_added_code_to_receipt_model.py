"""added code to Receipt model

Revision ID: 2d328d2c799c
Revises: f2b8516a468d
Create Date: 2019-12-24 00:11:30.551840

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2d328d2c799c'
down_revision = 'f2b8516a468d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('comhealth_test_receipts', sa.Column('code', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('comhealth_test_receipts', 'code')
    # ### end Alembic commands ###
