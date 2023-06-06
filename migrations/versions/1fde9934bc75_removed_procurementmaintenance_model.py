"""Removed ProcurementMaintenance model

Revision ID: 1fde9934bc75
Revises: fb143f0601cd
Create Date: 2023-04-07 11:53:00.045000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1fde9934bc75'
down_revision = 'fb143f0601cd'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('procurement_maintenances')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('procurement_maintenances',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('staff_id', sa.INTEGER(), autoincrement=False, nullable=False),
    sa.Column('repair_date', sa.DATE(), autoincrement=False, nullable=True),
    sa.Column('detail', sa.TEXT(), autoincrement=False, nullable=True),
    sa.Column('note', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('type', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('company_name', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('contact_name', sa.VARCHAR(length=255), autoincrement=False, nullable=True),
    sa.Column('tel', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('cost', sa.INTEGER(), autoincrement=False, nullable=True),
    sa.Column('company_des', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.Column('require', sa.VARCHAR(), autoincrement=False, nullable=True),
    sa.ForeignKeyConstraint(['staff_id'], [u'staff_account.id'], name=u'procurement_maintenances_staff_id_fkey'),
    sa.PrimaryKeyConstraint('id', name=u'procurement_maintenances_pkey')
    )
    # ### end Alembic commands ###
