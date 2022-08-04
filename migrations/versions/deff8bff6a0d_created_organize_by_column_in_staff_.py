"""created organize_by column in staff_seminar table

Revision ID: deff8bff6a0d
Revises: a00c66f2b9b2
Create Date: 2022-07-08 13:32:55.755822

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'deff8bff6a0d'
down_revision = 'a00c66f2b9b2'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('staff_seminar', sa.Column('organize_by', sa.String(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('staff_seminar', 'organize_by')
    # ### end Alembic commands ###
