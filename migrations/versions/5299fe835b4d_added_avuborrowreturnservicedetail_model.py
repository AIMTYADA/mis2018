"""Added AVUBorrowReturnServiceDetail model

Revision ID: 5299fe835b4d
Revises: 3b1999967872
Create Date: 2024-01-23 14:46:57.381528

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5299fe835b4d'
down_revision = '3b1999967872'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('avu_borrow_return_service_details',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('number', sa.String(), nullable=True),
    sa.Column('type_requester', sa.String(), nullable=True),
    sa.Column('objective', sa.Text(), nullable=True),
    sa.Column('request_date', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.Date(), server_default=sa.text('now()'), nullable=True),
    sa.Column('staff_id', sa.Integer(), nullable=True),
    sa.Column('student_year', sa.String(), nullable=True),
    sa.Column('student_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['staff_id'], ['staff_account.id'], ),
    sa.ForeignKeyConstraint(['student_id'], ['eduqa_students.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('avu_borrow_return_service_details')
    # ### end Alembic commands ###
