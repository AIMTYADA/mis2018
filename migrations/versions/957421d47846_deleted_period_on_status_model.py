"""Deleted period on Status Model

Revision ID: 957421d47846
Revises: b97a7ae2ecb8
Create Date: 2021-12-09 15:48:46.791000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '957421d47846'
down_revision = 'b97a7ae2ecb8'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('tracker_statuses', 'period')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('tracker_statuses', sa.Column('period', sa.VARCHAR(length=255), autoincrement=False, nullable=False))
    # ### end Alembic commands ###
