"""added lis test group model

Revision ID: e9252400ad25
Revises: 4fa12fe20307
Create Date: 2018-09-10 02:18:16.684730

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e9252400ad25'
down_revision = '4fa12fe20307'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('lis_test_groups',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('abbr', sa.String(), nullable=False),
    sa.Column('name', sa.String(), nullable=False),
    sa.Column('description', sa.String(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('lis_test_groups')
    # ### end Alembic commands ###
