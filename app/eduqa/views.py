# -*- coding:utf-8 -*-

from flask import render_template, request, flash, redirect, url_for
from flask_login import current_user

from . import eduqa_bp as edu
from forms import *


@edu.route('/qa/')
def index():
    return render_template('eduqa/QA/index.html')


@edu.route('/qa/mtc/criteria1')
def criteria1_index():
    return render_template('eduqa/QA/mtc/criteria1.html')


@edu.route('/qa/academic-staff/')
def academic_staff_info_main():
    return render_template('eduqa/QA/staff/index.html')


@edu.route('/qa/academic-staff/academic-position/edit', methods=['GET', 'POST'])
def academic_position_edit():
    form = AcademicPositionRecordForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            record = StaffAcademicPositionRecord()
            form.populate_obj(record)
            record.personal_info = current_user.personal_info
            db.session.add(record)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
            return redirect(url_for('eduqa.academic_staff_info_main'))
        else:
            flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
    return render_template('eduqa/QA/staff/academic_position_edit.html', form=form)


@edu.route('/qa/academic-staff/academic-position/remove/<int:record_id>')
def academic_position_remove(record_id):
    record = StaffAcademicPositionRecord.query.get(record_id)
    if record:
        db.session.delete(record)
        db.session.commit()
        flash(u'ลบรายการเรียบร้อย', 'success')
    else:
        flash(u'ไม่พบรายการในระบบ', 'warning')
    return redirect(url_for('eduqa.academic_staff_info_main'))


@edu.route('/qa/academic-staff/education-record/add', methods=['GET', 'POST'])
def add_education_record():
    form = EduDegreeRecordForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            record = StaffEduDegree()
            form.populate_obj(record)
            record.personal_info = current_user.personal_info
            db.session.add(record)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
            return redirect(url_for('eduqa.academic_staff_info_main'))
        else:
            print(form.errors)
            flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
    return render_template('eduqa/QA/staff/education_edit.html', form=form)


@edu.route('/qa/academic-staff/education-record/edit/<int:record_id>', methods=['GET', 'POST'])
def edit_education_record(record_id):
    record = StaffEduDegree.query.get(record_id)
    form = EduDegreeRecordForm(obj=record)
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(record)
            record.personal_info = current_user.personal_info
            db.session.add(record)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
            return redirect(url_for('eduqa.academic_staff_info_main'))
        else:
            print(form.errors)
            flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
    return render_template('eduqa/QA/staff/education_edit.html', form=form)


@edu.route('/qa/academic-staff/education-record/remove/<int:record_id>', methods=['GET', 'POST'])
def remove_education_record(record_id):
    record = StaffEduDegree.query.get(record_id)
    if record:
        db.session.delete(record)
        db.session.commit()
        flash(u'ลบรายการเรียบร้อย', 'success')
    else:
        flash(u'ไม่พบรายการในระบบ', 'warning')
    return redirect(url_for('eduqa.academic_staff_info_main'))


@edu.route('/qa/program')
def show_programs():
    programs = EduQAProgram.query.all()
    return render_template('eduqa/QA/program.html', programs=programs)



@edu.route('/qa/programs/add', methods=['POST', 'GET'])
def add_program():
    form = EduProgramForm()
    if request.method == 'POST':
        if form.validate_on_submit():
            program = EduQAProgram()
            form.populate_obj(program)
            db.session.add(program)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
            return redirect(url_for('eduqa.index'))
        else:
            print(form.errors)
            flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
    return render_template('eduqa/QA/program_edit.html', form=form)


@edu.route('/qa/programs/edit/<int:program_id>', methods=['POST', 'GET'])
def edit_program(program_id):
    program = EduQAProgram.query.get(program_id)
    form = EduProgramForm(obj=program)
    if request.method == 'POST':
        if form.validate_on_submit():
            form.populate_obj(program)
            db.session.add(program)
            db.session.commit()
            flash(u'บันทึกข้อมูลเรียบร้อย', 'success')
            return redirect(url_for('eduqa.index'))
        else:
            print(form.errors)
            flash(u'ข้อมูลไม่ถูกต้อง กรุณาตรวจสอบ', 'danger')
    return render_template('eduqa/QA/program_edit.html', form=form)
