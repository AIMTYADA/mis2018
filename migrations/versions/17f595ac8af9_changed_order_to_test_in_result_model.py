"""changed order to test in result model

Revision ID: 17f595ac8af9
Revises: ff31b3392618
Create Date: 2018-09-10 08:10:31.273846

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '17f595ac8af9'
down_revision = 'ff31b3392618'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(u'lis_results_order_id_fkey', 'lis_results', type_='foreignkey')
    op.create_foreign_key(None, 'lis_results', 'lis_tests', ['order_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'lis_results', type_='foreignkey')
    op.create_foreign_key(u'lis_results_order_id_fkey', 'lis_results', 'lis_orders', ['order_id'], ['id'])
    # ### end Alembic commands ###
