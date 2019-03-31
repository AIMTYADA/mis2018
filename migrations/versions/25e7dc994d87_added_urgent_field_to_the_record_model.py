"""added urgent field to the record model

Revision ID: 25e7dc994d87
Revises: 782214ea363f
Create Date: 2019-03-31 10:39:19.851287

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '25e7dc994d87'
down_revision = '782214ea363f'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('comhealth_test_records', sa.Column('urgent', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('comhealth_test_records', 'urgent')
    # ### end Alembic commands ###
