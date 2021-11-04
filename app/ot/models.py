# -*- coding:utf-8 -*-

from ..main import db
from pytz import timezone
from app.models import Org
from app.staff.models import StaffAccount
from datetime import datetime


class OtPaymentAnnounce(db.Model):
    __tablename__ = 'ot_payment_announce'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    topic = db.Column('topic', db.String(), info={'label':u'เรื่อง'})
    file_name = db.Column('file_name', db.String())
    upload_file_url = db.Column('upload_file_url', db.String())
    created_account_id = db.Column('created_account_id', db.ForeignKey('staff_account.id'))
    staff = db.relationship(StaffAccount, backref=db.backref('ot_announcement'))
    created_at = db.Column('created_at', db.DateTime(timezone=True), default=datetime.now())
    announce_at = db.Column('announce_at', db.DateTime(timezone=True), info={'label':u'ประกาศเมื่อ'})
    start_datetime = db.Column('start_datetime', db.DateTime(timezone=True), info={'label':u'เริ่มใช้ตั้งแต่'})
    cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))


class OtCompensationRate(db.Model):
    __tablename__ = 'ot_compensation_rate'
    id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
    announce_id = db.Column('announce_id', db.ForeignKey('ot_payment_announce.id'))
    work_at_org_id = db.Column('work_at_org_id', db.ForeignKey('orgs.id'))
    work_for_org_id = db.Column('work_for_org_id', db.ForeignKey('orgs.id'))
    work_at_org = db.relationship(Org, backref=db.backref('ot_work_at_rate'), foreign_keys=[work_at_org_id])
    work_for_org = db.relationship(Org, backref=db.backref('ot_work_for_rate'), foreign_keys=[work_for_org_id])
    role = db.Column('role', db.String(), info={'label':u'ตำแหน่ง'})
    per_period = db.Column('per_period', db.Integer(), info={'label':u'ต่อคาบ'})
    per_hour = db.Column('per_hour', db.Integer(), info={'label':u'ต่อชั่วโมง'})
    per_day = db.Column('per_day', db.Integer(), info={'label':u'ต่อวัน'})
    ot_start_datetime = db.Column('ot_start_datetime', db.DateTime(timezone=True))
    ot_end_datetime = db.Column('ot_end_datetime', db.DateTime(timezone=True))
    is_faculty_emp = db.Column('is_faculty_emp', db.Boolean(), info={'label':u'บุคลากรสังกัดคณะ'})
    is_workday = db.Column('is_workday', db.Boolean(), default=True, nullable=False, info={'label':u'นอกเวลาราชการ'})
    max_hour = db.Column('max_hour', db.Integer(), info={'label':u'จำนวนชั่วโมงสูงสุดที่สามารถทำได้'})
    double_payment = db.Column('double_payment', db.Boolean(), default=True, nullable=False,
                               info={'label':u'เบิกซ้ำกับอันอื่นได้'})


# class OtDocumentApproval(db.Model):
#     __tablename__ = 'ot_document_approval'
#     id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
#     approval_no = db.Column('approval_no', db.String())
#     approved_date = db.Column('approved_date', db.Date(), nullable=True)
#     created_at = db.Column('created_at',db.DateTime(timezone=True),default=datetime.now())
#     start_datetime = db.Column('start_datetime', db.DateTime(), nullable=False)
#     end_datetime = db.Column('end_datetime', db.DateTime())
#     cancelled_at = db.Column('cancelled_at', db.DateTime(timezone=True))
#     org_id = db.Column('orgs_id', db.ForeignKey('orgs.id'))
#     org = db.relationship(Org, backref=db.backref('document_approval'))
#     upload_file_url = db.Column('upload_file_url', db.String())
#     io_no
#     cost_no
#
#
# class OtApprovalDetail(db.Model):
#     __tablename__ = 'ot_approval_detail'
#     id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
#     doc_id = db.Column('doc_id', db.ForeignKey('ot_document_approval.id'))
#     role = db.Column('role', db.String())
#
#
# class OtPerson(db.Model):
#     __tablename__ = 'ot_document_approval'
#     id = db.Column('id', db.Integer(), primary_key=True, autoincrement=True)
#     doc_id = db.Column('doc_id', db.ForeignKey('ot_document_approval.id'))
#     created_at = db.Column('created_at',db.DateTime(timezone=True),default=datetime.now())
#     staff_account_id = db.Column('staff_account_id', db.ForeignKey('staff_account.id'))
#     staff = db.relationship(StaffAccount, backref=db.backref('ot_person'))


