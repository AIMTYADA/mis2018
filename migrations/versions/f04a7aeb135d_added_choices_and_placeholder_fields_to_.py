"""added choices and placeholder fields to the customer info item model

Revision ID: f04a7aeb135d
Revises: 729fb1154c63
Create Date: 2019-11-10 05:16:59.336254

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f04a7aeb135d'
down_revision = '729fb1154c63'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('comhealth_customer_info_items', sa.Column('choices', sa.String(length=128), nullable=True))
    op.add_column('comhealth_customer_info_items', sa.Column('placeholder', sa.String(length=64), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('comhealth_customer_info_items', 'placeholder')
    op.drop_column('comhealth_customer_info_items', 'choices')
    # ### end Alembic commands ###
