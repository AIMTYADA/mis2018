# -*- coding:utf-8 -*-
import time

from dateutil import parser
from flask_login import login_required, current_user
from pandas import read_excel, isna, DataFrame
from app.eduqa.models import EduQAInstructor, EduQACourseSession, EduQACurriculumnRevision

from models import *
from . import staffbp as staff
from app.main import db, get_weekdays, mail, app, csrf
from app.models import Holidays, Org
from flask import jsonify, render_template, request, redirect, url_for, flash, session, send_from_directory, \
    make_response
from datetime import date, datetime
from collections import defaultdict, namedtuple
import pytz
from sqlalchemy import and_, desc, func, cast, Date, or_
from werkzeug.utils import secure_filename
from app.auth.views import line_bot_api
from linebot.models import TextSendMessage
from pydrive.auth import ServiceAccountCredentials, GoogleAuth
from pydrive.drive import GoogleDrive
import requests
import gviz_api
import os
from flask_mail import Message
from flask_admin import BaseView, expose
from itsdangerous import TimedJSONWebSignatureSerializer
import qrcode
from app.staff.forms import StaffSeminarForm, create_seminar_attend_form
from app.roles import admin_permission, hr_permission

from ..comhealth.views import allowed_file

gauth = GoogleAuth()
keyfile_dict = requests.get(os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')).json()
scopes = ['https://www.googleapis.com/auth/drive']
gauth.credentials = ServiceAccountCredentials.from_json_keyfile_dict(keyfile_dict, scopes)
drive = GoogleDrive(gauth)

tz = pytz.timezone('Asia/Bangkok')

# TODO: remove hardcoded annual quota soon
LEAVE_ANNUAL_QUOTA = 10

def get_fiscal_date(date):
    if date.month >= 10:
        start_fiscal_date = datetime(date.year, 10, 1)
        end_fiscal_date = datetime(date.year + 1, 9, 30, 23, 59, 59, 0)
    else:
        start_fiscal_date = datetime(date.year - 1, 10, 1)
        end_fiscal_date = datetime(date.year, 9, 30, 23, 59, 59, 0)
    return start_fiscal_date, end_fiscal_date

def convert_to_fiscal_year(date):
    if date.month in [10, 11, 12]:
        return date.year + 1
    else:
        return date.year


def get_start_end_date_for_fiscal_year(fiscal_year):
    '''Find start and end date from a given fiscal year.

    :param fiscal_year:  fiscal year
    :return: date
    '''
    start_date = date(fiscal_year - 1, 10, 1)
    end_date = date(fiscal_year, 9, 30)
    return start_date, end_date


def send_mail(recp, title, message):
    message = Message(subject=title, body=message, recipients=recp)
    mail.send(message)


@staff.route('/')
@login_required
def index():
    new_leave_requests = 0
    new_wfh_requests = 0
    for requester in current_user.leave_approvers:
        if requester.is_active:
            for req in StaffLeaveRequest.query.filter_by(staff=requester.requester):
                if len(req.get_approved_by(current_user)) == 0 and req.cancelled_at is None:
                    if (datetime.today().date() - req.created_at.date()).days < 60:
                        new_leave_requests += 1
    for requester in current_user.wfh_approvers:
        if requester.is_active:
            for req in StaffWorkFromHomeRequest.query.filter_by(staff=requester.requester):
                if len(req.get_approved_by(current_user)) == 0 and req.cancelled_at is None:
                    if (datetime.today().date() - req.created_at.date()).days < 60:
                        new_wfh_requests += 1
    return render_template('staff/index.html', new_leave_requests=new_leave_requests, new_wfh_requests=new_wfh_requests)


@staff.route('/person/<int:account_id>')
def show_person_info(account_id=None):
    if account_id:
        account = StaffAccount.query.get(account_id)
        return render_template('staff/info.html', person=account)


@staff.route('/api/list/')
@staff.route('/api/list/<int:account_id>')
def get_staff(account_id=None):
    data = []
    if not account_id:
        accounts = StaffAccount.query.all()
        for account in accounts:
            data.append({
                'email': account.email,
                'firstname': account.personal_info.en_firstname,
                'lastname': account.personal_info.en_lastname,
            })
    else:
        account = StaffAccount.query.get(account_id)
        if account:
            data = [{
                'email': account.email,
                'firstname': account.personal_info.en_firstname,
                'lastname': account.personal_info.en_lastname,
            }]
        else:
            return jsonify(data), 401
    return jsonify(data), 200


@staff.route('/set_password', methods=['GET', 'POST'])
def set_password():
    if request.method == 'POST':
        email = request.form.get('email', None)
        return email
    return render_template('staff/set_password.html')


@staff.route('/leave/info')
@login_required
def show_leave_info():
    START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
    Quota = namedtuple('quota', ['id', 'limit', 'can_request'])
    cum_days = defaultdict(float)
    quota_days = defaultdict(float)
    pending_days = defaultdict(float)
    for req in current_user.leave_requests:
        used_quota = current_user.personal_info.get_total_leaves(req.quota.id,
                                                                 tz.localize(START_FISCAL_DATE),
                                                                 tz.localize(END_FISCAL_DATE))
        leave_type = unicode(req.quota.leave_type)
        cum_days[leave_type] = used_quota
        pending_day = current_user.personal_info.get_total_pending_leaves_request \
            (req.quota.id, tz.localize(START_FISCAL_DATE), tz.localize(END_FISCAL_DATE))
        pending_days[leave_type] = pending_day
    for quota in current_user.personal_info.employment.quota:
        delta = current_user.personal_info.get_employ_period()
        max_cum_quota = current_user.personal_info.get_max_cum_quota_per_year(quota)
        last_quota = StaffLeaveUsedQuota.query.filter_by(staff=current_user, fiscal_year=END_FISCAL_DATE.year-1,
                                                         leave_type=quota.leave_type).first()
        if delta.years > 0:
            if max_cum_quota:
                if last_quota:
                    quota_limit = last_quota.quota_days
                else:
                    quota_limit = max_cum_quota
            else:
                quota_limit = quota.max_per_year
        else:
            if delta.months > 5:
                quota_limit = quota.first_year
            else:
                quota_limit = quota.first_year if not quota.min_employed_months else 0
        can_request = quota.leave_type.requester_self_added
        quota_days[quota.leave_type.type_] = Quota(quota.id, quota_limit, can_request)

    approver = StaffLeaveApprover.query.filter_by(approver_account_id=current_user.id).first()
    return render_template('staff/leave_info.html',
                           line_profile=session.get('line_profile'),
                           cum_days=cum_days,
                           pending_days=pending_days,
                           quota_days=quota_days,
                           approver=approver)


@staff.route('/leave/request/quota/<int:quota_id>', methods=['GET', 'POST'])
@login_required
def request_for_leave(quota_id=None):
    if request.method == 'POST':
        form = request.form
        if quota_id:
            quota = StaffLeaveQuota.query.get(quota_id)
            if quota:
                start_t = "08:30"
                end_t = "16:30"
                start_d, end_d = form.get('dates').split(' - ')
                start_dt = '{} {}'.format(start_d, start_t)
                end_dt = '{} {}'.format(end_d, end_t)
                start_datetime = datetime.strptime(start_dt, '%d/%m/%Y %H:%M')
                end_datetime = datetime.strptime(end_dt, '%d/%m/%Y %H:%M')
                START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(start_datetime)
                if StaffLeaveRequest.query.filter(and_(StaffLeaveRequest.staff_account_id == current_user.id,
                                                       StaffLeaveRequest.start_datetime == start_datetime,
                                                       StaffLeaveRequest.quota == quota,
                                                       StaffLeaveRequest.cancelled_at == None)).first():
                    flash(u'ท่านได้มีการขอลาในวันดังกล่าวแล้ว')
                    return redirect(url_for('staff.request_for_leave_info', quota_id=quota_id))
                else:
                    req = StaffLeaveRequest(
                        start_datetime=tz.localize(start_datetime),
                        end_datetime=tz.localize(end_datetime),
                        created_at=tz.localize(datetime.today())
                    )
                    if form.get('traveldates'):
                        start_travel_dt, end_travel_dt = form.get('traveldates').split(' - ')
                        start_travel_datetime = datetime.strptime(start_travel_dt, '%d/%m/%Y')
                        end_travel_datetime = datetime.strptime(end_travel_dt, '%d/%m/%Y')
                        req.start_travel_datetime = tz.localize(start_travel_datetime)
                        req.end_travel_datetime = tz.localize(end_travel_datetime)
                    upload_file = request.files.get('document')
                    after_hour = True if form.getlist("after_hour") else False
                    if upload_file:
                        upload_file_name = secure_filename(upload_file.filename)
                        upload_file.save(upload_file_name)
                        file_drive = drive.CreateFile({'title': upload_file_name})
                        file_drive.SetContentFile(upload_file_name)
                        file_drive.Upload()
                        permission = file_drive.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
                        upload_file_id = file_drive['id']
                    else:
                        upload_file_id = None
                    if start_datetime.date() <= END_FISCAL_DATE.date() < end_datetime.date():
                        flash(u'ไม่สามารถลาข้ามปีงบประมาณได้ กรุณาส่งคำร้องแยกกัน 2 ครั้ง โดยแยกตามปีงบประมาณ')
                        resp = make_response()
                        resp.headers['HX-Redirect'] = request.referrer
                        return resp
                    delta = start_datetime.date() - datetime.today().date()
                    if delta.days > 0 and not quota.leave_type.request_in_advance:
                        flash(u'ไม่สามารถลาล่วงหน้าได้ กรุณาลองใหม่')
                        resp = make_response()
                        resp.headers['HX-Redirect'] = request.referrer
                        return resp
                        # retrieve cum periods
                    used_quota = current_user.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
                                                                             tz.localize(END_FISCAL_DATE))
                    pending_days = current_user.personal_info.get_total_pending_leaves_request \
                        (quota.id, tz.localize(START_FISCAL_DATE), tz.localize(END_FISCAL_DATE))
                    req_duration = get_weekdays(req)
                    holidays = Holidays.query.filter(and_(Holidays.holiday_date >= start_datetime.date(),
                                                          Holidays.holiday_date <= end_datetime.date())).all()
                    req_duration = req_duration - len(holidays)
                    delta = current_user.personal_info.get_employ_period()
                    if req_duration == 0:
                        flash(u'วันลาตรงกับวันหยุด')
                        resp = make_response()
                        resp.headers['HX-Redirect'] = request.referrer
                        return resp
                    if quota.max_per_leave:
                        if req_duration >= quota.max_per_leave and upload_file_id is None:
                            flash(u'ไม่สามารถลาป่วยเกินสามวันได้โดยไม่มีใบรับรองแพทย์ประกอบ', 'danger')
                            resp = make_response()
                            resp.headers['HX-Redirect'] = request.referrer
                            return resp
                        else:
                            if delta.years > 0:
                                quota_limit = quota.max_per_year
                            else:
                                quota_limit = quota.first_year
                    else:
                        max_cum_quota = current_user.personal_info.get_max_cum_quota_per_year(quota)
                        if delta.years > 0:
                            if max_cum_quota:
                                is_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=current_user,
                                                                                    leave_type=quota.leave_type,
                                                                                    fiscal_year=END_FISCAL_DATE.year).first()
                                is_last_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=current_user,
                                                                                        leave_type=quota.leave_type,
                                                                                        fiscal_year=END_FISCAL_DATE.year-1).first()
                                if not is_used_quota:
                                    if is_last_used_quota:
                                        last_remain_quota = is_last_used_quota.quota_days - is_last_used_quota.used_days
                                    else:
                                        last_remain_quota = max_cum_quota
                                    before_cut_max_quota = last_remain_quota + LEAVE_ANNUAL_QUOTA
                                    quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
                                else:
                                    quota_limit = is_used_quota.quota_days
                            else:
                                quota_limit = quota.max_per_year
                        else:
                            # skip min employ month of annual leave because leave req button doesn't appear
                            quota_limit = quota.first_year
                    req.quota = quota
                    req.staff = current_user
                    req.reason = form.get('reason')
                    req.country = form.get('country')
                    req.contact_address = form.get('contact_addr')
                    req.contact_phone = form.get('contact_phone')
                    req.total_leave_days = req_duration
                    req.upload_file_url = upload_file_id
                    req.after_hour = after_hour
                    print (used_quota, pending_days, req_duration, quota_limit)
                    if used_quota + pending_days + req_duration <= quota_limit:
                        if form.getlist('notified_by_line'):
                            req.notify_to_line = True
                        db.session.add(req)
                        db.session.commit()
                        mails = []
                        req_title = u'แจ้งการขออนุมัติ' + req.quota.leave_type.type_
                        req_msg = u'{} ขออนุมัติ{} ระหว่างวันที่ {} ถึงวันที่ {}\nคลิกที่ Link เพื่อดูรายละเอียดเพิ่มเติม {} ' \
                                  u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'. \
                            format(current_user.personal_info.fullname, req.quota.leave_type.type_,
                                   start_datetime, end_datetime,
                                   url_for("staff.pending_leave_approval", req_id=req.id, _external=True))
                        for approver in StaffLeaveApprover.query.filter_by(staff_account_id=current_user.id):
                            if approver.is_active:
                                if approver.notified_by_line and approver.account.line_id:
                                    if os.environ["FLASK_ENV"] == "production":
                                        line_bot_api.push_message(to=approver.account.line_id,
                                                                  messages=TextSendMessage(text=req_msg))
                                    else:
                                        print(req_msg, approver.account.id)
                                mails.append(approver.account.email + "@mahidol.ac.th")
                        if os.environ["FLASK_ENV"] == "production":
                            send_mail(mails, req_title, req_msg)
                        is_used_quota = StaffLeaveUsedQuota.query.filter_by(leave_type_id=req.quota.leave_type_id,
                                                                            staff_account_id=req.staff_account_id,
                                                                            fiscal_year=END_FISCAL_DATE.year).first()
                        if is_used_quota:
                            is_used_quota.used_days += req_duration
                            is_used_quota.pending_days += req_duration
                            db.session.add(is_used_quota)
                            db.session.commit()
                        else:
                            new_used_quota = StaffLeaveUsedQuota(
                                leave_type_id=req.quota.leave_type_id,
                                staff_account_id=current_user.id,
                                fiscal_year=END_FISCAL_DATE.year,
                                used_days=used_quota + pending_days + req_duration,
                                pending_days=pending_days + req_duration,
                                quota_days=quota_limit
                            )
                            db.session.add(new_used_quota)
                            db.session.commit()
                        flash(u'ส่งคำขอของท่านเรียบร้อยแล้ว (The request has been sent.)', 'success')
                        resp = make_response()
                        resp.headers['HX-Redirect'] = url_for('staff.request_for_leave_info', quota_id=quota_id)
                        return resp
                    else:
                        flash(u'วันลาที่ต้องการลา เกินจำนวนวันลาคงเหลือ (The quota is exceeded.)', 'danger')
                        resp = make_response()
                        resp.headers['HX-Redirect'] = request.referrer
                        return resp
            else:
                flash(u'ไม่พบข้อมูลในระบบฐานข้อมูล (Leave quota not found)', 'danger')
                resp = make_response()
                resp.headers['HX-Redirect'] = request.referrer
                return resp
    else:
        quota = StaffLeaveQuota.query.get(quota_id)
        holidays = [h.tojson()['date'] for h in Holidays.query.all()]
        START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
        delta = current_user.personal_info.get_employ_period()
        max_cum_quota = current_user.personal_info.get_max_cum_quota_per_year(quota)

        this_year_quota = StaffLeaveUsedQuota.query.filter_by(staff=current_user, fiscal_year=END_FISCAL_DATE.year,
                                                              leave_type_id=quota_id).first()
        last_year_quota = StaffLeaveUsedQuota.query.filter_by(staff=current_user,
                                                              fiscal_year=END_FISCAL_DATE.year-1,
                                                              leave_type_id=quota_id).first()
        if delta.years > 0:
            if max_cum_quota:
                if this_year_quota:
                    quota_limit = this_year_quota.quota_days
                else:
                    if last_year_quota:
                        last_year_quota = last_year_quota.quota_days - last_year_quota.used_days
                    else:
                        last_year_quota = max_cum_quota
                    before_cut_max_quota = last_year_quota + LEAVE_ANNUAL_QUOTA
                    quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
            else:
                quota_limit = quota.max_per_year
        else:
            if delta.months > 5:
                quota_limit = quota.first_year
            else:
                quota_limit = quota.first_year if not quota.min_employed_months else 0

        used_quota = current_user.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),tz.localize(END_FISCAL_DATE))
        pending_quota = current_user.personal_info.get_total_pending_leaves_request(quota.id,tz.localize(START_FISCAL_DATE),tz.localize(END_FISCAL_DATE))

        if this_year_quota:
            used_quota = this_year_quota.used_days
        else:
            used_quota = used_quota + pending_quota
        return render_template('staff/leave_request.html',
                               errors={},
                               quota=quota,
                               holidays=holidays,
                               used_quota=used_quota,
                               quota_limit=quota_limit)


@staff.route('/leave/request/quota/period/<int:quota_id>', methods=["POST", "GET"])
@login_required
def request_for_leave_period(quota_id=None):
    if request.method == 'POST':
        form = request.form
        if quota_id:
            quota = StaffLeaveQuota.query.get(quota_id)
            if quota:
                # retrieve cum periods
                start_t, end_t = form.get('times').split(' - ')
                start_d, end_d = form.get('dates').split(' - ')
                start_dt = '{} {}'.format(start_d, start_t)
                end_dt = '{} {}'.format(end_d, end_t)
                start_datetime = datetime.strptime(start_dt, '%d/%m/%Y %H:%M')
                end_datetime = datetime.strptime(end_dt, '%d/%m/%Y %H:%M')
                delta = start_datetime.date() - datetime.today().date()
                if delta.days > 0 and not quota.leave_type.request_in_advance:
                    flash(u'ไม่สามารถลาล่วงหน้าได้ กรุณาลองใหม่')
                    return redirect(request.referrer)
                START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(start_datetime)
                used_quota = current_user.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
                                                                         tz.localize(END_FISCAL_DATE))
                pending_days = current_user.personal_info.get_total_pending_leaves_request \
                    (quota.id, tz.localize(START_FISCAL_DATE), tz.localize(END_FISCAL_DATE))
                if StaffLeaveRequest.query. \
                        filter_by(staff_account_id=current_user.id, start_datetime=start_datetime).first():
                    flash(u'ท่านได้มีการขอลาในวันดังกล่าวแล้ว')
                    return redirect(url_for('staff.request_for_leave_info', quota_id=quota_id))
                else:
                    req = StaffLeaveRequest(
                        start_datetime=tz.localize(start_datetime),
                        end_datetime=tz.localize(end_datetime),
                        created_at=tz.localize(datetime.today())
                    )
                    req_duration = get_weekdays(req)
                    if req_duration == 0:
                        flash(u'วันลาตรงกับเสาร์-อาทิตย์')
                        return redirect(request.referrer)
                    holidays = Holidays.query.filter(Holidays.holiday_date == start_datetime.date()).all()
                    req_duration = req_duration - len(holidays)
                    if req_duration <= 0:
                        flash(u'วันลาตรงกับวันหยุด')
                        return redirect(request.referrer)
                    delta = current_user.personal_info.get_employ_period()

                    max_cum_quota = current_user.personal_info.get_max_cum_quota_per_year(quota)
                    if delta.years > 0:
                        if max_cum_quota:
                            is_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=current_user,
                                                                                leave_type=quota.leave_type,
                                                                                fiscal_year=END_FISCAL_DATE.year).first()
                            is_last_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=current_user,
                                                                                     leave_type=quota.leave_type,
                                                                                     fiscal_year=END_FISCAL_DATE.year - 1).first()
                            if not is_used_quota:
                                if is_last_used_quota:
                                    last_remain_quota = is_last_used_quota.quota_days - is_last_used_quota.used_days
                                else:
                                    last_remain_quota = max_cum_quota
                                before_cut_max_quota = last_remain_quota + LEAVE_ANNUAL_QUOTA
                                quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
                            else:
                                quota_limit = is_used_quota.quota_days
                        else:
                            quota_limit = quota.max_per_year
                    else:
                        quota_limit = quota.first_year
                    req.quota = quota
                    req.staff = current_user
                    req.reason = form.get('reason')
                    req.contact_address = form.get('contact_addr')
                    req.contact_phone = form.get('contact_phone')
                    req.total_leave_days = req_duration
                    if used_quota + pending_days + req_duration <= quota_limit:
                        if form.getlist('notified_by_line'):
                            req.notify_to_line = True
                        db.session.add(req)
                        db.session.commit()
                        mails = []
                        req_title = u'แจ้งการขออนุมัติ' + req.quota.leave_type.type_
                        req_msg = u'{} ขออนุมัติ{} ระหว่างวันที่ {} ถึงวันที่ {}\nคลิกที่ Link เพื่อดูรายละเอียดเพิ่มเติม {} ' \
                                  u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'. \
                            format(current_user.personal_info.fullname, req.quota.leave_type.type_,
                                   start_datetime, end_datetime,
                                   url_for("staff.pending_leave_approval", req_id=req.id, _external=True))
                        for approver in StaffLeaveApprover.query.filter_by(staff_account_id=current_user.id):
                            if approver.is_active:
                                if approver.notified_by_line and approver.account.line_id:
                                    if os.environ["FLASK_ENV"] == "production":
                                        line_bot_api.push_message(to=approver.account.line_id,
                                                                  messages=TextSendMessage(text=req_msg))
                                    else:
                                        print(req_msg, approver.account.id)
                                mails.append(approver.account.email + "@mahidol.ac.th")
                        if os.environ["FLASK_ENV"] == "production":
                            send_mail(mails, req_title, req_msg)

                        _, END_FISCAL_DATE = get_fiscal_date(req.start_datetime)
                        is_used_quota = StaffLeaveUsedQuota.query.filter_by(leave_type_id=req.quota.leave_type_id,
                                                                            staff_account_id=req.staff_account_id,
                                                                            fiscal_year=END_FISCAL_DATE.year).first()
                        if is_used_quota:
                            new_used=is_used_quota.used_days+req.total_leave_days
                            is_used_quota.used_days = new_used
                            db.session.add(is_used_quota)
                            db.session.commit()
                        else:
                            new_used_quota = StaffLeaveUsedQuota(
                                leave_type_id=req.quota.leave_type_id,
                                staff_account_id=current_user.id,
                                fiscal_year=END_FISCAL_DATE.year,
                                used_days=used_quota + pending_days + req_duration,
                                quota_days=quota_limit
                            )
                            db.session.add(new_used_quota)
                            db.session.commit()
                        flash(u'ส่งคำขอของท่านเรียบร้อยแล้ว', 'success')
                        return redirect(url_for('staff.request_for_leave_info', quota_id=quota_id))
                    else:
                        flash(u'วันลาที่ต้องการลา เกินจำนวนวันลาคงเหลือ')
                        return redirect(request.referrer)
            else:
                return 'Error happened'
    else:
        quota = StaffLeaveQuota.query.get(quota_id)
        holidays = [h.tojson()['date'] for h in Holidays.query.all()]
        START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())

        delta = current_user.personal_info.get_employ_period()
        max_cum_quota = current_user.personal_info.get_max_cum_quota_per_year(quota)

        this_year_quota = StaffLeaveUsedQuota.query.filter_by(staff=current_user,leave_type_id=quota_id,
                                                              fiscal_year=END_FISCAL_DATE.year).first()
        last_year_quota = StaffLeaveUsedQuota.query.filter_by(staff=current_user,leave_type_id=quota_id,
                                                              fiscal_year=END_FISCAL_DATE.year - 1).first()
        if delta.years > 0:
            if max_cum_quota:
                if this_year_quota:
                    quota_limit = this_year_quota.quota_days
                else:
                    if last_year_quota:
                        last_year_quota = last_year_quota.quota_days - last_year_quota.used_days
                        before_cut_max_quota = last_year_quota + LEAVE_ANNUAL_QUOTA
                        quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
                    else:
                        quota_limit = quota.first_year
            else:
                quota_limit = quota.max_per_year
        else:
            if delta.months > 5:
                quota_limit = quota.first_year
            else:
                quota_limit = quota.first_year if not quota.min_employed_months else 0

        used_quota = current_user.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
                                                                 tz.localize(END_FISCAL_DATE)) if not this_year_quota else this_year_quota.pending_days
        return render_template('staff/leave_request_period.html', errors={}, quota=quota, holidays=holidays,
                               used_quota=used_quota, quota_limit=quota_limit)


@staff.route('/leave/request/info/<int:quota_id>')
@login_required
def request_for_leave_info(quota_id=None):
    quota = StaffLeaveQuota.query.get(quota_id)
    leaves = []
    fiscal_years = set()
    START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
    for leave in current_user.leave_requests:
        if leave.start_datetime >= tz.localize(START_FISCAL_DATE) and leave.end_datetime <= tz.localize(
                END_FISCAL_DATE):
            if leave.quota == quota:
                leaves.append(leave)
        if leave.start_datetime.month in [10, 11, 12]:
            fiscal_years.add(leave.start_datetime.year + 1)
        else:
            fiscal_years.add(leave.start_datetime.year)
    approved_days = current_user.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
                                                             tz.localize(END_FISCAL_DATE))
    pending_day = current_user.personal_info.get_total_pending_leaves_request \
                  (quota_id, tz.localize(START_FISCAL_DATE), tz.localize(END_FISCAL_DATE))
    quota_info = StaffLeaveUsedQuota.query.filter_by(
                                                    leave_type_id=quota.leave_type_id,
                                                    fiscal_year=END_FISCAL_DATE.year,
                                                    staff=current_user).first()
    return render_template('staff/request_info.html', leaves=leaves, quota=quota, approved_days=approved_days,
                           fiscal_years=fiscal_years, quota_info=quota_info, pending_day=pending_day)


@staff.route('/leave/request/info/<int:quota_id>/deleted')
@login_required
def leave_info_deleted_records(quota_id=None):
    quota = StaffLeaveQuota.query.get(quota_id)
    leaves = []
    fiscal_years = set()
    START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
    for leave in current_user.leave_requests:
        if leave.start_datetime >= tz.localize(START_FISCAL_DATE) and leave.end_datetime <= tz.localize(
                END_FISCAL_DATE) and leave.cancelled_at:
            if leave.quota == quota:
                leaves.append(leave)
        if leave.start_datetime.month in [10, 11, 12]:
            fiscal_years.add(leave.start_datetime.year + 1)
        else:
            fiscal_years.add(leave.start_datetime.year)
    return render_template('staff/leave_request_deleted_records.html', leaves=leaves, quota=quota,
                           fiscal_years=fiscal_years)


@staff.route('/leave/request/info/<int:quota_id>/others_year/<int:fiscal_year>')
@login_required
def request_for_leave_info_others_fiscal(quota_id=None, fiscal_year=None):
    quota = StaffLeaveQuota.query.get(quota_id)
    leaves = []
    for leave in current_user.leave_requests:
        if leave.start_datetime.month in [10, 11, 12]:
            fiscal_years = leave.start_datetime.year + 1
        else:
            fiscal_years = leave.start_datetime.year

        if fiscal_year == fiscal_years:
            if leave.quota == quota:
                leaves.append(leave)
                fiscal_year = fiscal_year

    requester = StaffLeaveApprover.query.filter_by(staff_account_id=current_user.id)

    return render_template('staff/leave_info_others_fiscal_year.html', leaves=leaves, reqester=requester, quota=quota,
                           fiscal_year=fiscal_year)


@staff.route('/leave/request/edit/<int:req_id>', methods=['GET', 'POST'])
@login_required
def edit_leave_request(req_id=None):
    req = StaffLeaveRequest.query.get(req_id)
    if req.total_leave_days == 0.5:
        return redirect(url_for("staff.edit_leave_request_period", req_id=req_id))
    if request.method == 'POST':
        previous_total_leave_days = req.total_leave_days
        quota = req.quota
        if quota:
            start_t = "08:30"
            end_t = "16:30"
            start_d, end_d = request.form.get('dates').split(' - ')
            start_dt = '{} {}'.format(start_d, start_t)
            end_dt = '{} {}'.format(end_d, end_t)
            start_datetime = datetime.strptime(start_dt, '%d/%m/%Y %H:%M')
            end_datetime = datetime.strptime(end_dt, '%d/%m/%Y %H:%M')
            req.start_datetime = tz.localize(start_datetime)
            req.end_datetime = tz.localize(end_datetime)
            START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(req.start_datetime)
            if start_datetime <= END_FISCAL_DATE and end_datetime > END_FISCAL_DATE:
                flash(u'ไม่สามารถลาข้ามปีงบประมาณได้ กรุณาส่งคำร้องแยกกัน 2 ครั้ง โดยแยกตามปีงบประมาณ')
                return redirect(request.referrer)
            if request.form.get('traveldates'):
                start_travel_dt, end_travel_dt = request.form.get('traveldates').split(' - ')
                start_travel_datetime = datetime.strptime(start_travel_dt, '%d/%m/%Y')
                end_travel_datetime = datetime.strptime(end_travel_dt, '%d/%m/%Y')
                if not (start_travel_datetime <= start_datetime and end_travel_datetime >= end_datetime):
                    flash(u'ช่วงเวลาเดินทาง ไม่ครอบคลุมวันที่ต้องการขอลา กรุณาตรวจสอบอีกครั้ง', "danger")
                    return redirect(request.referrer)
                else:
                    req.start_travel_datetime = tz.localize(start_travel_datetime)
                    req.end_travel_datetime = tz.localize(end_travel_datetime)
            else:
                req.start_travel_datetime = None
                req.end_travel_datetime = None
            upload_file = request.files.get('document')
            after_hour = True if request.form.getlist("after_hour") else False
            if upload_file:
                upload_file_name = secure_filename(upload_file.filename)
                upload_file.save(upload_file_name)
                file_drive = drive.CreateFile({'title': upload_file_name})
                file_drive.SetContentFile(upload_file_name)
                file_drive.Upload()
                permission = file_drive.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
                upload_file_id = file_drive['id']
            else:
                if req.upload_file_url:
                    upload_file_id = req.upload_file_url
                else:
                    upload_file_id = None
            delta = start_datetime.date() - datetime.today().date()
            if delta.days > 0 and not quota.leave_type.request_in_advance:
                flash(u'ไม่สามารถลาล่วงหน้าได้ กรุณาลองใหม่')
                return redirect(request.referrer)
                # retrieve cum periods
            used_quota = current_user.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
                                                                     tz.localize(END_FISCAL_DATE))
            pending_days = current_user.personal_info.get_total_pending_leaves_request \
                (quota.id, tz.localize(START_FISCAL_DATE), tz.localize(END_FISCAL_DATE))
            req_duration = get_weekdays(req)
            holidays = Holidays.query.filter(and_(Holidays.holiday_date >= start_datetime,
                                                  Holidays.holiday_date <= end_datetime)).all()
            req_duration = req_duration - len(holidays)
            delta = current_user.personal_info.get_employ_period()
            if req_duration == 0:
                flash(u'วันลาตรงกับวันหยุด')
                return redirect(request.referrer)
            if quota.max_per_leave:
                if req_duration > quota.max_per_leave and upload_file_id is None:
                    flash(
                        u'ไม่สามารถลาป่วยเกินสามวันได้โดยไม่มีใบรับรองแพทย์ประกอบ')
                    return redirect(request.referrer)
                else:
                    if delta.years > 0:
                        quota_limit = quota.max_per_year
                    else:
                        quota_limit = quota.first_year
            else:
                max_cum_quota = current_user.personal_info.get_max_cum_quota_per_year(quota)
                if delta.years > 0:
                    if max_cum_quota:
                        is_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=current_user,
                                                                            leave_type=quota.leave_type,
                                                                            fiscal_year=END_FISCAL_DATE.year).first()
                        is_last_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=current_user,
                                                                                 leave_type=quota.leave_type,
                                                                                 fiscal_year=END_FISCAL_DATE.year - 1).first()
                        if not is_used_quota:
                            if is_last_used_quota:
                                last_remain_quota = is_last_used_quota.quota_days - is_last_used_quota.used_days
                            else:
                                last_remain_quota = max_cum_quota
                            before_cut_max_quota = last_remain_quota + LEAVE_ANNUAL_QUOTA
                            quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
                        else:
                            quota_limit = is_used_quota.quota_days
                    else:
                        quota_limit = quota.max_per_year
                else:
                    # skip min employ month of annual leave because leave req button doesn't appear
                    quota_limit = quota.first_year

            req.reason = request.form.get('reason')
            req.country = request.form.get('country')
            req.contact_address = request.form.get('contact_addr'),
            req.contact_phone = request.form.get('contact_phone'),
            req.total_leave_days = req_duration
            req.upload_file_url = upload_file_id
            req.after_hour = after_hour
            if used_quota + pending_days + req_duration <= quota_limit:
                req.notify_to_line = True if request.form.getlist("notified_by_line") else False
                db.session.add(req)
                db.session.commit()

                _, END_FISCAL_DATE = get_fiscal_date(req.start_datetime)
                is_used_quota = StaffLeaveUsedQuota.query.filter_by(leave_type_id=req.quota.leave_type_id,
                                                                    staff_account_id=req.staff_account_id,
                                                                    fiscal_year=END_FISCAL_DATE.year).first()
                if is_used_quota:
                    new_used=(is_used_quota.used_days-previous_total_leave_days)+req.total_leave_days
                    is_used_quota.used_days = new_used
                    is_used_quota.pending_days = (is_used_quota.pending_days - previous_total_leave_days) + req_duration
                    db.session.add(is_used_quota)
                    db.session.commit()
                else:
                    new_used_quota = StaffLeaveUsedQuota(
                        leave_type_id=req.quota.leave_type_id,
                        staff_account_id=current_user.id,
                        fiscal_year=END_FISCAL_DATE.year,
                        used_days=(used_quota + pending_days + req_duration)-previous_total_leave_days,
                        pending_days=(pending_days - previous_total_leave_days)+req_duration,
                        quota_days=quota_limit
                    )
                    db.session.add(new_used_quota)
                    db.session.commit()
                flash(u'แก้ไขคำขอของท่านเรียบร้อยแล้ว', 'success')
                return redirect(url_for('staff.request_for_leave_info', quota_id=req.leave_quota_id))
            else:
                flash(u'วันลาที่ต้องการลา เกินจำนวนวันลาคงเหลือ', 'warning')
                return redirect(request.referrer)
        else:
            return 'Error happened'
    selected_dates = [req.start_datetime, req.end_datetime]
    travel_dates = [req.start_travel_datetime, req.end_travel_datetime]
    holidays = [h.tojson()['date'] for h in Holidays.query.all()]
    if req.upload_file_url:
        upload_file = drive.CreateFile({'id': req.upload_file_url})
        upload_file.FetchMetadata()
        upload_file_url = upload_file.get('embedLink')
    else:
        upload_file_url = None
    return render_template('staff/edit_leave_request.html', selected_dates=selected_dates, req=req, errors={},
                           travel_dates=travel_dates, holidays=holidays, upload_file_url=upload_file_url)


@staff.route('/leave/request/edit/period/<int:req_id>',
             methods=['GET', 'POST'])
@login_required
def edit_leave_request_period(req_id=None):
    req = StaffLeaveRequest.query.get(req_id)
    if request.method == 'POST':
        quota = req.quota
        if quota:
            start_t, end_t = request.form.get('times').split(' - ')
            start_d, end_d = request.form.get('dates').split(' - ')
            start_dt = '{} {}'.format(start_d, start_t)
            end_dt = '{} {}'.format(end_d, end_t)
            start_datetime = datetime.strptime(start_dt, '%d/%m/%Y %H:%M')
            end_datetime = datetime.strptime(end_dt, '%d/%m/%Y %H:%M')
            delta = start_datetime - datetime.today()
            if delta.days > 0 and not quota.leave_type.request_in_advance:
                flash(u'ไม่สามารถลาล่วงหน้าได้ กรุณาลองใหม่')
                return redirect(request.referrer)

            START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(start_datetime)
            used_quota = current_user.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
                                                                     tz.localize(END_FISCAL_DATE))
            pending_days = current_user.personal_info.get_total_pending_leaves_request \
                (quota.id, tz.localize(START_FISCAL_DATE), tz.localize(END_FISCAL_DATE))

            holidays = Holidays.query.filter(Holidays.holiday_date == start_datetime.date()).all()
            if len(holidays) > 0:
                flash(u'วันลาตรงกับวันหยุด')
                return redirect(request.referrer)
            req.start_datetime = tz.localize(start_datetime)
            req.end_datetime = tz.localize(end_datetime)
            req_duration = get_weekdays(req)
            if req_duration == 0:
                flash(u'วันลาตรงกับเสาร์-อาทิตย์')
                return redirect(request.referrer)
            # if duration not exceeds quota
            delta = current_user.personal_info.get_employ_period()

            max_cum_quota = current_user.personal_info.get_max_cum_quota_per_year(quota)
            if delta.years > 0:
                if max_cum_quota:
                    is_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=current_user,
                                                                        leave_type=quota.leave_type,
                                                                        fiscal_year=END_FISCAL_DATE.year).first()
                    is_last_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=current_user,
                                                                             leave_type=quota.leave_type,
                                                                             fiscal_year=END_FISCAL_DATE.year - 1).first()
                    if not is_used_quota:
                        if is_last_used_quota:
                            last_remain_quota = is_last_used_quota.quota_days - is_last_used_quota.used_days
                        else:
                            last_remain_quota = max_cum_quota
                        before_cut_max_quota = last_remain_quota + LEAVE_ANNUAL_QUOTA
                        quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
                    else:
                        quota_limit = is_used_quota.quota_days
                else:
                    quota_limit = quota.max_per_year
            else:
                quota_limit = quota.first_year

            req.reason = request.form.get('reason')
            req.contact_address = request.form.get('contact_addr')
            req.contact_phone = request.form.get('contact_phone')
            req.total_leave_days = req_duration
            if used_quota + pending_days + req_duration <= quota_limit:
                if request.form.getlist('notified_by_line'):
                    req.notify_to_line = True
                db.session.add(req)
                db.session.commit()
                _, END_FISCAL_DATE = get_fiscal_date(req.start_datetime)
                is_used_quota = StaffLeaveUsedQuota.query.filter_by(leave_type_id=req.quota.leave_type_id,
                                                                    staff_account_id=req.staff_account_id,
                                                                    fiscal_year=END_FISCAL_DATE.year).first()
                if not is_used_quota:
                    new_used_quota = StaffLeaveUsedQuota(
                        leave_type_id=req.quota.leave_type_id,
                        staff_account_id=current_user.id,
                        fiscal_year=END_FISCAL_DATE.year,
                        used_days=used_quota + pending_days + req_duration,
                        pending_days=pending_days,
                        quota_days=quota_limit
                    )
                    db.session.add(new_used_quota)
                    db.session.commit()
                flash(u'แก้ไขคำขอของท่านเรียบร้อยแล้ว', 'success')
                return redirect(url_for('staff.request_for_leave_info', quota_id=req.leave_quota_id))
            else:
                flash(u'วันลาที่ต้องการลา เกินจำนวนวันลาคงเหลือ')
                return redirect(request.referrer)
        else:
            return 'Error happened'

    selected_dates = req.start_datetime

    return render_template('staff/edit_leave_request_period.html', req=req, selected_dates=selected_dates, errors={})


@staff.route('/leave/requests/approval/info')
@login_required
def show_leave_approval_info():
    leave_types = StaffLeaveType.query.all()
    requesters = StaffLeaveApprover.query.filter_by(approver_account_id=current_user.id).all()
    requester_cum_periods = {}
    START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
    for requester in requesters:
        cum_periods = defaultdict(float)
        for leave_request in requester.requester.leave_requests:
            if leave_request.cancelled_at is None and leave_request.get_approved:
                if leave_request.start_datetime.date() >= START_FISCAL_DATE.date() and leave_request.end_datetime.date()\
                        <= END_FISCAL_DATE.date():
                    cum_periods[leave_request.quota.leave_type] += leave_request.total_leave_days
        requester_cum_periods[requester] = cum_periods
    approver = StaffLeaveApprover.query.filter_by(approver_account_id=current_user.id).first()
    if approver:
        line_notified = approver.notified_by_line
    else:
        return redirect(url_for('staff.show_leave_info'))
    today = datetime.today().date()
    return render_template('staff/leave_request_approval_info.html',
                           requesters=requesters,
                           approver=approver,
                           requester_cum_periods=requester_cum_periods,
                           leave_types=leave_types, line_notified=line_notified, today=today)


@staff.route('/leave/requests/approval/info/download')
@login_required
def show_leave_approval_info_download():
    requesters = StaffLeaveApprover.query.filter_by(approver_account_id=current_user.id, is_active=True).all()
    requester_cum_periods = {}
    records = []
    START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
    for requester in requesters:
        cum_periods = defaultdict(float)
        for leave_request in requester.requester.leave_requests:
            if leave_request.cancelled_at is None and leave_request.get_approved:
                if leave_request.start_datetime.date() >= START_FISCAL_DATE.date() and leave_request.end_datetime.date() \
                        <= END_FISCAL_DATE.date():
                    cum_periods[u"{}".format(leave_request.quota.leave_type)] += leave_request.total_leave_days
                    records.append({
                        'name': requester.requester.personal_info.fullname,
                        'leave_type': u"{}".format(leave_request.quota.leave_type)
                    })
        requester_cum_periods[requester] = cum_periods
    df = DataFrame(records)
    summary = df.pivot_table(index='name', columns='leave_type', aggfunc=len, fill_value=0)
    summary.to_excel('leave_summary.xlsx')
    flash(u'ดาวน์โหลดไฟล์เรียบร้อยแล้ว ชื่อไฟล์ leave_summary.xlsx', 'success')
    return send_from_directory(os.getcwd(), 'leave_summary.xlsx')


@staff.route('/api/leave/requests/linenotified')
@login_required
def update_line_notification():
    notified = request.args.get("notified")
    if notified:
        is_notified = True if notified == "true" else False
        for approver in StaffLeaveApprover.query.filter_by(approver_account_id=current_user.id):
            approver.notified_by_line = is_notified
            db.session.add(approver)
        db.session.commit()
        return jsonify({"status": "success"})
    return jsonify({"status": "failed"})


@staff.route('/leave/requests/approval/pending/<int:req_id>')
@login_required
def pending_leave_approval(req_id):
    req = StaffLeaveRequest.query.get(req_id)
    approver = StaffLeaveApprover.query.filter_by(account=current_user, requester=req.staff).first()
    approve = StaffLeaveApproval.query.filter_by(approver=approver, request=req).first()
    approvers = StaffLeaveApproval.query.filter_by(request_id=req_id)
    if approve:
        return render_template('staff/leave_approve_status.html', approve=approve, req=req)
    if req.upload_file_url:
        upload_file = drive.CreateFile({'id': req.upload_file_url})
        upload_file.FetchMetadata()
        upload_file_url = upload_file.get('embedLink')
    else:
        upload_file_url = None
    START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(req.start_datetime)
    used_quota = req.staff.personal_info.get_total_leaves(req.quota.id, tz.localize(START_FISCAL_DATE),
                                                          tz.localize(END_FISCAL_DATE))
    last_req = None
    for last_req in StaffLeaveRequest.query.filter_by(staff_account_id=req.staff_account_id, cancelled_at=None). \
            order_by(desc(StaffLeaveRequest.start_datetime)):
        if last_req.get_approved:
            break

    return render_template('staff/leave_request_pending_approval.html', req=req, approver=approver, approvers=approvers,
                           upload_file_url=upload_file_url, used_quota=used_quota, last_req=last_req)


@staff.route('/leave/requests/approve/<int:req_id>/<int:approver_id>', methods=['GET', 'POST'])
@login_required
def leave_approve(req_id, approver_id):
    approved = request.args.get("approved")
    if request.method == 'POST':
        req = StaffLeaveRequest.query.get(req_id)
        if StaffLeaveApproval.query.filter_by(request_id=req_id, approver_id=approver_id).first():
            flash(u'อนุมัติการลาให้บุคลากรในสังกัดเรียบร้อย หากเปิดบน Line สามารถปิดหน้าต่างนี้ได้ทันที')
        else:
            comment = request.form.get('approval_comment')
            approval = StaffLeaveApproval(
                request_id=req_id,
                approver_id=approver_id,
                is_approved=True if approved == 'yes' else False,
                updated_at=tz.localize(datetime.today()),
                approval_comment=comment if comment != "" else None
            )
            db.session.add(approval)
            db.session.commit()

            req = StaffLeaveRequest.query.filter_by(id=req_id).first()
            START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(req.start_datetime)
            is_used_quota = StaffLeaveUsedQuota.query.filter_by(leave_type_id=req.quota.leave_type_id,
                                                                staff_account_id=req.staff_account_id,
                                                                fiscal_year=END_FISCAL_DATE.year).first()
            if is_used_quota:
                already_approved = StaffLeaveApproval.query.filter_by(request_id=req_id).first()
                if not already_approved:
                    is_used_quota.pending_days = is_used_quota.pending_days - req.total_leave_days
                    db.session.add(is_used_quota)
                    db.session.commit()
            else:
                used_quota = req.staff.personal_info.get_total_leaves(req.quota.id, tz.localize(START_FISCAL_DATE),
                                                                         tz.localize(END_FISCAL_DATE))
                pending_days = req.staff.personal_info.get_total_pending_leaves_request(req.quota.id, tz.localize(
                    START_FISCAL_DATE), tz.localize(END_FISCAL_DATE))

                max_cum_quota = req.staff.personal_info.get_max_cum_quota_per_year(req.quota)
                delta = req.staff.personal_info.get_employ_period()
                if delta.years > 0:
                    if max_cum_quota:
                        is_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=req.staff,
                                                                            leave_type=req.quota.leave_type,
                                                                            fiscal_year=END_FISCAL_DATE.year).first()
                        is_last_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=req.staff,
                                                                                 leave_type=req.quota.leave_type,
                                                                                 fiscal_year=END_FISCAL_DATE.year-1).first()
                        if not is_used_quota:
                            if is_last_used_quota:
                                last_remain_quota = is_last_used_quota.quota_days - is_last_used_quota.used_days
                            else:
                                last_remain_quota = max_cum_quota
                            before_cut_max_quota = last_remain_quota + LEAVE_ANNUAL_QUOTA
                            quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
                        else:
                            quota_limit = is_used_quota.quota_days
                    else:
                        quota_limit = req.quota.max_per_year
                else:
                    quota_limit = req.quota.first_year

                new_used_quota = StaffLeaveUsedQuota(
                    leave_type_id=req.quota.leave_type_id,
                    staff_account_id=req.staff_account_id,
                    fiscal_year=END_FISCAL_DATE.year,
                    used_days=used_quota + pending_days + req.total_leave_days,
                    pending_days=pending_days,
                    quota_days=quota_limit
                )
                db.session.add(new_used_quota)
                db.session.commit()

            flash(u'อนุมัติการลาให้บุคลากรในสังกัดเรียบร้อย หากเปิดบน Line สามารถปิดหน้าต่างนี้ได้ทันที')
            if approval.is_approved is True:
                approve_msg = u'การขออนุมัติ{} ระหว่างวันที่ {} ถึงวันที่ {} ได้รับการอนุมัติโดย {} เรียบร้อยแล้ว รายละเอียดเพิ่มเติม {}' \
                              u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(
                            req.quota.leave_type.type_,
                            req.start_datetime, req.end_datetime,
                            current_user.personal_info.fullname,
                            url_for("staff.show_leave_approval", req_id=req_id, _external=True))
            else:
                approve_msg = u'การขออนุมัติ{} ระหว่างวันที่ {} ถึงวันที่ {} ไม่ได้รับการอนุมัติโดย {} รายละเอียดเพิ่มเติม {}' \
                              u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(
                    req.quota.leave_type.type_,
                    req.start_datetime, req.end_datetime,
                    current_user.personal_info.fullname,
                    url_for("staff.show_leave_approval", req_id=req_id, _external=True))
            if req.notify_to_line and req.staff.line_id:
                if os.environ["FLASK_ENV"] == "production":
                    line_bot_api.push_message(to=req.staff.line_id, messages=TextSendMessage(text=approve_msg))
                else:
                    print(approve_msg, req.staff.id)
            approve_title = u'แจ้งสถานะการอนุมัติ' + req.quota.leave_type.type_
            if os.environ["FLASK_ENV"] == "production":
                send_mail([req.staff.email + "@mahidol.ac.th"], approve_title, approve_msg)
        return redirect(url_for('staff.show_leave_approval_info'))
    if approved is not None:
        return render_template('staff/leave_request_approval_comment.html')
    else:
        return redirect(url_for('staff.pending_leave_approval', req_id=req_id))


@staff.route('/leave/requests/<int:req_id>/approvals')
@login_required
def show_leave_approval(req_id):
    req = StaffLeaveRequest.query.get(req_id)
    approvers = StaffLeaveApprover.query.filter_by(staff_account_id=current_user.id)
    return render_template('staff/leave_approval_status.html', req=req, approvers=approvers)


@staff.route('/leave/requests/<int:req_id>/cancel-approved')
@login_required
def request_cancel_leave_request(req_id):
    req = StaffLeaveRequest.query.get(req_id)
    if req.get_last_cancel_request_from_now > 3 or not req.last_cancel_requested_at:
        req.last_cancel_requested_at = datetime.now(tz)
        db.session.add(req)
        db.session.commit()
        for approval in StaffLeaveApproval.query.filter_by(request_id=req_id):
            serializer = TimedJSONWebSignatureSerializer(app.config.get('SECRET_KEY'), expires_in=259200)
            token = serializer.dumps({'approver_id': approval.approver_id, 'req_id': req.id})
            req_to_cancel_msg = u'{} ยื่นคำขอยกเลิก {} วันที่ {} ถึง {}\nคลิกที่ Link {} เพื่อยกเลิกการลา' \
                                u'\n\n\n หน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'. \
                format(current_user.personal_info.fullname, req.quota.leave_type.type_,
                       req.start_datetime, req.end_datetime, url_for("staff.info_request_cancel_leave_request",
                                                                     token=token, _external=True))
            if approval.approver.notified_by_line and approval.approver.account.line_id:
                if os.environ["FLASK_ENV"] == "production":
                    line_bot_api.push_message(to=approval.approver.account.line_id,
                                              messages=TextSendMessage(text=req_to_cancel_msg))
                else:
                    print(req_to_cancel_msg, approval.approver.account.id)

            req_title = u'แจ้งการขอยกเลิก' + req.quota.leave_type.type_
            if os.environ["FLASK_ENV"] == "production":
                send_mail([approval.approver.account.email + "@mahidol.ac.th"], req_title, req_to_cancel_msg)
            else:
                print(req_to_cancel_msg)
        flash(u'ส่งคำขอยกเลิกการลาของท่านเรียบร้อยแล้ว', 'success')
        return redirect(url_for('staff.request_for_leave_info', quota_id=req.leave_quota_id))
    else:
        flash(u'ไม่สามารถส่งคำขอซ้ำภายใน 3 วันได้', 'warning')
    return redirect(url_for('staff.show_leave_info'))


@staff.route('/leave/requests/cancel-approved/info')
@login_required
def info_request_cancel_leave_request():
    token = request.args.get('token')
    serializer = TimedJSONWebSignatureSerializer(app.config.get('SECRET_KEY'))
    try:
        token_data = serializer.loads(token)
    except:
        return u'Bad JSON Web token. You need a valid token to cancelled leave request. รหัสสำหรับยกเลิกการลา หมดอายุหรือไม่ถูกต้อง'
    req_id = token_data.get("req_id")
    approver_id = token_data.get("approver_id")
    req = StaffLeaveRequest.query.get(req_id)
    approval = StaffLeaveApproval.query.filter_by(approver_id=approver_id).first()
    approvers = StaffLeaveApproval.query.filter_by(request_id=req_id)
    return render_template('staff/leave_request_cancel_request.html', req=req, approval=approval, approvers=approvers)


@staff.route('/leave/requests/<int:req_id>/cancel/by/<int:cancelled_account_id>')
@login_required
def approver_cancel_leave_request(req_id, cancelled_account_id):
    req = StaffLeaveRequest.query.get(req_id)
    req.cancelled_at = tz.localize(datetime.today())
    req.cancelled_account_id = cancelled_account_id
    db.session.add(req)
    db.session.commit()

    _, END_FISCAL_DATE = get_fiscal_date(req.start_datetime)
    is_used_quota = StaffLeaveUsedQuota.query.filter_by(leave_type_id=req.quota.leave_type_id,
                                                        staff_account_id=req.staff_account_id,
                                                        fiscal_year=END_FISCAL_DATE.year).first()
    quota = req.quota
    used_quota = req.staff.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
                                                             tz.localize(END_FISCAL_DATE))
    pending_days = req.staff.personal_info.get_total_pending_leaves_request \
        (quota.id, tz.localize(START_FISCAL_DATE), tz.localize(END_FISCAL_DATE))
    delta = req.staff.personal_info.get_employ_period()
    max_cum_quota = req.staff.personal_info.get_max_cum_quota_per_year(quota)

    if delta.years > 0:
        if max_cum_quota:
            is_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=req.staff,
                                                                leave_type=req.quota.leave_type,
                                                                fiscal_year=END_FISCAL_DATE.year).first()
            is_last_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=req.staff,
                                                                     leave_type=req.quota.leave_type,
                                                                     fiscal_year=END_FISCAL_DATE.year - 1).first()
            if not is_used_quota:
                if is_last_used_quota:
                    last_remain_quota = is_last_used_quota.quota_days - is_last_used_quota.used_days
                else:
                    last_remain_quota = max_cum_quota
                before_cut_max_quota = last_remain_quota + LEAVE_ANNUAL_QUOTA
                quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
            else:
                quota_limit = is_used_quota.quota_days
        else:
            quota_limit = quota.max_per_year

    else:
        quota_limit = req.quota.first_year

    if is_used_quota:
        new_used=is_used_quota.used_days-req.total_leave_days
        is_used_quota.used_days = new_used
        is_used_quota.pending_days = is_used_quota.pending_days-req.total_leave_days
        db.session.add(is_used_quota)
        db.session.commit()
    else:
        new_used_quota = StaffLeaveUsedQuota(
            leave_type_id=req.quota.leave_type_id,
            staff_account_id=req.staff_account_id,
            fiscal_year=END_FISCAL_DATE.year,
            used_days=used_quota,
            pending_days=pending_days,
            quota_days=quota_limit
        )
        db.session.add(new_used_quota)
        db.session.commit()

    cancelled_msg = u'คำขออนุมัติ{} วันที่ {} ถึง {} ถูกยกเลิกโดย {} เรียบร้อยแล้ว' \
                    u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(req.quota.leave_type.type_,
                                                                                          req.start_datetime,
                                                                                          req.end_datetime,
                                                                                          req.cancelled_by.personal_info
                                                                                          , _external=True)
    if req.notify_to_line and req.staff.line_id:
        if os.environ["FLASK_ENV"] == "production":
            line_bot_api.push_message(to=req.staff.line_id, messages=TextSendMessage(text=cancelled_msg))
        else:
            print(cancelled_msg, req.staff.id)
    cancelled_title = u'แจ้งยกเลิกการขอ' + req.quota.leave_type.type_ + u'โดยผู้บังคับบัญชา'
    if os.environ["FLASK_ENV"] == "production":
        send_mail([req.staff.email + "@mahidol.ac.th"], cancelled_title, cancelled_msg)
    return redirect(request.referrer)


@staff.route('/leave/requests/<int:req_id>/cancel/<int:cancelled_account_id>')
@login_required
def cancel_leave_request(req_id, cancelled_account_id):
    req = StaffLeaveRequest.query.get(req_id)
    req.cancelled_at = tz.localize(datetime.today())
    req.cancelled_account_id = cancelled_account_id
    db.session.add(req)
    db.session.commit()

    _, END_FISCAL_DATE = get_fiscal_date(req.start_datetime)

    quota = req.quota
    used_quota = current_user.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
                                                             tz.localize(END_FISCAL_DATE))
    pending_days = current_user.personal_info.get_total_pending_leaves_request \
        (quota.id, tz.localize(START_FISCAL_DATE), tz.localize(END_FISCAL_DATE))
    delta = current_user.personal_info.get_employ_period()
    max_cum_quota = current_user.personal_info.get_max_cum_quota_per_year(quota)

    if delta.years > 0:
        if max_cum_quota:
            is_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=req.staff,
                                                                leave_type=req.quota.leave_type,
                                                                fiscal_year=END_FISCAL_DATE.year).first()
            is_last_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=req.staff,
                                                                     leave_type=req.quota.leave_type,
                                                                     fiscal_year=END_FISCAL_DATE.year - 1).first()
            if not is_used_quota:
                if is_last_used_quota:
                    last_remain_quota = is_last_used_quota.quota_days - is_last_used_quota.used_days
                else:
                    last_remain_quota = max_cum_quota
                before_cut_max_quota = last_remain_quota + LEAVE_ANNUAL_QUOTA
                quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
            else:
                quota_limit = is_used_quota.quota_days
        else:
            quota_limit = quota.max_per_year
    else:
        quota_limit = req.quota.first_year

    is_used_quota = StaffLeaveUsedQuota.query.filter_by(leave_type_id=req.quota.leave_type_id,
                                                        staff_account_id=req.staff_account_id,
                                                        fiscal_year=END_FISCAL_DATE.year).first()
    if is_used_quota:
        new_used=is_used_quota.used_days-req.total_leave_days
        is_used_quota.used_days = new_used
        is_used_quota.pending_days = is_used_quota.pending_days - req.total_leave_days
        db.session.add(is_used_quota)
        db.session.commit()
    else:
        new_used_quota = StaffLeaveUsedQuota(
            leave_type_id=req.quota.leave_type_id,
            staff_account_id=current_user.id,
            fiscal_year=END_FISCAL_DATE.year,
            used_days=used_quota,
            pending_days=pending_days,
            quota_days=quota_limit
        )
        db.session.add(new_used_quota)
        db.session.commit()


    cancelled_msg = u'การขออนุมัติ{} วันที่ {} ถึง {} ถูกยกเลิกโดย {} เรียบร้อยแล้ว' \
                    u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(req.quota.leave_type.type_,
                                                                                          req.start_datetime,
                                                                                          req.end_datetime,
                                                                                          current_user.personal_info.fullname
                                                                                          , _external=True)
    if req.notify_to_line and req.staff.line_id:
        if os.environ["FLASK_ENV"] == "production":
            line_bot_api.push_message(to=req.staff.line_id, messages=TextSendMessage(text=cancelled_msg))
        else:
            print(cancelled_msg, req.staff.id)
    cancelled_title = u'แจ้งยกเลิกการขอ' + req.quota.leave_type.type_
    if os.environ["FLASK_ENV"] == "production":
        send_mail([req.staff.email + "@mahidol.ac.th"], cancelled_title, cancelled_msg)
    return redirect(request.referrer)


@staff.route('/leave/requests/approved/info/<int:requester_id>')
@login_required
def show_leave_approval_info_each_person(requester_id):
    requester = StaffLeaveRequest.query.filter_by(staff_account_id=requester_id).all()
    return render_template('staff/leave_request_approved_each_person.html', requester=requester)


@staff.route('leave/<int:request_id>/record/info')
@login_required
def record_each_request_leave_request(request_id):
    req = StaffLeaveRequest.query.get(request_id)
    approvers = StaffLeaveApproval.query.filter_by(request_id=request_id)
    if req.upload_file_url:
        upload_file = drive.CreateFile({'id': req.upload_file_url})
        upload_file.FetchMetadata()
        upload_file_url = upload_file.get('embedLink')
    else:
        upload_file_url = None
    all_hr = StaffSpecialGroup.query.filter_by(group_code='hr').first()
    for hr in all_hr.staffs:
        is_hr = True if hr.id == current_user.id else False
    return render_template('staff/leave_record_info.html', req=req, approvers=approvers,
                           upload_file_url=upload_file_url, is_hr=is_hr)


@staff.route('/leave/requests/search')
@login_required
def search_leave_request_info():
    reqs = StaffLeaveRequest.query.filter(StaffLeaveRequest.cancelled_at == None).all()
    record_schema = StaffLeaveRequestSchema(many=True)
    return jsonify(record_schema.dump(reqs).data)


@staff.route('/leave/requests')
@login_required
def leave_request_info():
    return render_template('staff/leave_request_info.html')


@staff.route('/wfh/requests/search')
@login_required
def search_wfh_request_info():
    reqs = StaffWorkFromHomeRequest.query.all()
    record_schema = StaffWorkFromHomeRequestSchema(many=True)
    return jsonify(record_schema.dump(reqs).data)


@staff.route('/wfh/requests')
@login_required
def wfh_request_info():
    return render_template('staff/wfh_list.html')


@staff.route('/leave/requests/result-by-date',
             methods=['GET', 'POST'])
@login_required
def leave_request_result_by_date():
    if request.method == 'POST':
        form = request.form
        start_dt, end_dt = form.get('dates').split(' - ')
        start_date = datetime.strptime(start_dt, '%d/%m/%Y')
        end_date = datetime.strptime(end_dt, '%d/%m/%Y')

        leaves = StaffLeaveRequest.query.filter(and_(StaffLeaveRequest.start_datetime >= start_date,
                                                     StaffLeaveRequest.end_datetime <= end_date))
        return render_template('staff/leave_request_result_by_date.html', leaves=leaves,
                               start_date=start_date.date(), end_date=end_date.date())
    else:
        return render_template('staff/leave_request_info_by_date.html')


@staff.route('/leave/requests/result-by-person',
             methods=['GET', 'POST'])
@login_required
def leave_request_result_by_person():
    org_id = request.args.get('deptid')
    fiscal_year = request.args.get('fiscal_year')
    if fiscal_year is not None:
        start_date, end_date = get_start_end_date_for_fiscal_year(int(fiscal_year))
    else:
        start_date = None
        end_date = None
    years = set()
    leaves_list = []
    departments = Org.query.all()
    leave_types = [t.type_ for t in StaffLeaveType.query.all()]
    leave_types_r = [t.type_ + u'คงเหลือ' for t in StaffLeaveType.query.all()]
    if org_id is None:
        account_query = StaffAccount.query.all()
    else:
        account_query = StaffAccount.query.filter(StaffAccount.personal_info.has(org_id=org_id)) \
                                          .filter(or_(StaffAccount.personal_info.has(retired=False),
                                                      StaffAccount.personal_info.has(retired=None)))
    for account in account_query:
        # record = account.personal_info.get_remaining_leave_day
        record = {}
        record["staffid"] = account.id
        record["fullname"] = account.personal_info.fullname
        record["total"] = 0
        record["pending"] = 0
        if account.personal_info.org:
            record["org"] = account.personal_info.org.name
        else:
            record["org"] = ""
        for leave_type in leave_types:
            record[leave_type] = 0
        for leave_remain in leave_types_r:
            record[leave_remain] = 0
        quota = StaffLeaveQuota.query.filter_by(employment_id=account.personal_info.employment_id).all()
        #ค่ามันไม่ใส่ตรงตามช่อง เช่น pending ไปใส่ใน total ค่า total บางคนครบ3 type
        for quota in quota:
           leave_type = quota.leave_type.type_
           leave_remain = quota.leave_type.type_
           if fiscal_year:
               used_quota = StaffLeaveUsedQuota.query.filter_by(staff=account,leave_type_id=quota.leave_type_id,
                                                                fiscal_year=fiscal_year).first()
               if used_quota:
                   record[leave_remain] = used_quota.quota_days - used_quota.used_days
                   record[leave_type] = used_quota.used_days
                   record["total"] += used_quota.used_days
                   record["pending"] += used_quota.pending_days
               else:
                   record["total"] = 0
                   record["pending"] = 0
                   record[leave_type] = 0
                   record[leave_remain] = 0
           else:
               _, END_FISCAL_DATE = get_fiscal_date(datetime.today())
               used_quota = StaffLeaveUsedQuota.query.filter_by(staff=account,
                                                                leave_type_id=quota.leave_type_id,
                                                                fiscal_year=END_FISCAL_DATE.year).first()
               if used_quota:
                   record["total"] += used_quota.used_days
                   record["pending"] += used_quota.pending_days
                   record[leave_type] = used_quota.used_days
                   record[leave_remain] = used_quota.quota_days - used_quota.used_days
               else:
                   record["total"] = 0
                   record["pending"] = 0
                   record[leave_type] = 0
                   record[leave_remain] = 0
        for req in account.leave_requests:
            years.add(req.start_datetime.year)
        # for req in account.leave_requests:
        #     if not req.cancelled_at:
        #         if req.get_approved:
        #             years.add(req.start_datetime.year)
        #             if start_date and end_date:
        #                 if req.start_datetime.date() < start_date or req.start_datetime.date() > end_date:
        #                     continue
        #             leave_type = req.quota.leave_type.type_
        #             record[leave_type] = record.get(leave_type, 0) + req.total_leave_days
        #             record["total"] += req.total_leave_days
        #         if not req.get_approved and not req.get_unapproved:
        #             record["pending"] += req.total_leave_days
        leaves_list.append(record)
    years = sorted(years)
    if len(years) > 0:
        years.append(years[-1] + 1)
        years.insert(0, years[0] - 1)
    return render_template('staff/leave_request_by_person.html', leave_types=leave_types, leave_types_r=leave_types_r,
                           sel_dept=org_id, year=fiscal_year,
                           leaves_list=leaves_list, departments=[{'id': d.id, 'name': d.name}
                                                                 for d in departments], years=years)


@staff.route('leave/requests/result-by-person/<int:requester_id>')
@login_required
def leave_request_by_person_detail(requester_id):
    requester = StaffLeaveRequest.query.filter_by(staff_account_id=requester_id)
    # quota = StaffLeaveQuota.query.get(quota_id)
    # used_quota = current_user.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
    #                                                          tz.localize(END_FISCAL_DATE))
    #
    # delta = current_user.personal_info.get_employ_period_of_current_fiscal_year()
    # max_cum_quota = current_user.personal_info.get_max_cum_quota_per_year(quota)
    # if delta.years > 0:
    #     if max_cum_quota:
    #         last_quota = StaffLeaveRemainQuota.query.filter(and_
    #                                                         (StaffLeaveRemainQuota.leave_quota_id == quota.id,
    #                                                          StaffLeaveRemainQuota.year == (START_FISCAL_DATE.year - 1),
    #                                                          StaffLeaveRemainQuota.staff_account_id == current_user.id)).first()
    #         if last_quota:
    #             last_year_quota = last_quota.last_year_quota
    #         else:
    #             last_year_quota = 0
    #         before_cut_max_quota = last_year_quota + LEAVE_ANNUAL_QUOTA
    #         quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
    #     else:
    #         quota_limit = quota.max_per_year
    # else:
    #     quota_limit = quota.first_year
    return render_template('staff/leave_request_by_person_detail.html', requester=requester,
                           START_FISCAL_DATE=START_FISCAL_DATE, END_FISCAL_DATE=END_FISCAL_DATE)


@staff.route('/wfh')
@login_required
def show_work_from_home():
    START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
    category = request.args.get('category', 'pending')
    wfh_list = []
    if category == 'pending':
        for wfh in current_user.wfh_requests:
            if wfh.start_datetime >= tz.localize(START_FISCAL_DATE) and wfh.end_datetime <= tz.localize(END_FISCAL_DATE) \
                    and not wfh.cancelled_at:
                if not wfh.get_approved:
                    if not wfh.get_unapproved:
                        wfh_list.append(wfh)
    elif category == 'approved':
        for wfh in current_user.wfh_requests:
            if wfh.get_approved:
                if not wfh.cancelled_at:
                    wfh_list.append(wfh)
    elif category == 'rejected':
        for wfh in current_user.wfh_requests:
            if wfh.get_unapproved:
                if not wfh.cancelled_at:
                    wfh_list.append(wfh)
    approver = StaffWorkFromHomeApprover.query.filter_by(approver_account_id=current_user.id).first()
    return render_template('staff/wfh_info.html', category=category, wfh_list=wfh_list, approver=approver)


@staff.route('/wfh/others-records')
@login_required
def show_work_from_home_others_records():
    START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
    wfh_history = []
    for wfh in current_user.wfh_requests:
        if wfh.start_datetime >= tz.localize(START_FISCAL_DATE) and wfh.end_datetime < tz.localize(END_FISCAL_DATE) and wfh.cancelled_at is None:
            wfh_history.append(wfh)

    wfh_cancelled_list = []
    for wfh in current_user.wfh_requests:
        if wfh.cancelled_at:
            wfh_cancelled_list.append(wfh)
    return render_template('staff/wfh_info_others_records.html', wfh_history=wfh_history, wfh_cancelled_list=wfh_cancelled_list)


@staff.route('/wfh/request', methods=['GET', 'POST'])
@login_required
def request_work_from_home():
    if request.method == 'POST':
        form = request.form
        start_t = "08:30"
        end_t = "16:30"
        start_d, end_d = form.get('dates').split(' - ')
        start_dt = '{} {}'.format(start_d, start_t)
        end_dt = '{} {}'.format(end_d, end_t)
        start_datetime = datetime.strptime(start_dt, '%d/%m/%Y %H:%M')
        end_datetime = datetime.strptime(end_dt, '%d/%m/%Y %H:%M')
        req = StaffWorkFromHomeRequest(
            staff=current_user,
            start_datetime=tz.localize(start_datetime),
            end_datetime=tz.localize(end_datetime),
            detail=form.get('detail'),
            contact_phone=form.get('contact_phone')
        )
        if form.getlist('notified_by_line'):
            req.notify_to_line = True
        db.session.add(req)
        db.session.commit()

        mails = []
        req_title = u'ทดสอบแจ้งการขออนุมัติ WFH'
        req_msg = u'{} ขออนุมัติ{} ระหว่างวันที่ {} ถึงวันที่ {}\nคลิกที่ Link เพื่อดูรายละเอียดเพิ่มเติม {} ' \
                  u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'. \
            format(current_user.personal_info.fullname, req.detail,
                   start_datetime, end_datetime,
                   url_for("staff.pending_wfh_request_for_approval", req_id=req.id, _external=True))

        # if no approvers assigned, assign the head of the unit as a designated approver
        if len(current_user.wfh_requesters) == 0:
            print('no approver found, assign head of the organization')
            org_head = StaffAccount.query.filter_by(email=current_user.personal_info.org.head).first()
            approver = StaffWorkFromHomeApprover(requester=current_user, account=org_head)
            db.session.add(approver)
            db.session.commit()

        for approver in current_user.wfh_requesters:
            if approver.is_active:
                if approver.notified_by_line and approver.account.line_id:
                    if os.environ["FLASK_ENV"] == "production":
                        line_bot_api.push_message(to=approver.account.line_id,
                                                  messages=TextSendMessage(text=req_msg))
                    else:
                        print(req_msg, approver.account.id)
                mails.append(approver.account.email + "@mahidol.ac.th")
        if os.environ["FLASK_ENV"] == "production":
            send_mail(mails, req_title, req_msg)
        else:
            print([approver.account.email + 'mahidol.ac.th'], req_title, req_msg)

        flash(u'ส่งคำขอของท่านเรียบร้อยแล้ว (The request has been sent.)', 'success')
        return redirect(url_for('staff.show_work_from_home'))
    else:
        return render_template('staff/wfh_request.html')


@staff.route('/wfh/request/<int:request_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_request_work_from_home(request_id):
    req = StaffWorkFromHomeRequest.query.get(request_id)
    if request.method == 'POST':
        start_t = "08:30"
        end_t = "16:30"
        start_d, end_d = request.form.get('dates').split(' - ')
        start_dt = '{} {}'.format(start_d, start_t)
        end_dt = '{} {}'.format(end_d, end_t)
        start_datetime = datetime.strptime(start_dt, '%d/%m/%Y %H:%M')
        end_datetime = datetime.strptime(end_dt, '%d/%m/%Y %H:%M')
        req.start_datetime = tz.localize(start_datetime),
        req.end_datetime = tz.localize(end_datetime),
        req.detail = request.form.get('detail'),
        req.contact_phone = request.form.get('contact_phone')
        db.session.add(req)
        db.session.commit()
        return redirect(url_for('staff.show_work_from_home'))

    selected_dates = [req.start_datetime, req.end_datetime]
    return render_template('staff/edit_wfh_request.html', req=req, selected_dates=selected_dates)


@staff.route('/wfh/request/<int:request_id>/cancel')
@login_required
def cancel_wfh_request(request_id):
    req = StaffWorkFromHomeRequest.query.get(request_id)
    req.cancelled_at = tz.localize(datetime.today())
    db.session.add(req)
    db.session.commit()
    return redirect(request.referrer)


@staff.route('/wfh/<int:request_id>/info',
             methods=['GET', 'POST'])
@login_required
def wfh_show_request_info(request_id):
    if request.method == 'POST':
        form = request.form
        req = StaffWorkFromHomeJobDetail(
            wfh_id=request_id,
            activity=form.get('activity')
        )
        db.session.add(req)
        db.session.commit()
        wfhreq = StaffWorkFromHomeRequest.query.get(request_id)
        detail = StaffWorkFromHomeJobDetail.query.filter_by(wfh_id=request_id)
        return render_template('staff/wfh_request_job_details.html', wfhreq=wfhreq, detail=detail)
    else:
        check = StaffWorkFromHomeCheckedJob.query.filter_by(request_id=request_id).first()
        if check:
            return redirect(url_for("staff.record_each_request_wfh_request", request_id=request_id))
        else:
            wfhreq = StaffWorkFromHomeRequest.query.get(request_id)
            detail = StaffWorkFromHomeJobDetail.query.filter_by(wfh_id=request_id)
            return render_template('staff/wfh_request_job_details.html', wfhreq=wfhreq, detail=detail)


@staff.route('/wfh/requests/approval')
@login_required
def show_wfh_requests_for_approval():
    approvers = StaffWorkFromHomeApprover.query.filter_by(approver_account_id=current_user.id).all()
    checkjob = StaffWorkFromHomeCheckedJob.query.all()
    return render_template('staff/wfh_requests_approval_info.html', approvers=approvers, checkjob=checkjob)


@staff.route('/wfh/requests/approval/pending/<int:req_id>')
@login_required
def pending_wfh_request_for_approval(req_id):
    req = StaffWorkFromHomeRequest.query.get(req_id)
    approver = StaffWorkFromHomeApprover.query.filter_by(account=current_user, requester=req.staff).first()
    approve = StaffWorkFromHomeApproval.query.filter_by(approver=approver, request=req).first()
    if approve:
        return render_template('staff/wfh_record_info_each_request.html', req=req, approver=approver)
    return render_template('staff/wfh_request_pending_approval.html', req=req, approver=approver)


@staff.route('/wfh/requests/approve/<int:req_id>/<int:approver_id>', methods=['GET', 'POST'])
@login_required
def wfh_approve(req_id, approver_id):
    approved = request.args.get("approved")
    if request.method == 'POST':
        comment = request.form.get('approval_comment')
        approval = StaffWorkFromHomeApproval(
            request_id=req_id,
            approver_id=approver_id,
            updated_at=tz.localize(datetime.today()),
            is_approved=True if approved == 'yes' else False,
            approval_comment=comment if comment != "" else None
        )
        db.session.add(approval)
        db.session.commit()
        flash(u'อนุมัติ WFH ให้บุคลากรในสังกัดเรียบร้อย หากเปิดบน Line สามารถปิดหน้าต่างนี้ได้ทันที', 'success')

        req = StaffWorkFromHomeRequest.query.get(req_id)
        if approval.is_approved is True:
            approve_msg = u'การขออนุมัติWFHเรื่อง {} ได้รับการอนุมัติโดย {} เรียบร้อยแล้ว รายละเอียดเพิ่มเติม {}' \
                            .format(req.detail, current_user.personal_info.fullname,
                                    url_for("staff.show_wfh_approval", request_id=req_id, _external=True))
        else:
            approve_msg = u'การขออนุมัติ WFH เรื่อง {} ไม่ได้รับการอนุมัติโดย {} รายละเอียดเพิ่มเติม {}' \
                            .format(req.detail, current_user.personal_info.fullname,
                                    url_for("staff.show_wfh_approval", request_id=req_id, _external=True))
        if req.notify_to_line and req.staff.line_id:
            if os.environ["FLASK_ENV"] == "production":
                line_bot_api.push_message(to=req.staff.line_id, messages=TextSendMessage(text=approve_msg))
            else:
                print(approve_msg, req.staff.id)
        approve_title = u'แจ้งสถานะการอนุมัติ WFH'
        if os.environ["FLASK_ENV"] == "production":
            send_mail([req.staff.email + "@mahidol.ac.th"], approve_title, approve_msg)
        else:
            print([req.staff.email + "@mahidol.ac.th"], approve_title, approve_msg)
        return redirect(url_for('staff.show_wfh_requests_for_approval'))
    if approved is not None:
        return render_template('staff/wfh_request_pending_approval_comment.html')
    else:
        return redirect(url_for('staff.pending_wfh_request_for_approval', req_id=req_id))


@staff.route('/wfh/requests/approved/list/<int:requester_id>')
@login_required
def show_wfh_approved_list_each_person(requester_id):
    requester = StaffWorkFromHomeRequest.query.filter_by(staff_account_id=requester_id)

    return render_template('staff/wfh_all_approved_list_each_person.html', requester=requester)


@staff.route('/wfh/requests/<int:request_id>/approvals')
@login_required
def show_wfh_approval(request_id):
    req = StaffWorkFromHomeRequest.query.get(request_id)
    approvers = StaffWorkFromHomeApprover.query.filter_by(staff_account_id=current_user.id)
    return render_template('staff/wfh_approval_status.html', req=req, approvers=approvers)

#Deleted
# @staff.route('/wfh/<int:request_id>/info/edit-detail/<detail_id>',methods=['GET', 'POST'])
# @login_required
# def edit_wfh_job_detail(request_id, detail_id):
#     detail = StaffWorkFromHomeJobDetail.query.get(detail_id)
#     if request.method == 'POST':
#         detail.activity = request.form.get('activity')
#         db.session.add(detail)
#         db.session.commit()
#         return redirect(url_for('staff.wfh_show_request_info', request_id=request_id))
#     detail = StaffWorkFromHomeJobDetail.query.get(detail_id)
#     return render_template('staff/edit_wfh_job_detail.html', detail=detail, request_id=request_id)
#
#
# @staff.route('/wfh/<int:request_id>/info/finish-job-detail/<detail_id>')
# @login_required
# def finish_wfh_job_detail(request_id, detail_id):
#     detail = StaffWorkFromHomeJobDetail.query.get(detail_id)
#     if detail:
#         detail.status = True
#         db.session.add(detail)
#         db.session.commit()
#         return redirect(url_for('staff.wfh_show_request_info', request_id=request_id))
#
#
# @staff.route('/wfh/info/cancel-job-detail/<detail_id>')
# @login_required
# def cancel_wfh_job_detail(detail_id):
#     detail = StaffWorkFromHomeJobDetail.query.get(detail_id)
#     if detail:
#         db.session.delete(detail)
#         db.session.commit()
#         return redirect(url_for('staff.wfh_show_request_info', request_id=detail.wfh_id))
#
#
# @staff.route('/wfh/<int:request_id>/info/unfinish-job-detail/<detail_id>')
# @login_required
# def unfinish_wfh_job_detail(request_id, detail_id):
#     detail = StaffWorkFromHomeJobDetail.query.get(detail_id)
#     if detail:
#         detail.status = False
#         db.session.add(detail)
#         db.session.commit()
#         return redirect(url_for('staff.wfh_show_request_info', request_id=request_id))


# @staff.route('/wfh/<int:request_id>/info/add-overall-result',
#              methods=['GET', 'POST'])
# @login_required
# def add_overall_result_work_from_home(request_id):
#     if request.method == 'POST':
#         form = request.form
#         result = StaffWorkFromHomeCheckedJob(
#             overall_result=form.get('overall_result'),
#             finished_at=tz.localize(datetime.today()),
#             request_id=request_id
#         )
#         db.session.add(result)
#         db.session.commit()
#         wfhreq = StaffWorkFromHomeRequest.query.get(request_id)
#         detail = StaffWorkFromHomeJobDetail.query.filter_by(wfh_id=request_id)
#         check = StaffWorkFromHomeCheckedJob.query.filter_by(request_id=request_id)
#         return render_template('staff/wfh_record_info_each_request_subordinate.html',
#                                req=wfhreq, job_detail=detail, checkjob=check)
#
#     else:
#         wfhreq = StaffWorkFromHomeRequest.query.get(request_id)
#         detail = StaffWorkFromHomeJobDetail.query.filter_by(wfh_id=request_id)
#         return render_template('staff/wfh_add_overall_result.html', wfhreq=wfhreq, detail=detail)


# @staff.route('wfh/<int:request_id>/check/<int:check_id>',
#              methods=['GET', 'POST'])
# @login_required
# def comment_wfh_request(request_id, check_id):
#     checkjob = StaffWorkFromHomeCheckedJob.query.get(check_id)
#     approval = StaffWorkFromHomeApproval.query.filter(and_(StaffWorkFromHomeApproval.request_id == request_id,
#                                                            StaffWorkFromHomeApproval.approver.has(
#                                                                account=current_user))).first()
#     if request.method == 'POST':
#         checkjob.id = check_id,
#         if not approval.approval_comment:
#             approval.approval_comment = request.form.get('approval_comment')
#         else:
#             approval.approval_comment += "," + request.form.get('approval_comment')
#         approval.checked_at = tz.localize(datetime.today())
#         db.session.add(checkjob)
#         db.session.commit()
#         return redirect(url_for('staff.show_wfh_requests_for_approval'))
#
#     else:
#         req = StaffWorkFromHomeRequest.query.get(request_id)
#         job_detail = StaffWorkFromHomeJobDetail.query.filter_by(wfh_id=request_id)
#         check = StaffWorkFromHomeCheckedJob.query.filter_by(id=check_id)
#         return render_template('staff/wfh_approval_comment.html', req=req, job_detail=job_detail,
#                                checkjob=check)


@staff.route('wfh/<int:request_id>/record/info',
             methods=['GET', 'POST'])
@login_required
def record_each_request_wfh_request(request_id):
    req = StaffWorkFromHomeRequest.query.get(request_id)
    job_detail = StaffWorkFromHomeJobDetail.query.filter_by(wfh_id=request_id)
    check = StaffWorkFromHomeCheckedJob.query.filter_by(request_id=request_id)
    return render_template('staff/wfh_record_info_each_request.html', req=req, job_detail=job_detail,
                           checkjob=check)


@staff.route('/wfh/requests/list', methods=['GET', 'POST'])
@login_required
def wfh_requests_list():
    if request.method == 'POST':
        form = request.form
        start_dt, end_dt = form.get('dates').split(' - ')
        start_date = datetime.strptime(start_dt, '%d/%m/%Y')
        end_date = datetime.strptime(end_dt, '%d/%m/%Y')

        wfh_request = StaffWorkFromHomeRequest.query.filter(and_(StaffWorkFromHomeRequest.start_datetime >= start_date,
                                                                 StaffWorkFromHomeRequest.end_datetime <= end_date))
        return render_template('staff/wfh_request_result_by_date.html', request=wfh_request,
                               start_date=start_date.date(), end_date=end_date.date())
    else:
        return render_template('staff/wfh_request_info_by_date.html')


@staff.route('/for-hr')
@hr_permission.require()
@login_required
def for_hr():
    return render_template('staff/for_hr.html')


@staff.route('/api/for-hr/login-report')
@hr_permission.require()
@login_required
def get_hr_login_summary_report_data():
    description = {'date': ("date", "Day"), 'heads': ("number", "heads")}
    data = defaultdict(int)
    START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
    for rec in StaffWorkLogin.query.filter(StaffWorkLogin.start_datetime.between(START_FISCAL_DATE, END_FISCAL_DATE)):
        data[rec.start_datetime.date()] += 1

    count_data = []
    for date, heads in data.iteritems():
        count_data.append({
            'date': date,
            'heads': heads
        })

    data_table = gviz_api.DataTable(description)
    data_table.LoadData(count_data)
    return data_table.ToJSon(columns_order=('date', 'heads'))


@staff.route('/api/for-hr/wfh-report')
@hr_permission.require()
@login_required
def get_hr_wfh_summary_report_data():
    description = {'date': ("date", "Day"), 'heads': ("number", "heads")}
    data = defaultdict(int)
    START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
    for rec in StaffWorkFromHomeRequest.query\
            .filter(StaffWorkFromHomeRequest.start_datetime.between(START_FISCAL_DATE, END_FISCAL_DATE)):
        if not rec.cancelled_at and rec.get_unapproved:
            data[rec.start_datetime.date()] += 1

    count_data = []
    for date, heads in data.iteritems():
        count_data.append({
            'date': date,
            'heads': heads
        })

    data_table = gviz_api.DataTable(description)
    data_table.LoadData(count_data)
    return data_table.ToJSon(columns_order=('date', 'heads'))


@staff.route('/api/for-hr/leave-report')
@hr_permission.require()
@login_required
def get_hr_leave_summary_report_data():
    description = {'date': ("date", "Day"), 'heads': ("number", "heads")}
    data = defaultdict(int)
    START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
    for rec in StaffLeaveRequest.query\
            .filter(StaffLeaveRequest.start_datetime.between(START_FISCAL_DATE, END_FISCAL_DATE)):
        if not rec.cancelled_at and not rec.get_unapproved:
            data[rec.start_datetime.date()] += 1

    count_data = []
    for date, heads in data.iteritems():
        count_data.append({
            'date': date,
            'heads': heads
        })

    data_table = gviz_api.DataTable(description)
    data_table.LoadData(count_data)
    return data_table.ToJSon(columns_order=('date', 'heads'))


@staff.route('/api/for-hr/login-time')
@hr_permission.require()
@login_required
def get_hr_login_time_data():
    description = {'timeofday': ("timeofday", "Time"), 'heads': ("number", "heads")}
    data = defaultdict(int)
    for rec in StaffWorkLogin.query.all():
        start_datetime = rec.start_datetime.astimezone(tz)
        data[(start_datetime.hour, start_datetime.minute, 0)] += 1

    count_data = []
    for tod, heads in data.iteritems():
        count_data.append({
            'timeofday': list(tod),
            'heads': heads
        })

    data_table = gviz_api.DataTable(description)
    data_table.LoadData(count_data)
    return data_table.ToJSon()


@staff.route('/for-hr/login-report')
@hr_permission.require()
@login_required
def hr_login_summary_report():
    return render_template('staff/hr_login_summary_report.html')


@staff.route('/login-scan', methods=['GET', 'POST'])
@csrf.exempt
@admin_permission.require()
@login_required
def login_scan():
    office_starttime = '09:00'
    office_endtime = '16:30'
    DATETIME_FORMAT = '%d/%m/%Y %H:%M:%S'

    if request.method == 'POST':
        req_data = request.get_json()
        lat = req_data['data'].get('lat', '0.0')
        long = req_data['data'].get('long', '0.0')
        th_name = req_data['data'].get('thName')
        en_name = req_data['data'].get('enName')
        qrcode_exp_datetime = datetime.strptime(req_data['data'].get('qrCodeExpDateTime'), DATETIME_FORMAT)
        qrcode_exp_datetime = qrcode_exp_datetime.replace(tzinfo=tz)
        if th_name:
            name = th_name.split(' ')
            # some lastnames contain spaces
            fname, lname = name[0], ' '.join(name[1:])
            lname = lname.lstrip()
            person = StaffPersonalInfo.query \
                .filter_by(th_firstname=fname, th_lastname=lname).first()
        elif en_name:
            fname, lname = en_name.split(' ')
            lname = lname.lstrip()
            person = StaffPersonalInfo.query \
                .filter_by(en_firstname=fname, en_lastname=lname).first()
        else:
            return jsonify({'message': 'The QR Code is not valid.'}), 400

        if person:
            now = datetime.now(pytz.utc)
            date_id = StaffWorkLogin.generate_date_id(now.astimezone(tz))
            record = StaffWorkLogin.query \
                .filter_by(date_id=date_id, staff=person.staff_account).first()
            # office_startdt = datetime.strptime(u'{} {}'.format(now.date(), office_starttime), DATETIME_FORMAT)
            # office_startdt = office_startdt.replace(tzinfo=pytz.utc)
            # office_enddt = datetime.strptime(u'{} {}'.format(now.date(), office_endtime), DATETIME_FORMAT)
            # office_enddt = office_enddt.replace(tzinfo=pytz.utc)

            # use the first login of the day as the checkin time.
            # use the last login of the day as the checkout time.
            if not record:
                num_scans = 1
                record = StaffWorkLogin(
                    date_id=date_id,
                    staff=person.staff_account,
                    lat=float(lat),
                    long=float(long),
                    start_datetime=now,
                    num_scans=num_scans,
                    qrcode_in_exp_datetime=qrcode_exp_datetime.astimezone(pytz.utc)
                )
                activity = 'checked in'
            else:
                # status = "Late" if morning > 0 else "On time"
                num_scans = record.num_scans + 1 if record.num_scans else 1
                record.qrcode_out_exp_datetime = qrcode_exp_datetime.astimezone(pytz.utc)
                record.end_datetime = now
                record.num_scans = num_scans
                activity = 'checked out'
            db.session.add(record)
            db.session.commit()
            return jsonify(
                {'message': 'success', 'activity': activity, 'name': person.fullname, 'time': now.isoformat(),
                 'numScans': num_scans})
        else:
            return jsonify({'message': u'The staff with the name {} not found.'.format(fname + ' ' + lname)}), 404

    return render_template('staff/login_scan.html')


@staff.route('/login-activity-scan/<int:seminar_id>', methods=['GET', 'POST'])
@csrf.exempt
@hr_permission.require()
@login_required
def checkin_activity(seminar_id):
    seminar = StaffSeminar.query.get(seminar_id)
    if request.method == 'POST':
        req_data = request.get_json()
        th_name = req_data['data'].get('thName')
        en_name = req_data['data'].get('enName')
        if th_name:
            name = th_name.split(' ')
            # some lastnames contain spaces
            fname, lname = name[0], ' '.join(name[1:])
            lname = lname.lstrip()
            person = StaffPersonalInfo.query \
                .filter_by(th_firstname=fname, th_lastname=lname).first()
        elif en_name:
            fname, lname = en_name.split(' ')
            lname = lname.lstrip()
            person = StaffPersonalInfo.query \
                .filter_by(en_firstname=fname, en_lastname=lname).first()
        else:
            return jsonify({'message': 'The QR Code is not valid.'}), 400

        if person:
            now = datetime.now(pytz.utc)
            record = person.staff_account.seminar_attends.filter_by(seminar_id=seminar_id).first()
            if not record:
                record = StaffSeminarAttend(
                    seminar_id=seminar_id,
                    start_datetime=now
                )
                person.staff_account.seminar_attends.append(record)
            else:
                record.end_datetime = now
            db.session.add(record)
            db.session.commit()
            return jsonify({'message': 'success', 'name': person.fullname, 'time': now.isoformat()})
        else:
            return jsonify({'message': u'The staff with the name {} not found.'.format(fname + ' ' + lname)}), 404
    return render_template('staff/checkin_activity.html', seminar=seminar)


class LoginDataUploadView(BaseView):
    @expose('/')
    def index(self):
        return self.render('staff/login_datetime_upload.html')

    def calculate(self, row):
        DATETIME_FORMAT = '%d/%m/%Y %H:%M'
        office_starttime = '09:00'
        office_endtime = '16:30'

        if not isna(row.Time):
            account = StaffPersonalInfo.query.filter_by(finger_scan_id=row.ID).first()
            if not account:
                return

            start, end = row.Time.split()[0], row.Time.split()[-1]

            if start != end:
                start_dt = datetime.strptime(u'{} {}'.format(row.Date, start), DATETIME_FORMAT)
                end_dt = datetime.strptime(u'{} {}'.format(row.Date, end), DATETIME_FORMAT)
            else:
                start_dt = datetime.strptime(u'{} {}'.format(row.Date, start), DATETIME_FORMAT)
                end_dt = None
            office_startdt = datetime.strptime(u'{} {}'.format(row.Date, office_starttime), DATETIME_FORMAT)
            office_enddt = datetime.strptime(u'{} {}'.format(row.Date, office_endtime), DATETIME_FORMAT)

            if start_dt:
                if office_startdt > start_dt:
                    morning = office_startdt - start_dt
                    morning = (morning.seconds / 60.0) * -1
                else:
                    morning = start_dt - office_startdt
                    morning = morning.seconds / 60.0
                # status = "Late" if morning > 0 else "On time"
            if end_dt:
                if office_enddt < end_dt:
                    evening = end_dt - office_enddt
                    evening = evening.seconds / 60.0
                else:
                    evening = office_enddt - end_dt
                    evening = (evening.seconds / 60.0) * -1
                # status = "Off early" if evening < 0 else "On time"
            if start_dt and end_dt:
                record = StaffWorkLogin(
                    staff=account.staff_account,
                    start_datetime=tz.localize(start_dt),
                    end_datetime=tz.localize(end_dt),
                    checkin_mins=morning,
                    checkout_mins=evening
                )
            else:
                record = StaffWorkLogin(
                    staff=account.staff_account,
                    start_datetime=tz.localize(start_dt),
                    checkin_mins=morning,
                )
            db.session.add(record)
            db.session.commit()

    @expose('/upload', methods=['GET', 'POST'])
    def upload(self):
        if request.method == 'POST':
            if 'file' not in request.files:
                flash('No file alert')
                return redirect(request.url)
            file = request.files['file']
            if file.filename == '':
                flash('No file selected')
                return redirect(request.url)
            if file and allowed_file(file.filename):
                df = read_excel(file, dtype=object)
                df.apply(self.calculate, axis=1)
        return 'Done'


@staff.route('/for-hr/seminar-report/<int:seminar_id>', methods=['GET'])
@hr_permission.require()
@login_required
def seminar_report(seminar_id):
    seminar = StaffSeminar.query.get(seminar_id)
    return render_template('staff/seminar_report.html', seminar=seminar)


@staff.route('/for-hr/<int:seminar_id>/attend/download', methods=['GET'])
def attend_download(seminar_id):
    records = []
    attends = StaffSeminarAttend.query.filter_by(seminar_id=seminar_id).all()
    for attend in attends:
        records.append({
            u'เรื่อง': u"{}".format(attend.seminar.topic),
            u'ชื่อ-นามสกุล': u"{}".format(attend.staff.personal_info.fullname),
            u'ประเภท': u"สายวิชาการ" if attend.staff.personal_info.academic_staff is True else u"สายสนับสนุน",
            u'หน่วยงาน/ภาควิชา': u"{}".format(attend.staff.personal_info.org.name),
            u'ประเภทที่ไป': u"{}".format(attend.role),
            u'วันที่เริ่มต้น': u"{}".format(attend.start_datetime.date()),
            u'วันที่สิ้นสุด': u"{}".format(attend.end_datetime.date()
                                           if attend.end_datetime else attend.start_datetime.date()),
        })
    df = DataFrame(records)
    df.to_excel('attend_summary.xlsx')
    return send_from_directory(os.getcwd(), 'attend_summary.xlsx')


@staff.route('/api/summary')
@login_required
def send_summary_data():
    cal_start = request.args.get('start')
    cal_end = request.args.get('end')
    curr_dept_id = request.args.get('curr_dept_id', type=int)
    tab = request.args.get('tab')
    print(tab)
    if cal_start:
        cal_start = parser.isoparse(cal_start)
    if cal_end:
        cal_end = parser.isoparse(cal_end)
    employees = StaffPersonalInfo.query.filter_by(org_id=curr_dept_id)
    leaves = []
    wfhs = []
    seminars = []
    logins = []
    for emp in employees:
        if tab in ['login', 'all']:
            # TODO: recheck staff login model
            for rec in StaffWorkLogin.query.filter_by(staff=emp.staff_account) \
                    .filter(StaffWorkLogin.start_datetime.between(cal_start, cal_end)):
                end = None if rec.end_datetime is None else rec.end_datetime.astimezone(tz)
                border_color = '#ffffff' if end else '#f56956'
                text_color = '#ffffff'
                bg_color = '#7d9df0'
                '''
                if (rec.checkin_mins < 0) and (rec.checkout_mins > 0):
                    bg_color = '#4da6ff'
                    status = u'ปกติ'
                elif rec.checkin_mins > 0 and rec.checkout_mins < 0:
                    status = u'สายและออกก่อน'
                    bg_color = '#ff5c33'
                elif rec.checkin_mins > 0:
                    status = u'เข้าสาย'
                    text_color = '#000000'
                    bg_color = '#ffff66'
                elif rec.checkout_mins < 0:
                    status = u'ออกก่อน'
                    text_color = '#000000'
                    bg_color = '#ffff66'
                '''
                logins.append({
                    'id': rec.id,
                    'start': rec.start_datetime.astimezone(tz).isoformat(),
                    'end': end.isoformat() if end else None,
                    'status': 'Done' if end else 'Not done',
                    'title': u'{}'.format(emp.th_firstname),
                    'backgroundColor': bg_color,
                    'borderColor': border_color,
                    'textColor': text_color,
                    'type': 'login'
                })

        if tab in ['leave', 'all']:
            for leave_req in StaffLeaveRequest.query.filter_by(staff=emp.staff_account) \
                    .filter(StaffLeaveRequest.start_datetime.between(cal_start, cal_end)):
                if not leave_req.cancelled_at:
                    if leave_req.get_approved:
                        text_color = '#ffffff'
                        bg_color = '#2b8c36'
                        border_color = '#ffffff'
                        leave_status = 'Approved'
                    else:
                        text_color = '#989898'
                        bg_color = '#d1e0e0'
                        border_color = '#ffffff'
                        leave_status = 'Pending'
                    leaves.append({
                        'id': leave_req.id,
                        'start': leave_req.start_datetime.astimezone(tz).isoformat(),
                        'end': leave_req.end_datetime.astimezone(tz).isoformat(),
                        'title': u'{} {}'.format(emp.th_firstname, leave_req.quota.leave_type),
                        'backgroundColor': bg_color,
                        'borderColor': border_color,
                        'textColor': text_color,
                        'status': leave_status,
                        'type': 'leave'
                    })

        if tab in ['wfh', 'all']:
            for wfh_req in StaffWorkFromHomeRequest.query.filter_by(staff=emp.staff_account).filter(
                    StaffWorkFromHomeRequest.start_datetime.between(cal_start, cal_end)):
                if not wfh_req.cancelled_at and not wfh_req.get_unapproved:
                    if wfh_req.get_approved:
                        text_color = '#989898'
                        bg_color = '#C5ECFB'
                        border_color = '#109AD3'
                        wfh_status = 'Approved'
                    else:
                        text_color = '#989898'
                        bg_color = '#C5ECFB'
                        border_color = '#ffffff'
                        wfh_status = 'Pending'
                    wfhs.append({
                        'id': wfh_req.id,
                        'start': wfh_req.start_datetime.astimezone(tz).isoformat(),
                        'end': wfh_req.end_datetime.astimezone(tz).isoformat(),
                        'title': emp.th_firstname + " WFH",
                        'backgroundColor': bg_color,
                        'borderColor': border_color,
                        'textColor': text_color,
                        'status': wfh_status,
                        'type': 'wfh'
                    })
        if tab in ['smr', 'all']:
            for smr in emp.staff_account.seminar_attends.filter(
                    StaffSeminarAttend.start_datetime.between(cal_start, cal_end)):
                text_color = '#ffffff'
                bg_color = '#FF33A5'
                border_color = '#ffffff'
                seminars.append({
                    'id': smr.id,
                    'start': smr.start_datetime.astimezone(tz).isoformat(),
                    'end': smr.end_datetime.astimezone(tz).isoformat(),
                    'title': emp.th_firstname + " " + smr.seminar.topic,
                    'staff_id': emp.staff_account.id,
                    'backgroundColor': bg_color,
                    'borderColor': border_color,
                    'textColor': text_color,
                    'type': 'smr'
                })

    all = wfhs + leaves + logins + seminars

    return jsonify(all)


@staff.route('/summary')
@login_required
def summary_index():
    depts = Org.query.filter_by(head=current_user.email).all()
    if len(depts) == 0:
        # return redirect(request.referrer)
        return redirect(url_for("staff.summary_org"))

    tab = request.args.get('tab', 'all')
    curr_dept_id = request.args.get('curr_dept_id', default=depts[0].id, type=int)
    return render_template('staff/summary_index.html', depts=depts, curr_dept_id=curr_dept_id, tab=tab)


@staff.route('/api/staffids')
def get_staffid():
    staff = []
    for sid in StaffPersonalInfo.query.all():
        staff.append({
            'id': sid.id,
            'fullname': sid.fullname,
            'org': sid.org.name if sid.org else 'ไม่มีต้นสังกัด'
        })

    return jsonify(staff)


@staff.route('/summary/org')
@login_required
def summary_org():
    gj = StaffSpecialGroup.query.filter_by(group_code='gj').first()
    secret = StaffSpecialGroup.query.filter_by(group_code='secretary').first()
    if current_user not in gj.staffs and current_user not in secret.staffs:
        return redirect(url_for("staff.index"))
    fiscal_year = request.args.get('fiscal_year')
    if fiscal_year is None:
        if today.month in [10, 11, 12]:
            fiscal_year = today.year + 1
        else:
            fiscal_year = today.year
        init_date = today
    else:
        fiscal_year = int(fiscal_year)
        init_date = date(fiscal_year - 1, 10, 1)

    curr_dept_id = request.args.get('curr_dept_id', current_user.personal_info.org.id)
    tab = request.args.get('tab', 'all')

    employees = StaffPersonalInfo.query.filter_by(org_id=int(curr_dept_id))

    leaves = []
    for emp in employees:
        if tab == 'leave' or tab == 'all':
            fiscal_years = StaffLeaveRequest.query.distinct(func.date_part('YEAR', StaffLeaveRequest.start_datetime))
            fiscal_years = [convert_to_fiscal_year(req.start_datetime) for req in fiscal_years]
            start_fiscal_date, end_fiscal_date = get_start_end_date_for_fiscal_year(fiscal_year)
            for leave_req in StaffLeaveRequest.query.filter_by(staff=emp) \
                    .filter(StaffLeaveRequest.start_datetime.between(start_fiscal_date, end_fiscal_date)):
                if not leave_req.cancelled_at:
                    if leave_req.get_approved:
                        text_color = '#ffffff'
                        bg_color = '#2b8c36'
                        border_color = '#ffffff'
                    else:
                        text_color = '#989898'
                        bg_color = '#d1e0e0'
                        border_color = '#ffffff'
                    leaves.append({
                        'id': leave_req.id,
                        'start': leave_req.start_datetime.astimezone(tz).isoformat(),
                        'end': leave_req.end_datetime.astimezone(tz).isoformat(),
                        'title': u'{} {}'.format(emp.th_firstname, leave_req.quota.leave_type),
                        'backgroundColor': bg_color,
                        'borderColor': border_color,
                        'textColor': text_color,
                        'type': 'leave'
                    })
            all = leaves

    if tab == 'all':
        all = leaves

    return render_template('staff/summary_org.html', init_date=init_date,
                           curr_dept_id=int(curr_dept_id),
                           all=all, tab=tab, fiscal_years=fiscal_years, fiscal_year=fiscal_year)


@staff.route('/shift-schedule')
@login_required
def shift_schedule():
    employees = StaffPersonalInfo.query.all()
    shift_record = []
    for emp in employees:
        for record in StaffShiftSchedule.query.filter_by(staff=emp.staff_account):
            leave_request = StaffLeaveRequest.query.filter(cast(StaffLeaveRequest.start_datetime, Date)
                                                           == record.start_datetime.date()).all()
            if leave_request:
                text_color = '#ffffff'
                bg_color = '#D8D8D8'
            else:
                text_color = '#000000'
                bg_color = '#FFC300'
            border_color = '#ffffff'
            shift_record.append({
                'id': record.id,
                'start': record.start_datetime.astimezone(tz).isoformat(),
                'end': record.end_datetime.astimezone(tz).isoformat(),
                'title': emp.th_firstname,
                'backgroundColor': bg_color,
                'borderColor': border_color,
                'textColor': text_color,
                'type': 'ot'
            })
        all = shift_record
    return render_template('staff/shift_schedule.html', all=all)


@staff.route('/shift-schedule/create', methods=['GET', 'POST'])
@login_required
def create_shift_schedule():
    staff_list = []
    account_query = StaffAccount.query.all()
    for account in account_query:
        record = dict(staffid=account.id,
                      fullname=account.personal_info.fullname,
                      email=account.email)
        organization = account.personal_info.org
        record["org"] = organization.name if organization else ""
        staff_list.append(record)
    if request.method == "POST":
        form = request.form
        # TODO: auto generate end_datetime (8 hours from start datetime)
        start_datetime = datetime.strptime(form.get('start_dt'), '%d/%m/%Y %H:%M')
        end_datetime = datetime.strptime(form.get('end_dt'), '%d/%m/%Y %H:%M')
        timedelta = end_datetime - start_datetime
        if timedelta.days < 0 or timedelta.seconds == 0:
            flash(u'วันที่สิ้นสุดต้องไม่เร็วกว่าวันที่เริ่มต้น', 'danger')
            return render_template('staff/shift_schedule_create_schedule.html', staff_list=staff_list)
        else:
            for staff_id in form.getlist("worker"):
                schedule = StaffShiftSchedule(
                    staff_id=int(staff_id),
                    start_datetime=tz.localize(start_datetime),
                    end_datetime=tz.localize(end_datetime)
                )
                db.session.add(schedule)
            db.session.commit()
            flash(u'เพิ่มเวลาปฏิบัติงานเรียบร้อยแล้ว', 'success')
            return redirect(url_for('staff.shift_schedule'))
    return render_template('staff/shift_schedule_create_schedule.html', staff_list=staff_list)


@staff.route('/shift-schedule/edit/<int:schedule_id>', methods=['GET', 'POST'])
@login_required
def edit_shift_schedule(schedule_id):
    schedule = StaffShiftSchedule.query.get(schedule_id)
    if request.method == 'POST':
        form = request.form
        start_datetime = datetime.strptime(form.get('start_dt'), '%d/%m/%Y %H:%M')
        end_datetime = datetime.strptime(form.get('end_dt'), '%d/%m/%Y %H:%M')
        timedelta = end_datetime - start_datetime
        if timedelta.days < 0 or timedelta.seconds == 0:
            flash(u'วันที่สิ้นสุดต้องไม่เร็วกว่าวันที่เริ่มต้น', 'danger')
            return render_template('staff/shift_schedule_edit.html', schedule=schedule)
        else:
            schedule.start_datetime = tz.localize(start_datetime)
            schedule.end_datetime = tz.localize(end_datetime)
            db.session.add(schedule)
            db.session.commit()
            flash(u'การแก้ไขถูกบันทึกเรียบร้อย', 'success')
            return redirect(url_for('staff.shift_schedule'))
    return render_template('staff/shift_schedule_edit.html', schedule=schedule)


@staff.route('/for-hr/seminar')
@hr_permission.require()
@login_required
def seminar():
    return render_template('staff/seminar.html')


@staff.route('/for-hr/seminar/approval')
@hr_permission.require()
@login_required
def seminar_approval_records():
    seminar_attend = []
    for seminars in StaffSeminarAttend.query.filter(StaffSeminarAttend.id ==
                                                    StaffSeminarProposal.seminar_attend_id).all():
        seminar_attend.append(seminars)

    seminar_approval_records = []
    for seminar_approval in StaffSeminarAttend.query.filter(StaffSeminar.cancelled_at == None).all():
        if seminar_approval.seminar_approval:
            seminar_approval_records.append(seminar_approval)
    return render_template('staff/seminar_approval_info.html', seminar_records=seminar_records
                           , seminar_approval_records=seminar_approval_records, seminar_attend=seminar_attend)


@staff.route('/for-hr/seminar/approval/add-approval/<int:attend_id>', methods=['GET', 'POST'])
@hr_permission.require()
@login_required
def seminar_add_approval(attend_id):
    # attend = StaffSeminarAttend.query.filter_by(id=attend_id).all()
    # attend_first = StaffSeminarAttend.query.filter_by(id=attend_id).first()
    # attend_query = StaffSeminarAttend.query.filter_by(seminar_id=attend_first.seminar_id).all()
    # management = StaffSpecialGroup.query.filter_by(group_code='management').first()
    # approvers = management.staffs
    # staff_attend_list = []
    # for attend in attend_query:
    #     if not attend.staff_account_id == attend_first.staff_account_id:
    #         staff_attend_list.append(attend)

    attend = StaffSeminarAttend.query.get(attend_id)
    management = StaffSpecialGroup.query.filter_by(group_code='management').first()
    approvers = management.staffs
    if request.method == 'POST':
        form = request.form
        update_d = form.get('update_at')
        #TODO: recheck update time
        update_t = "13:00"
        update_dt = '{} {}'.format(update_d, update_t)
        updated_at = datetime.strptime(update_dt, '%d/%m/%Y %H:%M')
        approval = StaffSeminarApproval(
            seminar_attend=attend,
            updated_at=tz.localize(updated_at),
            recorded_account_id=current_user.id,
            final_approver_account_id=form.get('approver_id'),
            is_approved=False if form.get('approval') == 'False' else True,
            approval_comment=form.get('other_approval') if form.get('other_approval') else ""
        )
        db.session.add(approval)
        db.session.commit()
        attends = StaffSeminarAttend.query.get(attend_id)
        if form.get('document_id'):
            document_id = form.get('document_id')
            document_no = form.get('document_no')
            document = u'อว.{}/{}'.format(document_id, document_no)
            attends.document_no = document
        attends.registration_fee = form.get('registration_fee')
        attends.budget_type = form.get('budget_type')
        attends.budget = form.get('budget')
        attends.accommodation_cost = form.get('accommodation_cost')
        attends.fuel_cost = form.get('fuel_cost')
        attends.taxi_cost = form.get('taxi_cost')
        attends.train_ticket_cost = form.get('train_ticket_cost')
        attends.flight_ticket_cost = form.get('flight_ticket_cost')
        attends.transaction_fee = form.get('transaction_fee')
        db.session.add(attend)
        db.session.commit()

        if form.get('approval') == 'True':
            req_msg = u'ตามที่ท่านขออนุมัติ{} เรื่อง {} ระหว่างวันที่ {} ถึงวันที่ {}\n {}อนุมัติเรียบร้อยแล้ว' \
                      u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'. \
                format(attend.seminar.topic_type, attend.seminar.topic,
                       attend.start_datetime, attend.end_datetime, approval.approver.personal_info)
        elif form.get('approval') == 'False':
            req_msg = u'ตามที่ท่านขออนุมัติ{} เรื่อง {} ระหว่างวันที่ {} ถึงวันที่ {}\n {}ไม่อนุมัติคำขอของท่าน' \
                      u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'. \
                format(attend.seminar.topic_type, attend.seminar.topic,
                       attend.start_datetime, attend.end_datetime, approval.approver.personal_info)
        else:
            req_msg = u'ตามที่ท่านขออนุมัติ{} เรื่อง {} ระหว่างวันที่ {} ถึงวันที่ {}\n {}อนุมัติแบบมีเงื่อนไข {}' \
                      u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'. \
                format(attend.seminar.topic_type, attend.seminar.topic,
                       attend.start_datetime, attend.end_datetime,
                       approval.approver.personal_info, approval.approval_comment)
        req_title = u'ทดสอบแจ้งผลการขออนุมัติ' + attend.seminar.topic_type
        requester_email = attend.staff.email
        line_id = attend.staff.line_id
        if os.environ["FLASK_ENV"] == "production":
            send_mail([requester_email + "@mahidol.ac.th"], req_title, req_msg)
            if line_id:
                line_bot_api.push_message(to=line_id, messages=TextSendMessage(text=req_msg))
        else:
            print(req_msg, requester_email, line_id)
        flash(u'update รายการอนุมัติเรียบร้อยแล้ว', 'success')

        seminar_records = []
        for seminars in StaffSeminarAttend.query.filter(StaffSeminar.cancelled_at == None).all():
            if seminars.document_title:
                seminar_records.append(seminars)
        seminar_approval_records = []
        for seminar_approval in StaffSeminarAttend.query.filter(StaffSeminar.cancelled_at == None).all():
            if seminar_approval.seminar_approval:
                seminar_approval_records.append(seminar_approval)
        return render_template('staff/seminar_approval_info.html', seminar_records=seminar_records,
                                                seminar_approval_records=seminar_approval_records)
    return render_template('staff/seminar_add_approval.html', attend=attend, approvers=approvers)


@staff.route('/seminar/create', methods=['GET', 'POST'])
@login_required
def create_seminar():
    form = StaffSeminarForm()
    if form.validate_on_submit():
        seminar = StaffSeminar()
        form.populate_obj(seminar)
        timedelta = form.end_datetime.data - form.start_datetime.data
        if timedelta.days < 0 and timedelta.seconds == 0:
            flash(u'วันที่สิ้นสุดต้องไม่เร็วกว่าวันที่เริ่มต้น', 'danger')
        else:
            seminar.start_datetime = tz.localize(form.start_datetime.data),
            seminar.end_datetime = tz.localize(form.end_datetime.data)
            db.session.add(seminar)
            db.session.commit()
            flash(u'เพิ่มข้อมูลกิจกรรมเรียบร้อย', 'success')
        if hr_permission.can():
            return redirect(url_for('staff.seminar_attend_info_for_hr', seminar_id=seminar.id))
        else:
            return redirect(url_for('staff.seminar_attend_info', seminar_id=seminar.id))
    else:
        for err in form.errors:
            flash('{}: {}'.format(err, form.errors[err]), 'danger')
    return render_template('staff/seminar_create_event.html', form=form)


@staff.route('/seminar/add-attend/for-hr/<int:seminar_id>')
@login_required
@hr_permission.require()
def seminar_attend_info_for_hr(seminar_id):
    seminar = StaffSeminar.query.get(seminar_id)
    attends = StaffSeminarAttend.query.filter_by(seminar_id=seminar_id).all()
    return render_template('staff/seminar_attend_info_for_hr.html', seminar=seminar, attends=attends)


@staff.route('/seminar/add-attend/<int:seminar_id>', methods=['GET', 'POST'])
@login_required
def seminar_attend_info(seminar_id):
    seminar = StaffSeminar.query.get(seminar_id)
    attends = StaffSeminarAttend.query.filter_by(seminar_id=seminar_id).all()
    current_user_attended = StaffSeminarAttend.query.filter_by(seminar_id=seminar_id, staff_account_id=current_user.id).first()
    return render_template('staff/seminar_attend_info.html', seminar=seminar, attends=attends, current_user_attended=current_user_attended)


@staff.route('/seminar/all-seminars', methods=['GET', 'POST'])
@login_required
def seminar_records():
    if request.method == "POST":
        form = request.form
        start_t = "00:00"
        end_t = "23:59"
        start_d, end_d = form.get('dates').split(' - ')
        start_dt = '{} {}'.format(start_d, start_t)
        end_dt = '{} {}'.format(end_d, end_t)
        start_datetime = datetime.strptime(start_dt, '%d/%m/%Y %H:%M')
        end_datetime = datetime.strptime(end_dt, '%d/%m/%Y %H:%M')
        records = []
        attends = StaffSeminarAttend.query.filter(and_(StaffSeminarAttend.start_datetime >= start_datetime,
                                                          StaffSeminarAttend.start_datetime <= end_datetime))
        columns = [u'ชื่อ-นามสกุล', u'ประเภท', u'ประเภทที่ไป', u'เรื่อง',
                   u'ประเภทแหล่งเงิน', u'จำนวนเงิน', u'วันที่เริ่มต้น', u'วันที่สิ้นสุด', u'สถานที่']
        for attend in attends:
            records.append({
                columns[0]: u"{}".format(attend.staff.personal_info.fullname),
                columns[1]: u"สายวิชาการ" if attend.staff.personal_info.academic_staff is True else u"สายสนับสนุน",
                columns[2]: u"{}".format(attend.role),
                columns[3]: u"{}".format(attend.seminar.topic),
                columns[4]: u"{}".format(attend.budget_type if attend.budget_type else ""),
                columns[5]: u"{}".format(attend.budget if attend.budget else ""),
                columns[6]: u"{}".format(attend.start_datetime.date()),
                columns[7]: u"{}".format(attend.end_datetime.date()
                                                   if attend.end_datetime else attend.start_datetime.date()),
                columns[8]: u"{}".format(attend.seminar.location),
            })
        df = DataFrame(records, columns=columns)
        df.to_excel('attend_summary.xlsx',index=False, columns=columns)
        return send_from_directory(os.getcwd(), 'attend_summary.xlsx')
    else:
        seminar_list = []
        seminar_query = StaffSeminar.query.filter(StaffSeminar.cancelled_at == None).all()
        for seminar in seminar_query:
            record = {}
            record["id"] = seminar.id
            record["topic_type"] = seminar.topic_type
            record["name"] = seminar.topic
            record["start"] = seminar.start_datetime
            record["end"] = seminar.end_datetime
            record["organize_by"] = seminar.organize_by
            seminar_list.append(record)
        return render_template('staff/seminar_records.html', seminar_list=seminar_list)


@staff.route('/seminar/create-record/<int:seminar_id>', methods=['GET', 'POST'])
@login_required
def seminar_create_record(seminar_id):
    MyStaffSeminarAttendForm = create_seminar_attend_form(current_user)
    #TODO: check case duplicate attend
    form = MyStaffSeminarAttendForm()
    seminar = StaffSeminar.query.get(seminar_id)
    if form.validate_on_submit():
        attend = StaffSeminarAttend()
        form.populate_obj(attend)
        attend.start_datetime = tz.localize(form.start_datetime.data)
        attend.end_datetime = tz.localize(form.end_datetime.data)
        attend.staff = current_user
        attend.seminar = seminar
        if form.invited_document_date.data:
            attend.invited_document_date = form.invited_document_date.data
        if form.approver.data:
            attend.lower_level_approver_account_id = form.approver.data.account.id
        # if form.contact_no.data:
        #     attend.contact_no = form.contact_no.data
            attend.document_title = form.document_title.data
        db.session.add(attend)
        db.session.commit()

        req_title = u'ทดสอบแจ้งการขออนุมัติ' + attend.seminar.topic_type
        req_msg = u'{} ขออนุมัติ{} เรื่อง {} ระหว่างวันที่ {} ถึงวันที่ {}\nคลิกที่ Link เพื่อดูรายละเอียดเพิ่มเติม {} ' \
                  u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'. \
            format(attend.staff.personal_info, attend.seminar.topic_type, attend.seminar.topic,
                   attend.start_datetime, attend.end_datetime,
                   url_for("staff.seminar_request_for_proposal", seminar_attend_id=attend.id, _external=True))
        if attend.lower_level_approver_account_id:
            approver = StaffLeaveApprover.query.filter_by(
                approver_account_id=attend.lower_level_approver_account_id).first()
            approver_email = approver.account.email
            is_notify_line = approver.notified_by_line
            line_id = approver.account.line_id
            if os.environ["FLASK_ENV"] == "production":
                send_mail([approver_email + "@mahidol.ac.th"], req_title, req_msg)
                if is_notify_line and line_id:
                    line_bot_api.push_message(to=line_id,messages=TextSendMessage(text=req_msg))
            else:
                print(req_msg, line_id)
            flash(u'ส่งคำขอไปยังผู้บังคับบัญชาของท่านเรียบร้อยแล้ว ', 'success')
        else:
            flash(u'เพิ่มรายชื่อของท่านเรียบร้อยแล้ว', 'success')
        attends = StaffSeminarAttend.query.filter_by(seminar_id=seminar_id).all()
        return render_template('staff/seminar_attend_info.html', seminar=seminar, attends=attends)
    print (form.errors)
    return render_template('staff/seminar_create_record.html', seminar=seminar, form=form)


@staff.route('/seminar/requests/proposal/info')
@login_required
def show_seminar_proposal_info():
    leave_approver = StaffLeaveApprover.query.filter_by(approver_account_id=current_user.id).first()
    if not leave_approver:
        return redirect(url_for('staff.seminar_attends_each_person', staff_id=current_user.id))
    lower_level_requests = StaffSeminarAttend.query.filter_by(lower_level_approver=current_user).all()
    middle_level_requests = StaffSeminarAttend.query.filter_by(middle_level_approver=current_user).all()
    last_two_month = datetime.now() - timedelta(60)
    pending_proposal = StaffSeminarProposal.query.filter_by(proposer=current_user)\
                                            .filter(StaffSeminarProposal.approved_at >= last_two_month).all()
    return render_template('staff/seminar_request_for_proposal.html', lower_level_requests=lower_level_requests,
                           middle_level_requests=middle_level_requests, pending_proposal=pending_proposal)


@staff.route('/seminar/request/proposal/detail/<int:seminar_attend_id>', methods=['GET', 'POST'])
@login_required
def seminar_request_for_proposal(seminar_attend_id):
    seminar_attend = StaffSeminarAttend.query.get(seminar_attend_id)
    another_proposer = StaffLeaveApprover.query.filter_by(staff_account_id=seminar_attend.staff_account_id).filter(
                                        StaffLeaveApprover.approver_account_id != current_user.id).all()
    #TODO: if the request have IDP objective, show personal's IDP information
    # TODO: generate document no
    if request.method == 'POST':
        form = request.form
        is_previous_proposer = StaffSeminarProposal.query.filter_by(seminar_attend_id=seminar_attend_id).first()
        proposal = StaffSeminarProposal(
            seminar_attend_id=seminar_attend_id,
            approved_at=tz.localize(datetime.today()),
            is_approved=True if form.get('status') == 'yes' else False,
            comment=form.get('comment') if form.get('comment') else None,
            proposer_account_id=current_user.id,
            previous_proposal_id=is_previous_proposer.id if is_previous_proposer else None
        )
        db.session.add(proposal)
        db.session.commit()
        if form.get('status') == 'yes':
            if form.get('another_proposer_id'):
                middle_level_approver_account_id = form.get('another_proposer_id')
                seminar_attend.middle_level_approver_account_id = middle_level_approver_account_id
                db.session.add(seminar_attend)
                db.session.commit()

                if seminar_attend.middle_level_approver_account_id:
                    req_title = u'ทดสอบแจ้งการขออนุมัติ' + seminar_attend.seminar.topic_type
                    req_msg = u'{} ขออนุมัติ{} เรื่อง {} ระหว่างวันที่ {} ถึงวันที่ {}\nคลิกที่ Link เพื่อดูรายละเอียดเพิ่มเติม {} ' \
                              u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'. \
                        format(seminar_attend.staff.personal_info, seminar_attend.seminar.topic_type,
                               seminar_attend.seminar.topic, seminar_attend.start_datetime, seminar_attend.end_datetime,
                               url_for("staff.seminar_request_for_proposal",
                                       seminar_attend_id=seminar_attend.id, _external=True))
                    approver = StaffLeaveApprover.query.filter_by(approver_account_id=middle_level_approver_account_id).first()
                    approver_email = approver.account.email
                    is_notify_line = approver.notified_by_line
                    line_id = approver.account.line_id
                    if os.environ["FLASK_ENV"] == "production":
                        send_mail([approver_email + "@mahidol.ac.th"], req_title, req_msg)
                        if is_notify_line and line_id:
                            line_bot_api.push_message(to=line_id, messages=TextSendMessage(text=req_msg))
                    else:
                        print(req_msg, approver_email, line_id)
                    flash(u'ส่งคำขอต่อไปยังรองคณบดีเรียบร้อยแล้ว ', 'success')
            else:
                flash(u'ระบบบันทึกการอนุมัติของท่านแล้ว กรุณาเซ็นเอกสารและ Upload เข้าระบบต่อไป', 'success')
        else:
            req_title = u'ทดสอบแจ้งผลการขออนุมัติ' + seminar_attend.seminar.topic_type
            req_msg = u'ตามที่ท่านขออนุมัติ{} เรื่อง {} ระหว่างวันที่ {} ถึงวันที่ {}\n ผู้บังคับบัญชาขั้นต้นไม่อนุมัติเนื่องจาก {} ' \
                      u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'. \
                format(seminar_attend.seminar.topic_type, seminar_attend.seminar.topic,
                       seminar_attend.start_datetime, seminar_attend.end_datetime, seminar_attend.proposal.comment)
            requester_email = seminar_attend.staff.email
            line_id = seminar_attend.staff.line_id
            if os.environ["FLASK_ENV"] == "production":
                send_mail([requester_email + "@mahidol.ac.th"], req_title, req_msg)
                if line_id:
                    line_bot_api.push_message(to=line_id, messages=TextSendMessage(text=req_msg))
            else:
                print(req_msg, requester_email, line_id)
        return redirect(url_for('staff.show_seminar_proposal_info'))
    return render_template('staff/seminar_request_for_proposal_detail.html', seminar_attend=seminar_attend,
                           another_proposer=another_proposer)


@staff.route('/seminar/request/upload/<int:seminar_attend_id>/<int:proposal_id>', methods=['GET', 'POST'])
@login_required
def seminar_upload_proposal(seminar_attend_id, proposal_id):
    proposal = StaffSeminarProposal.query.filter_by(seminar_attend_id=seminar_attend_id).all()
    this_proposal = StaffSeminarProposal.query.get(proposal_id)
    if request.method == 'POST':
        upload_file = request.files.get('document')
        if upload_file:
            upload_file_name = secure_filename(upload_file.filename)
            upload_file.save(upload_file_name)
            file_drive = drive.CreateFile({'title': upload_file_name})
            file_drive.SetContentFile(upload_file_name)
            file_drive.Upload()
            permission = file_drive.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
            upload_file_url = file_drive['id']
            flash(u'Upload File เรียบร้อยแล้ว', 'success')
        else:
            upload_file_url = None
            flash(u'Upload File ไม่สำเร็จ', 'warning')
        this_proposal.upload_file_url = upload_file_url
        db.session.add(this_proposal)
        db.session.commit()
        return redirect(url_for('staff.show_seminar_proposal_info'))
    return render_template('staff/seminar_upload_proposal.html', proposal=proposal, this_proposal=this_proposal)


@staff.route('/seminar/all-proposal')
@login_required
def seminar_proposal():
    seminar_attend_list = []
    attend_query = StaffSeminarAttend.query.all()
    for attend in attend_query:
        if attend.is_approved_by(current_user):
            seminar_attend_list.append(attend)
    return render_template('staff/seminar_all_proposal.html', seminar_attend_list=seminar_attend_list)


@staff.route('/seminar/add-attend/add-attendee/<int:seminar_id>', methods=['GET', 'POST'])
@login_required
def seminar_add_attendee(seminar_id):
    seminar = StaffSeminar.query.get(seminar_id)
    staff_list = []
    account_query = StaffAccount.query.all()
    for account in account_query:
        record = dict(staffid=account.id,
                      fullname=account.personal_info.fullname,
                      email=account.email)
        organization = account.personal_info.org
        record["org"] = organization.name if organization else ""
        staff_list.append(record)
    if request.method == "POST":
        form = request.form
        start_datetime = datetime.strptime(form.get('start_dt'), '%d/%m/%Y %H:%M')
        end_datetime = datetime.strptime(form.get('end_dt'), '%d/%m/%Y %H:%M')
        for staff_id in form.getlist("participants"):
            attend = StaffSeminarAttend(
                staff_account_id=staff_id,
                seminar_id=seminar_id,
                role=form.get('role'),
                registration_fee=form.get('registration_fee') if form.get("registration_fee") else "",
                budget_type=form.get('budget_type'),
                budget=form.get('budget'),
                start_datetime=tz.localize(start_datetime),
                end_datetime=tz.localize(end_datetime),
                attend_online=True if form.get("attend_online") else False,
                accommodation_cost=form.get('accommodation_cost') if form.get("accommodation_cost") else "",
                fuel_cost=form.get('fuel_cost') if form.get("fuel_cost") else "",
                taxi_cost=form.get('taxi_cost') if form.get("taxi_cost") else "",
                train_ticket_cost=form.get('train_ticket_cost') if form.get("train_ticket_cost") else "",
                flight_ticket_cost=form.get('flight_ticket_cost') if form.get("flight_ticket_cost") else "",
                objective=form.get('objective') if form.get('objective') != '' else form.get('other_objective')
            )
            db.session.add(attend)
            db.session.commit()
        attends = StaffSeminarAttend.query.filter_by(seminar_id=seminar_id).all()
        flash(u'เพิ่มผู้เข้าร่วมใหม่เรียบร้อยแล้ว', 'success')
        return render_template('staff/seminar_attend_info_for_hr.html', seminar=seminar, attends=attends)
    return render_template('staff/seminar_add_attendee.html', seminar=seminar, staff_list=staff_list)


@staff.route('/seminar/seminar-attend/<int:attend_id>')
@login_required
def delete_participant(attend_id):
    attend = StaffSeminarAttend.query.get(attend_id)
    db.session.delete(attend)
    db.session.commit()
    seminar = StaffSeminar.query.get(attend.seminar_id)
    attends = StaffSeminarAttend.query.filter_by(seminar_id=attend.seminar_id).all()
    return render_template('staff/seminar_attend_info.html', seminar=seminar, attends=attends)


@staff.route('/seminar/info/<int:record_id>')
@login_required
def show_seminar_info_each_person(record_id):
    attend = StaffSeminarAttend.query.get(record_id)
    proposal = StaffSeminarProposal.query.filter_by(seminar_attend_id=attend.id).all()
    approval = StaffSeminarApproval.query.filter_by(seminar_attend_id=attend.id).first()
    all_hr = StaffSpecialGroup.query.filter_by(group_code='hr').first()
    for hr in all_hr.staffs:
        is_hr = True if hr.id == current_user.id else False
    return render_template('staff/seminar_each_record.html', attend=attend, approval=approval,
                           proposal=proposal, is_hr=is_hr)


@staff.route('/seminar/edit-seminar/<int:seminar_id>', methods=['GET', 'POST'])
@login_required
def edit_seminar_info(seminar_id):
    seminar = StaffSeminar.query.get(seminar_id)
    if request.method == 'POST':
        form = request.form
        start_datetime = datetime.strptime(form.get('start_datetime'), '%d/%m/%Y %H:%M')
        end_datetime = datetime.strptime(form.get('end_datetime'), '%d/%m/%Y %H:%M')
        timedelta = end_datetime - start_datetime
        if timedelta.days < 0 or timedelta.seconds == 0:
            flash(u'วันที่สิ้นสุดต้องไม่เร็วกว่าวันที่เริ่มต้น', 'danger')
            return render_template('staff/seminar_edit_seminar_info.html', seminar=seminar)
        else:
            seminar.start_datetime = tz.localize(start_datetime)
            seminar.end_datetime = tz.localize(end_datetime)
            seminar.topic_type = form.get('topic_type')
            seminar.topic = form.get('topic')
            seminar.mission = form.get('mission')
            seminar.location = form.get('location')
            seminar.country = form.get('country')
            seminar.is_online = True if form.getlist("online") else False
            db.session.add(seminar)
            db.session.commit()
            flash(u'การแก้ไขถูกบันทึกเรียบร้อย', 'success')
            return redirect(url_for('staff.seminar_records'))

    return render_template('staff/seminar_edit_seminar_info.html', seminar=seminar)


@staff.route('/seminar/cancel-seminar/<int:seminar_id>', methods=['GET', 'POST'])
@login_required
def cancel_seminar(seminar_id):
    seminar = StaffSeminar.query.get(seminar_id)
    attends = StaffSeminarAttend.query.filter_by(seminar_id=seminar_id).all()
    if attends:
        flash(u'ไม่สามารถลบกิจกรรมนี้ได้ เนื่องจากมีข้อมูลผู้เข้าร่วมอยู่ในกิจกรรม จำเป็นต้องลบข้อมูลผู้เข้าร่วมก่อน',
              'danger')
    else:
        seminar.cancelled_at = tz.localize(datetime.today())
        db.session.add(seminar)
        db.session.commit()
        flash(u'ลบกิจกรรมเรียบร้อยแล้ว', 'success')
    return redirect(url_for('staff.seminar_records'))


@staff.route('/seminar/attends-each-person/<int:staff_id>', methods=['GET', 'POST'])
@login_required
def seminar_attends_each_person(staff_id):
    seminar_list = []
    attend_name = StaffSeminarAttend.query.filter_by(staff_account_id=staff_id).first()
    attends_query = StaffSeminarAttend.query.filter_by(staff_account_id=staff_id).all()
    for attend in attends_query:
        seminar_list.append(attend)

    seminar_records = []
    seminar_query = StaffSeminar.query.filter(StaffSeminar.cancelled_at == None).all()
    for seminars in seminar_query:
        seminar_records.append(seminars)
    approver = StaffLeaveApprover.query.filter_by(approver_account_id=current_user.id).first()
    return render_template('staff/seminar_records_each_person.html', seminar_list=seminar_list,
                           attend_name=attend_name ,seminar_records=seminar_records, approver=approver)


@staff.route('/api/time-report')
@login_required
def send_time_report_data():
    cal_start = request.args.get('start')
    cal_end = request.args.get('end')
    if cal_start:
        cal_start = parser.isoparse(cal_start)
    if cal_end:
        cal_end = parser.isoparse(cal_end)
    records = []
    for rec in StaffWorkLogin.query.filter(StaffWorkLogin.start_datetime.between(cal_start, cal_end))\
            .filter_by(staff=current_user):
        # The event object is a dict object with a 'summary' key.
        text_color = '#ffffff'
        bg_color = '#4da6ff'
        border_color = '#ffffff'
        end = None if rec.end_datetime is None else rec.end_datetime.astimezone(tz)
        records.append({
            'id': rec.id,
            'start': rec.start_datetime.astimezone(tz).isoformat(),
            'end': end.isoformat() if end else None,
            'title': u'{}'.format(rec.staff.personal_info.th_firstname),
            'backgroundColor': bg_color,
            'borderColor': border_color,
            'textColor': text_color,
            'type': 'login'
        })
    return jsonify(records)


@staff.route('/time-report/report')
@login_required
def show_time_report():
    return render_template('staff/time_report.html',
                           logins=current_user.work_logins.order_by(StaffWorkLogin.start_datetime.desc()))


@staff.route('/for-hr/staff-info')
@login_required
def staff_index():
    return render_template('staff/staff_index.html')


@staff.route('/for-hr/staff-info/create', methods=['GET', 'POST'])
@login_required
def staff_create_info():
    if request.method == 'POST':
        form = request.form
        getemail = form.get('email')
        for staff in StaffAccount.query.all():
            if staff.email == getemail:
                flash(u'มีบัญชีนี้อยู่ในระบบแล้ว', 'warning')
                departments = Org.query.all()
                employments = StaffEmployment.query.all()
                return render_template('staff/staff_create_info.html', departments=departments, employments=employments)

        start_d = form.get('employed_date')
        start_date = datetime.strptime(start_d, '%d/%m/%Y')
        createstaff = StaffPersonalInfo(
            en_firstname=form.get('en_firstname'),
            en_lastname=form.get('en_lastname'),
            th_firstname=form.get('th_firstname'),
            th_lastname=form.get('th_lastname'),
            position=form.get('position'),
            # TODO: try removing localize
            employed_date=tz.localize(start_date),
            finger_scan_id=form.get('finger_scan_id'),
            employment_id=form.get('employment_id'),
            org_id=form.get('org_id')
        )
        academic_staff = True if form.getlist("academic_staff") else False
        createstaff.academic_staff = academic_staff

        db.session.add(createstaff)
        db.session.commit()

        create_email = StaffAccount(
            personal_id=createstaff.id,
            email=form.get('email'),
            password=form.get('password')
        )
        db.session.add(create_email)
        db.session.commit()

        START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
        for type in StaffLeaveType.query.all():
            quota = StaffLeaveQuota.query.filter_by(employment_id=createstaff.employment_id,
                                                    leave_type_id=type.id).first()
            new_used_quota = StaffLeaveUsedQuota(
                leave_type_id=type.id,
                staff_account_id=create_email.id,
                fiscal_year=END_FISCAL_DATE.year,
                used_days=0,
                pending_days=0,
                quota_days=quota.first_year
            )
            db.session.add(new_used_quota)
            db.session.commit()

        flash(u'เพิ่มบุคลากรเรียบร้อย และเพิ่มข้อมูล quota การลาให้กับพนักงานใหม่เรียบร้อย', 'success')
        staff = StaffPersonalInfo.query.get(createstaff.id)
        return render_template('staff/staff_show_info.html', staff=staff)
    departments = Org.query.all()
    employments = StaffEmployment.query.all()
    return render_template('staff/staff_create_info.html', departments=departments, employments=employments)


@staff.route('/for-hr/staff-info/search-info', methods=['GET', 'POST'])
@login_required
def staff_search_info():
    if request.method == 'POST':
        staff_id = request.form.get('staffname')
        staff = StaffPersonalInfo.query.get(staff_id)
        emp_date = staff.employed_date
        resign_date = staff.resignation_date
        retired_date = staff.retirement_date
        employments = StaffEmployment.query.all()
        departments = Org.query.all()
        return render_template('staff/staff_edit_info.html', staff=staff, emp_date=emp_date, retired_date=retired_date,
                               resign_date=resign_date, employments=employments, departments=departments)
    return render_template('staff/staff_find_name_to_edit.html')


@staff.route('/for-hr/staff-info/edit-info/<int:staff_id>', methods=['GET', 'POST'])
@login_required
def staff_edit_info(staff_id):
    staff = StaffPersonalInfo.query.get(staff_id)
    early_staff_employment_id = staff.employment_id
    if request.method == 'POST':
        form = request.form
        staff_email = StaffAccount.query.filter_by(personal_id=staff_id).first()
        if staff_email:
            staff_email.email = form.get('email')
            db.session.add(staff_email)
        else:
            createstaff = StaffAccount(
                personal_id=staff_id,
                email=form.get('email')
            )
            db.session.add(createstaff)
        start_d = form.get('employed_date')
        start_date = datetime.strptime(start_d, '%d/%m/%Y') if start_d else None
        resign_date = datetime.strptime(form.get('resignation_date'), '%d/%m/%Y') \
                      if form.get('resignation_date') else None
        retired_date = datetime.strptime(form.get('retirement_date'), '%d/%m/%Y') \
            if form.get('retirement_date') else None
        staff.th_title = form.get('th_title')
        staff.en_title = form.get('en_title')
        staff.en_firstname = form.get('en_firstname')
        staff.en_lastname = form.get('en_lastname')
        staff.th_firstname = form.get('th_firstname')
        staff.th_lastname = form.get('th_lastname')
        staff.position = form.get('position')
        staff.employed_date = tz.localize(start_date) if start_date else None
        staff.resignation_date = tz.localize(resign_date) if resign_date else None
        staff.retirement_date = tz.localize(retired_date) if retired_date else None
        if form.get('finger_scan_id'):
            staff.finger_scan_id = form.get('finger_scan_id')
        staff.employment_id = form.get('employment_id')
        staff.org_id = form.get('org_id')
        academic_staff = True if form.getlist("academic_staff") else False
        staff.academic_staff = academic_staff
        retired = True if form.getlist("retired") else False
        staff.retired = retired
        db.session.add(staff)
        db.session.commit()

        if early_staff_employment_id != staff.employment_id:
            START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(datetime.today())
            delta = staff.get_employ_period()
            for type in StaffLeaveType.query.all():
                quota = StaffLeaveQuota.query.filter_by(employment_id=staff.employment_id,
                                                        leave_type_id=type.id).first()
                is_used_quota = StaffLeaveUsedQuota.query.filter_by\
                                (staff=createstaff, fiscal_year=END_FISCAL_DATE, leave_type_id=type.id).first()
                max_cum_quota = staff.get_max_cum_quota_per_year(quota)
                if is_used_quota:
                    if delta.years > 0:
                        if max_cum_quota:
                            quota_limit = is_used_quota.quota_days
                        else:
                            quota_limit = quota.max_per_year
                    else:
                        quota_limit = quota.first_year
                    type.quota_days = quota_limit
                    db.session.add(type)
                    db.session.commit()
            else:
                flash(u'บุคลากรท่านนี้ยังไม่มีข้อมูลประวัติการลา กรุณาแจ้งหน่วยสารสนเทศ เพื่อดำเนินการเพิ่มเติม', 'danger')
        flash(u'แก้ไขข้อมูลบุคลากรเรียบร้อย', 'success')
        return render_template('staff/staff_show_info.html', staff=staff)
    return render_template('staff/staff_index.html')


@staff.route('/for-hr/staff-info/edit-info/<int:staff_id>/show-info')
@login_required
def staff_show_info(staff_id):
    staff = StaffPersonalInfo.query.get(staff_id)
    return render_template('staff/staff_show_info.html', staff=staff)


@staff.route('/for-hr/staff-info/search-account', methods=['GET', 'POST'])
@login_required
def staff_search_to_change_pwd():
    if request.method == 'POST':
        staff_id = request.form.get('staffname')
        account = StaffAccount.query.filter_by(personal_id=staff_id).first()
        return render_template('staff/staff_edit_pwd.html', account=account)
    return render_template('staff/staff_search_to_change_pwd.html')


@staff.route('/for-hr/staff-info/search-account/edit-pwd/<int:staff_id>', methods=['GET', 'POST'])
@login_required
def staff_edit_pwd(staff_id):
    if request.method == 'POST':
        form = request.form
        staff_email = StaffAccount.query.filter_by(id=staff_id).first()
        staff_email.password = form.get('pwd')
        db.session.add(staff_email)
        db.session.commit()
        flash(u'แก้ไขรหัสผ่านเรียบร้อย')
        return render_template('staff/staff_index.html')
    return render_template('staff/staff_search_to_change_pwd.html')


@staff.route('/for-hr/staff-info/approvers',
             methods=['GET', 'POST'])
@login_required
def staff_show_approvers():
    org_id = request.args.get('deptid')
    departments = Org.query.all()
    if org_id is None:
        account_query = StaffAccount.query.filter(StaffAccount.personal_info.has(retired=False))
    else:
        account_query = StaffAccount.query.filter(StaffAccount.personal_info.has(org_id=org_id))\
                                          .filter(or_(StaffAccount.personal_info.has(retired=False),
                                                      StaffAccount.personal_info.has(retired=None)))

    return render_template('staff/show_leave_approver.html',
                           sel_dept=org_id, account_list=account_query,
                           departments=[{'id': d.id, 'name': d.name} for d in departments])


@staff.route('/for-hr/staff-info/approvers/add/<int:approver_id>',
             methods=['GET', 'POST'])
@login_required
def staff_add_approver(approver_id):
    if request.method == 'POST':
        staff_account_id = request.form.get('staffname')
        find_requester = StaffLeaveApprover.query.filter_by \
            (approver_account_id=approver_id, staff_account_id=staff_account_id).first()
        if find_requester:
            flash(u'ไม่สามารถเพิ่มบุคลากรท่านนี้ได้ เนื่องจากมีข้อมูลบุคลากรท่านนี้อยู่แล้ว', 'warning')
        else:
            createrequester = StaffLeaveApprover(
                staff_account_id=staff_account_id,
                approver_account_id=approver_id
            )
            db.session.add(createrequester)
            db.session.commit()
            flash(u'เพิ่มบุคลากรเรียบร้อยแล้ว', 'success')
    approvers = StaffLeaveApprover.query.filter_by(approver_account_id=approver_id)
    return render_template('staff/leave_request_manage_approver.html', approvers=approvers)


@staff.route('/for-hr/staff-info/approvers/edit/<int:approver_id>/<int:requester_id>/change-active-status')
@login_required
def staff_approver_change_active_status(approver_id, requester_id):
    approver = StaffLeaveApprover.query.filter_by(approver_account_id=approver_id,
                                                  staff_account_id=requester_id).first()
    approver.is_active = True if not approver.is_active else False
    db.session.add(approver)
    db.session.commit()
    flash(u'แก้ไขสถานะการอนุมัติเรียบร้อยแล้ว', 'success')
    return redirect(request.referrer)


@staff.route('/for-hr/staff-info/approvers/add/requester/<int:requester_id>',
             methods=['GET', 'POST'])
@login_required
def staff_add_requester(requester_id):
    if request.method == 'POST':
        approver_account_id = request.form.get('staffname'),
        find_approver = StaffLeaveApprover.query.filter_by \
            (approver_account_id=approver_account_id, staff_account_id=requester_id).first()
        if find_approver:
            flash(u'ไม่สามารถเพิ่มผู้อนุมัติได้เนื่องจากมีผู้อนุมัตินี้อยู่แล้ว', 'warning')
        else:
            createapprover = StaffLeaveApprover(
                approver_account_id=approver_account_id,
                staff_account_id=requester_id
            )
            db.session.add(createapprover)
            db.session.commit()
            flash(u'เพิ่มผู้อนุมัติเรียบร้อยแล้ว', 'success')

    requester = StaffLeaveApprover.query.filter_by(staff_account_id=requester_id)
    requester_name = StaffLeaveApprover.query.filter_by(staff_account_id=requester_id).first()
    name = StaffAccount.query.filter_by(id=requester_id).first()
    return render_template('staff/leave_request_manage_requester.html', approvers=requester,
                           requester_name=requester_name, name=name)


@staff.route('/for-hr/search', methods=['GET', 'POST'])
@login_required
def search_person_for_add_leave_request():
    if request.method == 'POST':
        staff_id = request.form.get('staffname')
        staff = StaffPersonalInfo.query.get(staff_id)
        leave_types = StaffLeaveQuota.query.filter_by(employment_id=staff.employment_id).all()
        approvers = StaffLeaveApprover.query.filter_by(is_active=True).filter_by(
            staff_account_id=staff.staff_account.id).all()
        return render_template('staff/leave_request_add_by_hr.html', staff=staff, approvers=approvers,
                               leave_types=leave_types)
    return render_template('staff/leave_request_search_person_for_hr.html')


@staff.route('/for-hr/search/add-leave-request/<int:staff_id>',
             methods=['GET', 'POST'])
@login_required
def add_leave_request_by_hr(staff_id):
    staff = StaffPersonalInfo.query.get(staff_id)
    leave_types = StaffLeaveQuota.query.filter_by(employment_id=staff.employment_id).all()
    approvers = StaffLeaveApprover.query.filter_by(is_active=True).filter_by(
        staff_account_id=staff.staff_account.id).all()
    if request.method == 'POST':
        form = request.form
        staff_id = StaffAccount.query.filter_by(personal_id=staff_id).first()
        start_t = "08:30"
        end_t = "16:30"
        start_d, end_d = form.get('dates').split(' - ')
        start_dt = '{} {}'.format(start_d, start_t)
        end_dt = '{} {}'.format(end_d, end_t)
        start_datetime = datetime.strptime(start_dt, '%d/%m/%Y %H:%M')
        end_datetime = datetime.strptime(end_dt, '%d/%m/%Y %H:%M')

        START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(start_datetime)
        if start_datetime.date() <= END_FISCAL_DATE.date() and end_datetime.date() > END_FISCAL_DATE.date():
            flash(u'ไม่สามารถลาข้ามปีงบประมาณได้ กรุณาส่งคำร้องแยกกัน 2 ครั้ง โดยแยกตามปีงบประมาณ', 'warning')
            return render_template('staff/leave_request_add_by_hr.html',
                                   staff=staff, approvers=approvers, leave_types=leave_types)
        createleave = StaffLeaveRequest(
            leave_quota_id=form.get('type_id'),
            staff_account_id=staff_id.id,
            created_at=tz.localize(datetime.today()),
            total_leave_days=form.get('total_leave_days'),
            start_datetime=tz.localize(start_datetime),
            end_datetime=tz.localize(end_datetime),
        )
        createleave.after_hour = True if form.getlist("after_hour") else False
        if form.get('traveldates'):
            start_travel_dt, end_travel_dt = form.get('traveldates').split(' - ')
            start_travel_datetime = datetime.strptime(start_travel_dt, '%d/%m/%Y')
            end_travel_datetime = datetime.strptime(end_travel_dt, '%d/%m/%Y')
            createleave.start_travel_datetime = tz.localize(start_travel_datetime)
            createleave.end_travel_datetime = tz.localize(end_travel_datetime)
        if form.get('reason'):
            createleave.reason = form.get('reason')
        if form.get('country'):
            createleave.country = form.get('country')
        upload_file = request.files.get('document')
        if upload_file:
            upload_file_name = secure_filename(upload_file.filename)
            upload_file.save(upload_file_name)
            file_drive = drive.CreateFile({'title': upload_file_name})
            file_drive.SetContentFile(upload_file_name)
            file_drive.Upload()
            permission = file_drive.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
            upload_file_id = file_drive['id']
        else:
            upload_file_id = None
        createleave.upload_file_url = upload_file_id
        db.session.add(createleave)
        if form.get('moreapprovedAt'):
            if form.get('moreapprover_id') == form.get('approver_id'):
                flash(u'ผู้อนุมัติเป็นคนเดียวกัน กรุณาตรวจสอบอีกครั้ง', 'danger')
                return render_template('staff/leave_request_add_by_hr.html',
                                       staff=staff, approvers=approvers, leave_types=leave_types)
        db.session.commit()

        apprved_dt = form.get('approvedAt')
        start_dt = '{} {}'.format(apprved_dt, start_t)
        approved_at = datetime.strptime(start_dt, '%d/%m/%Y %H:%M')
        createleaveapproval = StaffLeaveApproval(
            request_id=createleave.id,
            approver_id=form.get('approver_id'),
            is_approved=True,
            updated_at=tz.localize(approved_at)
        )
        db.session.add(createleaveapproval)
        if form.get('moreapprovedAt'):
            moreapprved_dt = form.get('moreapprovedAt')
            start_dt = '{} {}'.format(moreapprved_dt, start_t)
            moreapproved_at = datetime.strptime(start_dt, '%d/%m/%Y %H:%M')
            createmoreleaveapproval = StaffLeaveApproval(
                request_id=createleave.id,
                approver_id=form.get('moreapprover_id'),
                is_approved=True,
                updated_at=tz.localize(moreapproved_at)
            )
            db.session.add(createmoreleaveapproval)
        if form.get('deanapprovedAt'):
            dean = StaffAccount.query.filter_by(email='chartchalerm.isa').first()
            if not StaffLeaveApprover.query.filter_by(approver_account_id=dean.id).filter_by(
                    staff_account_id=staff_id.id).first():
                createdeanapprover = StaffLeaveApprover(
                    approver_account_id=dean.id,
                    staff_account_id=staff_id.id,
                    is_active=False,
                    notified_by_line=False
                )
                db.session.add(createdeanapprover)
                db.session.commit()
            dean_approver = StaffLeaveApprover.query.filter_by(approver_account_id=dean.id).filter_by(
                staff_account_id=staff_id.id).first()
            start_dean_dt = form.get('deanapprovedAt')
            dean_dt = '{} {}'.format(start_dean_dt, start_t)
            dean_approved_at = datetime.strptime(dean_dt, '%d/%m/%Y %H:%M')
            createdeanapproval = StaffLeaveApproval(
                request_id=createleave.id,
                approver_id=dean_approver.id,
                is_approved=True,
                updated_at=tz.localize(dean_approved_at)
            )
            db.session.add(createdeanapproval)
        db.session.commit()


        START_FISCAL_DATE, END_FISCAL_DATE = get_fiscal_date(createleave.start_datetime)
        quota = StaffLeaveQuota.query.get(createleave.quota.id)
        use_quota = staff.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
                                                                tz.localize(END_FISCAL_DATE))
        pending_days = staff.get_total_pending_leaves_request \
            (quota.id, tz.localize(START_FISCAL_DATE), tz.localize(END_FISCAL_DATE))
        delta = staff.get_employ_period()
        if quota.max_per_leave:
            if delta.years > 0:
                quota_limit = quota.max_per_year
            else:
                quota_limit = quota.first_year
        else:
            max_cum_quota = staff.get_max_cum_quota_per_year(quota)
            if delta.years > 0:
                if max_cum_quota:
                    is_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=createleave.staff,
                                                                        leave_type=quota.leave_type,
                                                                        fiscal_year=END_FISCAL_DATE.year).first()
                    is_last_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=createleave.staff,
                                                                             leave_type=quota.leave_type,
                                                                             fiscal_year=END_FISCAL_DATE.year - 1).first()
                    if not is_used_quota:
                        if is_last_used_quota:
                            last_remain_quota = is_last_used_quota.quota_days - is_last_used_quota.used_days
                        else:
                            last_remain_quota = max_cum_quota
                        before_cut_max_quota = last_remain_quota + LEAVE_ANNUAL_QUOTA
                        quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
                    else:
                        quota_limit = is_used_quota.quota_days
                else:
                    quota_limit = quota.max_per_year
            else:
                quota_limit = quota.first_year

        used_quota = StaffLeaveUsedQuota.query.filter_by(leave_type_id=createleave.quota.leave_type_id,
                                                         staff_account_id=createleave.staff_account_id,
                                                         fiscal_year=END_FISCAL_DATE.year).first()
        if used_quota:
            new_used=used_quota.used_days+createleave.total_leave_days
            used_quota.used_days = new_used
            db.session.add(used_quota)
            db.session.commit()
        else:
            new_used_quota = StaffLeaveUsedQuota(
                leave_type_id=createleave.quota.leave_type_id,
                staff_account_id=current_user.id,
                fiscal_year=END_FISCAL_DATE.year,
                used_days=use_quota+createleave.total_leave_days,
                pending_days=pending_days,
                quota_days=quota_limit
            )
            db.session.add(new_used_quota)
            db.session.commit()

        mails = []
        req_title = u'แจ้งการบันทึกการขอลา' + createleave.quota.leave_type.type_
        req_msg = u'การขออนุมัติ{} ของ{} ระหว่างวันที่ {} ถึงวันที่ {}\nเจ้าหน้าที่หน่วยพัฒนาบุคลากรและการเจ้าหน้าที่ได้ทำการบันทึกลงระบบเรียบร้อยแล้ว' \
                  u'\nคลิกที่ Link เพื่อดูรายละเอียดเพิ่มเติม {}\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'. \
            format(createleave.quota.leave_type.type_, createleave.staff.personal_info.fullname, start_datetime,
                   end_datetime,
                   url_for("staff.record_each_request_leave_request", request_id=createleave.id, _external=True))
        if os.environ["FLASK_ENV"] == "production":
            line_bot_api.push_message(to=staff_id.line_id, messages=TextSendMessage(text=req_msg))
        else:
            print(req_msg, staff_id.email)
        mails.append(staff_id.email + "@mahidol.ac.th")
        if os.environ["FLASK_ENV"] == "production":
            send_mail(mails, req_title, req_msg)
        flash(u'บันทึกการลาเรียบร้อยแล้ว', 'success')
        return redirect(url_for('staff.record_each_request_leave_request', request_id=createleave.id))
    return render_template('staff/leave_request_add_by_hr.html', staff=staff, approvers=approvers,
                           leave_types=leave_types)


@staff.route('/for-hr/cancel-leave-requests/<int:req_id>')
@hr_permission.require()
def cancel_leave_request_by_hr(req_id):
    req = StaffLeaveRequest.query.get(req_id)
    req.cancelled_at = tz.localize(datetime.today())
    req.cancelled_account_id = current_user.id
    db.session.add(req)
    db.session.commit()

    _, END_FISCAL_DATE = get_fiscal_date(req.start_datetime)
    is_used_quota = StaffLeaveUsedQuota.query.filter_by(leave_type_id=req.quota.leave_type_id,
                                                        staff_account_id=req.staff_account_id,
                                                        fiscal_year=END_FISCAL_DATE.year).first()
    quota = req.quota
    used_quota = req.staff.personal_info.get_total_leaves(quota.id, tz.localize(START_FISCAL_DATE),
                                                             tz.localize(END_FISCAL_DATE))
    pending_days = req.staff.personal_info.get_total_pending_leaves_request \
        (quota.id, tz.localize(START_FISCAL_DATE), tz.localize(END_FISCAL_DATE))
    delta = req.staff.personal_info.get_employ_period()
    max_cum_quota = req.staff.personal_info.get_max_cum_quota_per_year(quota)

    if delta.years > 0:
        if max_cum_quota:
            is_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=req.staff,
                                                                leave_type=req.quota.leave_type,
                                                                fiscal_year=END_FISCAL_DATE.year).first()
            is_last_used_quota = StaffLeaveUsedQuota.query.filter_by(staff=req.staff,
                                                                     leave_type=req.quota.leave_type,
                                                                     fiscal_year=END_FISCAL_DATE.year - 1).first()
            if not is_used_quota:
                if is_last_used_quota:
                    last_remain_quota = is_last_used_quota.quota_days - is_last_used_quota.used_days
                else:
                    last_remain_quota = max_cum_quota
                before_cut_max_quota = last_remain_quota + LEAVE_ANNUAL_QUOTA
                quota_limit = max_cum_quota if max_cum_quota < before_cut_max_quota else before_cut_max_quota
            else:
                quota_limit = is_used_quota.quota_days
        else:
            quota_limit = quota.max_per_year

    else:
        quota_limit = req.quota.first_year

    if is_used_quota:
        new_used=is_used_quota.used_days-req.total_leave_days
        is_used_quota.used_days = new_used
        is_used_quota.pending_days = is_used_quota.pending_days-req.total_leave_days
        db.session.add(is_used_quota)
        db.session.commit()
    else:
        new_used_quota = StaffLeaveUsedQuota(
            leave_type_id=req.quota.leave_type_id,
            staff_account_id=req.staff_account_id,
            fiscal_year=END_FISCAL_DATE.year,
            used_days=used_quota,
            pending_days=pending_days,
            quota_days=quota_limit
        )
        db.session.add(new_used_quota)
        db.session.commit()

    cancelled_msg = u'การลา{} ในวันที่ {} ถึง {} ถูกยกเลิกโดย {} เจ้าหน้าที่หน่วย HR แล้ว' \
                    u'\n\n\nหน่วยพัฒนาบุคลากรและการเจ้าหน้าที่\nคณะเทคนิคการแพทย์'.format(req.quota.leave_type.type_,
                                                                                          req.start_datetime,
                                                                                          req.end_datetime,
                                                                                          req.cancelled_by.personal_info
                                                                                          , _external=True)
    if req.notify_to_line and req.staff.line_id:
        if os.environ["FLASK_ENV"] == "production":
            line_bot_api.push_message(to=req.staff.line_id, messages=TextSendMessage(text=cancelled_msg))
        else:
            print(cancelled_msg, req.staff.id)
    cancelled_title = u'แจ้งยกเลิกการขอ' + req.quota.leave_type.type_ + u'โดยเจ้าหน้าที่หน่วย HR'
    if os.environ["FLASK_ENV"] == "production":
        send_mail([req.staff.email + "@mahidol.ac.th"], cancelled_title, cancelled_msg)
    return redirect(request.referrer)


@staff.route('/for-hr/organizations')
@hr_permission.require()
@login_required
def edit_organizations():
    orgs = Org.query.all()
    return render_template('staff/organizations.html', orgs=orgs)


@staff.route('/for-hr/organizations/<int:org_id>/staff', methods=['GET', 'POST'])
@hr_permission.require()
@login_required
def list_org_staff(org_id):
    org = Org.query.get(org_id)
    org_head = StaffAccount.query.filter_by(email=org.head).first()
    if org_head:
        org_head_name = org_head.personal_info.fullname
    else:
        org_head_name = 'N/A'
    if request.method == 'POST':
        for emp_id in request.form.getlist('employees'):
            staff = StaffPersonalInfo.query.get(int(emp_id))
            staff.org = org
            db.session.add(staff)
        db.session.commit()
        flash(u'เพิ่มบุคลากรเข้าสังกัดเรียบร้อยแล้ว', 'success')
    return render_template('staff/org_staff.html', org=org, org_head_name=org_head_name)


@staff.route('/api/staff', methods=['GET'])
@login_required
def get_all_employees():
    search_term = request.args.get('term', '')
    results = []
    for staff in StaffPersonalInfo.query.all():
        if (search_term in staff.fullname or search_term in staff.staff_account.email) \
                and staff.retired is not True:
            results.append({
                "id": staff.id,
                "text": staff.fullname
            })
    return jsonify({'results': results})


@staff.route('/for-hr/organizations/<int:org_id>/staff/<string:email>/make-head')
@hr_permission.require()
@login_required
def make_org_head(org_id, email):
    org = Org.query.get(org_id)
    org.head = email
    db.session.add(org)
    db.session.commit()
    return redirect(url_for('staff.list_org_staff', org_id=org_id))


@staff.route('/for-hr/organizations/<int:org_id>/edit-head-email', methods=['GET', 'POST'])
@hr_permission.require()
@login_required
def edit_org_head_email(org_id):
    org = Org.query.get(org_id)
    if request.method == 'POST':
        email = request.form.get('org_head_email')
        if StaffAccount.get_account_by_email(email):
            org.head = email
            db.session.add(org)
            db.session.commit()
            flash(u'แก้ไขชื่อหัวหน้าหน่วยงานเรียบร้อย', 'success')
            return redirect(url_for('staff.list_org_staff', org_id=org_id))
        else:
            flash(u'ไม่พบบัญชีที่ใช้อีเมล {} กรุณาตรวจสอบอีกครั้ง'.format(email), 'danger')
    return render_template('staff/org_head_email_form.html', org_id=org_id)


@staff.route('/api/users/<int:account_id>/qrcode')
@login_required
def create_qrcode(account_id):
    latitude = request.args.get('lat', '')
    longitude = request.args.get('long', '')
    account = StaffAccount.query.get(account_id)
    qr = qrcode.QRCode(version=1, box_size=20)
    current_time = datetime.now(pytz.utc)
    expired_time = current_time + timedelta(minutes=10)
    qr_data = '|'.join([
        str(account.id),
        latitude,
        longitude,
        expired_time.astimezone(tz).strftime('%H:%M:%S'),
        expired_time.astimezone(tz).strftime('%d/%m/%Y'),
        "",
        account.personal_info.th_title or u'คุณ',
        account.personal_info.th_firstname + ' ' + account.personal_info.th_lastname,
        "",
        account.personal_info.en_title or '',
        account.personal_info.en_firstname + ' ' + account.personal_info.en_lastname,
        u"คณะเทคนิคการแพทย์",
        "FACULTY OF MEDICAL TECHNOLOGY",
    ])
    qr.add_data(qr_data)
    qr.make(fit=True)
    qr_img = qr.make_image()
    qr_img.save('personal_qrcode.png')
    import base64
    with open("personal_qrcode.png", "rb") as img_file:
        qrcode_base64 = base64.b64encode(img_file.read())
    return jsonify(qrcode=qrcode_base64, expDateTime=expired_time.astimezone(tz).isoformat())


@staff.route('/users/qrcode')
@login_required
def show_qrcode():
    return render_template('staff/qrcode.html')


@staff.route('/users/pa_index')
@login_required
def pa_index():
    return render_template('staff/pa_index.html')


@staff.route('/users/teaching-calendar')
@login_required
def teaching_calendar():
    instructor = EduQAInstructor.query.filter_by(account=current_user).first()
    year = request.args.get('year')
    # revision = EduQACurriculumnRevision.query.get(revision_id)
    data = []
    years = set()
    # for session in EduQACourseSession.query.filter(EduQACourseSession.course.has(revision_id=revision_id)).all():
    if instructor:
        for session in instructor.sessions:
            if session.course:
                session_detail = session.details.filter_by(staff_id=current_user.id).first()
                if session_detail:
                    factor = session_detail.factor if session_detail.factor else 1
                else:
                    factor = 1
                print(session.total_seconds * factor, session.total_seconds, factor)
                d = {
                        'course': '<a href="{}">{} ({}/{})</a>'.format(url_for('eduqa.show_course_detail', course_id=session.course.id),
                                                                       session.course.en_code,
                                                                       session.course.semester,
                                                                       session.course.academic_year),
                        'instructor': instructor.account.personal_info.fullname,
                        'seconds': session.total_seconds * factor
                    }
                years.add(str(session.course.academic_year))
                if year:
                    if str(session.course.academic_year) == year:
                        data.append(d)
                else:
                    data.append(d)
        df = DataFrame(data)
    else:
        df = DataFrame(columns=['course', 'instructor', 'seconds'])
    sum_hours = df.pivot_table(index='course',
                               values='seconds',
                               aggfunc='sum',
                               margins=True).apply(lambda x: (x / 3600.0)).fillna('')
    years = sorted(years)
    return render_template('staff/teaching_calendar.html',
                           year=year,
                           instructor=instructor,
                           sum_hours=sum_hours,
                           years=years)


@staff.route('/api/my-teaching-events')
@login_required
def get_my_teaching_events():
    events = []
    end = request.args.get('end')
    start = request.args.get('start')
    if start:
        start = parser.isoparse(start)
    if end:
        end = parser.isoparse(end)
    instructor = EduQAInstructor.query.filter_by(account=current_user).first()
    for evt in instructor.sessions:
        if evt.start >= start and evt.end <= end:
            events.append(evt.to_event())
    return jsonify(events)


@staff.route('/users/teaching-hours/summary')
def show_teaching_hours_summary():
    instructor = EduQAInstructor.query.filter_by(account=current_user).first()
    year = request.args.get('year')
    # revision = EduQACurriculumnRevision.query.get(revision_id)
    data = []
    years = set()
    # for session in EduQACourseSession.query.filter(EduQACourseSession.course.has(revision_id=revision_id)).all():
    for session in instructor.sessions:
        if session.course:
            d = {
                    'course': '<a href="{}">{}</a>'.format(url_for('eduqa.show_course_detail', course_id=session.course.id), session.course.en_code),
                    'instructor': instructor.account.personal_info.fullname,
                    'seconds': session.total_seconds
                }
            years.add(str(session.course.academic_year))
            if year:
                if str(session.course.academic_year) == year:
                    data.append(d)
            else:
                data.append(d)
    df = DataFrame(data)
    sum_hours = df.pivot_table(index='course',
                               values='seconds',
                               aggfunc='sum',
                               margins=True).apply(lambda x: (x / 3600.0)).fillna('')
    years = sorted(years)
    return render_template('eduqa/QA/hours_summary.html',
                           year=year,
                           instructor=instructor,
                           sum_hours=sum_hours,
                           years=years)


