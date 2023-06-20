"""Added ScbPaymentRecord model

Revision ID: a078b3fea292
Revises: 7bbc4f789e9d
Create Date: 2022-12-16 14:36:34.987000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a078b3fea292'
down_revision = '7bbc4f789e9d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('scb_payment_records',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('payer_account_number', sa.String(), nullable=True),
    sa.Column('payee_proxy_type', sa.String(), nullable=True),
    sa.Column('send_bank_code', sa.String(), nullable=True),
    sa.Column('payee_proxy_id', sa.String(), nullable=True),
    sa.Column('bill_payment_ref3', sa.String(), nullable=True),
    sa.Column('currency_code', sa.String(), nullable=True),
    sa.Column('transaction_type', sa.String(), nullable=True),
    sa.Column('transaction_date_time', sa.DateTime(timezone=True), nullable=True),
    sa.Column('channel_code', sa.String(), nullable=True),
    sa.Column('bill_payment_ref1', sa.String(), nullable=True),
    sa.Column('amount', sa.Float(asdecimal=True), nullable=True),
    sa.Column('payer_proxy_type', sa.String(), nullable=True),
    sa.Column('payee_name', sa.String(), nullable=True),
    sa.Column('receiveing_bank_code', sa.String(), nullable=True),
    sa.Column('payee_account_number', sa.String(), nullable=True),
    sa.Column('payer_proxy_id', sa.String(), nullable=True),
    sa.Column('bill_payment_ref2', sa.String(), nullable=True),
    sa.Column('transaction_id', sa.String(), nullable=True),
    sa.Column('payer_name', sa.String(), nullable=True),
    sa.Column('customer1', sa.String(), nullable=True),
    sa.Column('customer2', sa.String(), nullable=True),
    sa.Column('service', sa.String(), nullable=True),
    sa.Column('created_datetime', sa.DateTime(timezone=True), server_default=sa.text(u'now()'), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('scb_payment_records')
    # ### end Alembic commands ###
