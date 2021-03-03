# -*- coding:utf-8 -*-
from datetime import datetime

from flask import render_template, request, flash, redirect, url_for, jsonify
from flask_cors import cross_origin
from sqlalchemy import extract

from models import *
from forms import *
from . import health_service_blueprint as hs
from app.main import csrf
from pytz import timezone
from flask_login import login_required, current_user

localtz = timezone('Asia/Bangkok')

@hs.route('/')
@login_required
def index():
    return render_template('health_service_scheduler/index.html')


@hs.route('/sites/add', methods=['GET', 'POST'])
@login_required
def add_site():
    form = ServiceSiteForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            site = HealthServiceSite()
            form.populate_obj(site)
            db.session.add(site)
            db.session.commit()
            flash(u'New site has been added.', 'success')
            return redirect(url_for('health_service_scheduler.get_sites'))
        else:
            for field, err in form.errors:
                flash(u'{}:{}'.format(field, err), 'danger')
    return render_template('health_service_scheduler/site_form.html', form=form)


@hs.route('/sites')
@login_required
def get_sites():
    sites = HealthServiceSite.query.all()
    return render_template('health_service_scheduler/sites.html', sites=sites)


@hs.route('/services')
@login_required
def get_services():
    services = HealthServiceService.query.all()
    return render_template('health_service_scheduler/services.html', services=services)


@hs.route('/services/add', methods=['GET', 'POST'])
@login_required
def add_service():
    form = ServiceForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            service = HealthServiceService()
            form.populate_obj(service)
            db.session.add(service)
            db.session.commit()
            flash(u'New service has been added.', 'success')
            return redirect(url_for('health_service_scheduler.get_services'))
        else:
            for field, err in form.errors:
                flash(u'{}:{}'.format(field, err), 'danger')
    return render_template('health_service_scheduler/service_form.html', form=form)


@hs.route('/slots/add', methods=['GET', 'POST'])
@login_required
def add_slot():
    form = ServiceSlotForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            slot = HealthServiceTimeSlot()
            form.populate_obj(slot)
            start = localtz.localize(slot.start)
            end = localtz.localize(slot.end)
            if start >= end:
                flash(u'ช่วงเวลาไม่ถูกต้อง กรุณาเลือกช่วงเวลาใหม่', 'danger')
            else:
                slot.start = start
                slot.end = end
                slot.created_at = datetime.now(localtz).astimezone(localtz)
                slot.created_by = current_user
                db.session.add(slot)
                db.session.commit()
                flash(u'New time slot has been added.', 'success')
                return redirect(url_for('health_service_scheduler.show_slots'))
        else:
            for field, err in form.errors:
                flash(u'{}:{}'.format(field, err), 'danger')
    return render_template('health_service_scheduler/slot_form.html', form=form)


@hs.route('/slots')
@login_required
def show_slots():
    mode = request.args.get('mode', 'agendaWeek')
    return render_template('health_service_scheduler/slots.html', mode=mode)


@hs.route('/bookings')
@login_required
def show_bookings():
    services = HealthServiceService.query.all()
    return render_template('health_service_scheduler/bookings.html', services=services)


@hs.route('/services/<int:service_id>/bookings')
@login_required
def show_bookings_by_service(service_id):
    bookings = HealthServiceBooking.query.all()
    return render_template('health_service_scheduler/service_bookings.html',
                           bookings=[booking for booking in bookings
                                     if booking.slot.service.id == service_id])

@hs.route('/bookings/<int:booking_id>')
@login_required
def show_booking_detail(booking_id):
    booking = HealthServiceBooking.query.get(booking_id)
    return render_template('health_service_scheduler/booking_detail.html',
                           booking=booking)


@hs.route('/bookings/<int:booking_id>/confirm')
@login_required
def confirm_booking(booking_id):
    booking = HealthServiceBooking.query.get(booking_id)
    booking.confirmed_at = datetime.now(localtz).astimezone(localtz)
    db.session.add(booking)
    db.session.commit()
    return redirect(url_for('health_service_scheduler.show_bookings'))


@hs.route('/api/calendar/slots')
@login_required
def get_slots_calendar_api():
    # only query events of the current year to reduce load time
    slots = HealthServiceTimeSlot.query\
        .filter(extract('year', HealthServiceTimeSlot.start) == datetime.today().year)
    slot_data = []
    for evt in slots:
        if not evt.cancelled_at:
            slot_data.append({
                'id': evt.id,
                'start': evt.start.astimezone(localtz).isoformat(),
                'end': evt.end.astimezone(localtz).isoformat(),
                'title': u'{} ({}) by {}'.format(evt.service.name,evt.quota, evt.created_by.personal_info.th_firstname),
                'quota': evt.quota,
                'resourceId': evt.site.id,
                'site': evt.site.name
            })
    return jsonify(slot_data)


@hs.route('/api/calendar/sites')
def get_sites_calendar_api():
    sites = HealthServiceSite.query.all()
    site_data = []
    for s in sites:
        site_data.append({
            'id': s.id,
            'title': s.name,
        })
    return jsonify(site_data)


@hs.route('/api/bookings/add', methods=['POST'])
@csrf.exempt
@cross_origin(support_credentials=True)
def add_booking():
    data = request.get_json()
    print(data)
    slot = HealthServiceTimeSlot.query.get(int(data.get('slotId', 0)))
    # user = HealthServiceAppUser.query.filter_by(line_id=data.get('lineId', 'abcd')).first()
    if slot and slot.is_available:
        booking = HealthServiceBooking()
        booking.slot = slot
        booking.user = HealthServiceAppUser.query.first()
        booking.created_at = datetime.now(localtz).astimezone(localtz)
        '''
        if not user:
            new_user = HealthServiceAppUser(line_id=data['lineId'])
            booking.user = new_user
        else:
            booking.user = user
        '''
        db.session.add(booking)
        db.session.commit()
        return jsonify({'status': 'success'})
    return jsonify({'status': 'failed'})