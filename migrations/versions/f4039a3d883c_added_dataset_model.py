"""added dataset model

Revision ID: f4039a3d883c
Revises: 14359c19725c
Create Date: 2022-02-25 08:25:04.006636

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f4039a3d883c'
down_revision = '14359c19725c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('db_datasets',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('reference', sa.String(length=255), nullable=False),
    sa.Column('desc', sa.Text(), nullable=True),
    sa.Column('source_url', sa.Text(), nullable=True),
    sa.Column('data_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['data_id'], ['db_data.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('db_datasets')
    # ### end Alembic commands ###
