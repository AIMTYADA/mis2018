"""Created new procurement details table

Revision ID: 39a1408fd55c
Revises: ff0fafc1a5a6
Create Date: 2021-11-04 15:02:49.266000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '39a1408fd55c'
down_revision = 'ff0fafc1a5a6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('procurement_details',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('number', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('procurement_details')
    # ### end Alembic commands ###
