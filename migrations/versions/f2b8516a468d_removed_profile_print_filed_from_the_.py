"""removed profile print filed from the ReceiptID model

Revision ID: f2b8516a468d
Revises: 7d9062fc6c39
Create Date: 2019-12-23 23:03:07.607865

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f2b8516a468d'
down_revision = '7d9062fc6c39'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('comhealth_receipt_ids', 'print_profile_note')
    op.add_column('comhealth_test_receipts', sa.Column('print_profile_note', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('comhealth_test_receipts', 'print_profile_note')
    op.add_column('comhealth_receipt_ids', sa.Column('print_profile_note', sa.BOOLEAN(), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
