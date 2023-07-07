"""added meeting note and agenda

Revision ID: 79d91bd2e2ea
Revises: 6f5f09e47bec
Create Date: 2023-07-06 10:22:45.471466

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '79d91bd2e2ea'
down_revision = '6f5f09e47bec'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('meeting_agenda_notes',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('note', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('staff_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['staff_id'], ['staff_account.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('meeting_agendas',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('group', sa.String(), nullable=False),
    sa.Column('number', sa.String(), nullable=True),
    sa.Column('detail', sa.Text(), nullable=True),
    sa.Column('consensus', sa.Text(), nullable=True),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('consensus_updated_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('meeting_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['meeting_id'], ['meeting_events.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('meeting_agendas')
    op.drop_table('meeting_agenda_notes')
    # ### end Alembic commands ###
