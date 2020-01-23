"""replaced firstname and lastname with staff account

Revision ID: 7fe034326b48
Revises: ba74f681cdfa
Create Date: 2020-01-24 01:24:38.332444

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7fe034326b48'
down_revision = 'ba74f681cdfa'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('comhealth_cashier', sa.Column('staff_id', sa.Integer(), nullable=True))
    op.drop_index('ix_comhealth_cashier_firstname', table_name='comhealth_cashier')
    op.drop_index('ix_comhealth_cashier_lastname', table_name='comhealth_cashier')
    op.create_foreign_key(None, 'comhealth_cashier', 'staff_account', ['staff_id'], ['id'])
    op.drop_column('comhealth_cashier', 'lastname')
    op.drop_column('comhealth_cashier', 'firstname')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('comhealth_cashier', sa.Column('firstname', sa.VARCHAR(length=255), autoincrement=False, nullable=True))
    op.add_column('comhealth_cashier', sa.Column('lastname', sa.VARCHAR(length=255), autoincrement=False, nullable=True))
    op.drop_constraint(None, 'comhealth_cashier', type_='foreignkey')
    op.create_index('ix_comhealth_cashier_lastname', 'comhealth_cashier', ['lastname'], unique=False)
    op.create_index('ix_comhealth_cashier_firstname', 'comhealth_cashier', ['firstname'], unique=False)
    op.drop_column('comhealth_cashier', 'staff_id')
    # ### end Alembic commands ###
