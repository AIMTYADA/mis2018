"""Added column received from in ElectronicReceiptDetail model

Revision ID: d98e9eee1b25
Revises: 03ca7f8d689c
Create Date: 2022-08-11 15:41:49.934000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd98e9eee1b25'
down_revision = '03ca7f8d689c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('electronic_receipt_details', sa.Column('received_from', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('electronic_receipt_details', 'received_from')
    # ### end Alembic commands ###
