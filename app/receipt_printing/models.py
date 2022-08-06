# -*- coding:utf-8 -*-
from app.main import db


class ElectronicReceiptCashier(db.Model):
    __tablename__ = 'electronic_receipt_cashier'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    staff_id = db.Column('staff_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship('StaffAccount', backref=db.backref('cashier',
                                                               cascade='all, delete-orphan',
                                                               uselist=False))
    position = db.Column('position', db.String(255))

    @property
    def fullname(self):
        return self.staff.personal_info.fullname

    def __str__(self):
        return self.fullname


class ElectronicReceiptDetail(db.Model):
    __tablename__ = 'electronic_receipt_details'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    number = db.Column('number', db.String(), info={'label': u'เลขที่'})
    copy_number = db.Column('copy_number', db.Integer, default=1)
    book_number = db.Column('book_number', db.String(), info={'label': u'เล่มที่'})
    created_datetime = db.Column('created_datetime', db.DateTime(timezone=True))
    comment = db.Column('comment', db.Text())
    paid = db.Column('paid', db.Boolean(), default=False)
    cancelled = db.Column('cancelled', db.Boolean(), default=False)
    cancel_comment = db.Column('cancel_comment', db.Text())
    issuer_id = db.Column('issuer_id', db.ForeignKey('electronic_receipt_cashier.id'))
    issuer = db.relationship('ElectronicReceiptCashier',
                             foreign_keys=[issuer_id],
                             backref=db.backref('issued_receipts'))
    issued_at = db.Column('issued_at', db.String())
    cashier_id = db.Column('cashier_id', db.ForeignKey('electronic_receipt_cashier.id'))
    cashier = db.relationship('ElectronicReceiptCashier', foreign_keys=[cashier_id])
    payment_method = db.Column('payment_method', db.String(), info={'label': u'ช่องทางการชำระเงิน',
                                'choices': [(c, c) for c in
                                [u'เงินสด', u'บัตรเครดิต', u'Scan QR Code', u'โอนผ่านระบบธนาคารอัตโนมัติ', u'เช็คสั่งจ่าย' ]]})
    paid_amount = db.Column('paid_amount', db.Numeric(), default=0.0)
    card_number = db.Column('card_number', db.String(16))
    issued_for = db.Column('issued_for', db.String())
    address = db.Column('address', db.Text())


class ElectronicReceiptList(db.Model):
    __tablename__ = 'electronic_receipt_lists'
    id = db.Column('id', db.Integer, autoincrement=True, primary_key=True)
    item = db.Column('item', db.String())
    receipt_id = db.Column('receipt_id', db.ForeignKey('electronic_receipt_details.id'))
    receipt = db.relationship('ElectronicReceiptDetail',
                           backref=db.backref('items', cascade='all, delete-orphan'))
    price = db.Column('price', db.Numeric(), default=0.0)
    quantity = db.Column('quantity', db.Numeric(), default=1.0)
    comment = db.Column('comment', db.Text())