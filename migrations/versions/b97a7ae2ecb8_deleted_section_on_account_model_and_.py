"""Deleted section on Account Model and Updated choice of status added period on Status Model

Revision ID: b97a7ae2ecb8
Revises: af26f5312795
Create Date: 2021-12-08 16:03:32.982000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b97a7ae2ecb8'
down_revision = 'af26f5312795'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('tracker_accounts', 'section')
    op.add_column('tracker_statuses', sa.Column('account_id', sa.Integer(), nullable=True))
    op.add_column('tracker_statuses', sa.Column('period', sa.String(length=255), nullable=False))
    op.drop_constraint(u'tracker_statuses_item_id_fkey', 'tracker_statuses', type_='foreignkey')
    op.create_foreign_key(None, 'tracker_statuses', 'tracker_accounts', ['account_id'], ['id'])
    op.drop_column('tracker_statuses', 'item_id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('tracker_statuses', sa.Column('item_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'tracker_statuses', type_='foreignkey')
    op.create_foreign_key(u'tracker_statuses_item_id_fkey', 'tracker_statuses', 'tracker_accounts', ['item_id'], ['id'])
    op.drop_column('tracker_statuses', 'period')
    op.drop_column('tracker_statuses', 'account_id')
    op.add_column('tracker_accounts', sa.Column('section', sa.VARCHAR(length=255), autoincrement=False, nullable=False))
    # ### end Alembic commands ###
