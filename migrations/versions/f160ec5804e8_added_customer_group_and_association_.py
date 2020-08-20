"""added customer group and association table

Revision ID: f160ec5804e8
Revises: 8a621c2894bf
Create Date: 2020-08-20 12:58:47.481598

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f160ec5804e8'
down_revision = '8a621c2894bf'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('comhealth_customer_groups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('desc', sa.Text(), nullable=True),
    sa.Column('created_at', sa.Date(), server_default=sa.text(u'now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('comhealth_group_customers',
    sa.Column('customer_id', sa.Integer(), nullable=False),
    sa.Column('group_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['customer_id'], ['comhealth_customer_groups.id'], ),
    sa.ForeignKeyConstraint(['group_id'], ['comhealth_customers.id'], ),
    sa.PrimaryKeyConstraint('customer_id', 'group_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('comhealth_group_customers')
    op.drop_table('comhealth_customer_groups')
    # ### end Alembic commands ###
