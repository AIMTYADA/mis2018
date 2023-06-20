"""added event and participant association table

Revision ID: cdf234b0242d
Revises: d929cc1d08c7
Create Date: 2023-05-23 17:22:24.317968

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'cdf234b0242d'
down_revision = 'd929cc1d08c7'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('event_participant_assoc',
    sa.Column('staff_id', sa.Integer(), nullable=True),
    sa.Column('event_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['event_id'], ['scheduler_room_reservations.id'], ),
    sa.ForeignKeyConstraint(['staff_id'], ['staff_account.id'], )
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('event_participant_assoc')
    # ### end Alembic commands ###
