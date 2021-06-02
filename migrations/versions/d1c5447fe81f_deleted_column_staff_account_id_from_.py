"""deleted column staff_account_id from table staff_seminar_attends and edited backref name

Revision ID: d1c5447fe81f
Revises: 696e0d8b86d1
Create Date: 2021-05-24 21:43:06.498120

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd1c5447fe81f'
down_revision = '696e0d8b86d1'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(u'staff_seminar_attends_staff_account_id_fkey', 'staff_seminar_attends', type_='foreignkey')
    op.drop_column('staff_seminar_attends', 'staff_account_id')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('staff_seminar_attends', sa.Column('staff_account_id', sa.INTEGER(), autoincrement=False, nullable=True))
    op.create_foreign_key(u'staff_seminar_attends_staff_account_id_fkey', 'staff_seminar_attends', 'staff_account', ['staff_account_id'], ['id'])
    # ### end Alembic commands ###
