"""added relationships for KPIs + processes + services

Revision ID: 14359c19725c
Revises: d6c05b494c30
Create Date: 2022-02-23 16:19:06.148221

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '14359c19725c'
down_revision = 'd6c05b494c30'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('kpi_process_assoc',
    sa.Column('kpi_id', sa.Integer(), nullable=False),
    sa.Column('process_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['kpi_id'], ['kpis.id'], ),
    sa.ForeignKeyConstraint(['process_id'], ['db_processes.id'], ),
    sa.PrimaryKeyConstraint('kpi_id', 'process_id')
    )
    op.create_table('kpi_service_assoc',
    sa.Column('kpi_id', sa.Integer(), nullable=False),
    sa.Column('core_service_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['core_service_id'], ['db_core_services.id'], ),
    sa.ForeignKeyConstraint(['kpi_id'], ['kpis.id'], ),
    sa.PrimaryKeyConstraint('kpi_id', 'core_service_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('kpi_service_assoc')
    op.drop_table('kpi_process_assoc')
    # ### end Alembic commands ###
