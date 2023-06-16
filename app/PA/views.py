# -*- coding:utf-8 -*-
import datetime
import pytz
from sqlalchemy import and_
from . import pa_blueprint as pa

from flask_login import login_required, current_user
from flask import render_template, request, redirect, url_for, flash
from app.PA.models import *
from app.roles import hr_permission, manager_permission
from ..models import Org
from app.PA.forms import PACommitteeForm, PARequestForm, create_rate_performance_form, create_pa_scoresheet_form

tz = pytz.timezone('Asia/Bangkok')

@pa.route('/pa/')
@login_required
def index():
    return render_template('pa/index.html', hr_permission=hr_permission, manager_permission=manager_permission)


@pa.route('/hr/create-round', methods=['GET', 'POST'])
@login_required
def create_round():
    pa_round = PARound.query.all()
    if request.method == 'POST':
        form = request.form
        start_d, end_d = form.get('dates').split(' - ')
        start = datetime.datetime.strptime(start_d, '%d/%m/%Y')
        end = datetime.datetime.strptime(end_d, '%d/%m/%Y')
        createround = PARound(
            start=tz.localize(start),
            end=tz.localize(end)
        )
        db.session.add(createround)
        db.session.commit()
        flash('เพิ่มรอบการประเมินใหม่เรียบร้อยแล้ว', 'success')
        return redirect(url_for('pa.create_round'))
    return render_template('pa/hr_create_round.html', pa_round=pa_round)


@pa.route('/hr/add-committee', methods=['GET', 'POST'])
@login_required
def add_commitee():
    form = PACommitteeForm()
    if form.validate_on_submit():
        commitee = PACommittee()
        form.populate_obj(commitee)
        db.session.add(commitee)
        db.session.commit()
        flash('เพิ่มผู้ประเมินใหม่เรียบร้อยแล้ว', 'success')
    else:
        for err in form.errors:
            flash('{}: {}'.format(err, form.errors[err]), 'danger')
    return render_template('pa/hr_add_committee.html', form=form)


@pa.route('/hr/committee', methods=['GET', 'POST'])
@login_required
def show_commitee():
    #TODO: org filter
    org_id = request.args.get('deptid')
    departments = Org.query.all()
    if org_id is None:
        committee_list = PACommittee.query.all()
    else:
        committee_list = PACommittee.query.filter(PACommittee.has(org_id=org_id))
    return render_template('pa/hr_show_committee.html',
                           sel_dept=org_id, committee_list=committee_list,
                           departments=[{'id': d.id, 'name': d.name} for d in departments])


@pa.route('/head/requests')
@login_required
def all_request():
    all_req = PARequest.query.filter_by(supervisor_id=current_user.id).filter(PARequest.submitted_at!=None).all()
    #all_req = PARequest.query.filter_by(supervisor_id=current_user.id).all()
    return render_template('pa/head_all_request.html', all_req=all_req)


@pa.route('/head/request/<int:request_id>', methods=['GET', 'POST'])
@login_required
def respond_request(request_id):
    req = PARequest.query.get(request_id)
    form = PARequestForm(obj=req)
    #TODO: for_ required
    if form.validate_on_submit():
        form.populate_obj(req)
        req.responded_at = datetime.datetime.now(tz)
        db.session.add(req)
        db.session.commit()
        flash('บันทึกผลเรียบร้อยแล้ว', 'success')
        return redirect(url_for('pa.all_request'))
    else:
        for err in form.errors:
            flash('{}: {}'.format(err, form.errors[err]), 'danger')
    return render_template('pa/head_respond_request.html', form=form, req=req)


@pa.route('/cmte/all_pa_agreement', methods=['GET', 'POST'])
@login_required
def all_pa_agreement():
    #pa = PAAgreement.query.filter(and_(PARequest.submitted_at !='',PARequest.for_=='ขอรับการประเมิน')).all()
    pa = PAAgreement.query.all()
    return render_template('pa/cmte_all_pa_agreement.html', pa=pa)


@pa.route('/cmte/head/all_performance/<int:scoresheet_id>', methods=['GET', 'POST'])
@login_required
def all_performance(scoresheet_id):
    scoresheet = PAScoreSheet.query.filter_by(id=scoresheet_id).first()
    return render_template('pa/cmte_all_performance.html', scoresheet=scoresheet)


@pa.route('/cmte/head/all_performance/<int:pa_id>/item/<int:item_id>', methods=['GET', 'POST'])
@login_required
def rate_performance(pa_id, item_id):
    pa_item = PAItem.query.filter_by(id=item_id).first()
    ScoreItemForm = create_rate_performance_form(pa_id)
    # TODO: check case duplicate attend
    form = ScoreItemForm()
    if form.validate_on_submit():
        score_item = PAScoreSheetItem()
        form.populate_obj(score_item)
    return render_template('pa/cmte_rate_performance.html', form=form, pa_item=pa_item, pa_id=pa_id)


@pa.route('/cmte/all-scoresheet', methods=['GET', 'POST'])
@login_required
def all_scoresheet():
    # evaluator = PAScoreSheet.query.filter(PACommittee.org_id).all()
    pa = PAAgreement.query.filter(and_(PARequest.submitted_at !='',
                                       PARequest.for_=='ขอรับการประเมิน')).all()
    return render_template('pa/cmte_all_scoresheet.html', pa=pa)


@pa.route('/head/create-scoresheet/<int:pa_id>', methods=['GET', 'POST'])
@login_required
def create_scoresheet(pa_id):
    #scoresheet = PAScoreSheet.query.filter_by(pa_id=pa_id, committee_id=current_user.id).first()
    scoresheet = PAScoreSheet.query.all()
    return render_template('pa/cmte_all_performance.html', scoresheet=scoresheet)
    # if not scoresheet:
    #     create_scoresheet = PAScoreSheet(
    #         pa_id=pa_id,
    #         committee_id=current_user.id
    #     )
    #     db.session.add(create_scoresheet)
    #     db.session.commit()
    #
    #     pa_kpi = PAKPI.query.filter_by(pa_id=pa_id).all()
    #     for kpi in pa_kpi:
    #         pa_item = PAItem.query.filter_by(pa_id=pa_id).all()
    #         for item in pa_item:
    #             create_scoresheet_item = PAScoreSheetItem(
    #                 score_sheet_id=create_scoresheet.id,
    #                 item_id=item.id,
    #                 kpi_id=kpi.id
    #             )
    #             db.session.add(create_scoresheet_item)
    #             db.session.commit()
    #     return render_template('pa/all_performance.html', pa_id=pa_id)
    # else:
    #     return render_template('pa/all_performance.html', scoresheet_id=scoresheet.id)
