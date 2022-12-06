# -*- coding:utf-8 -*-
from sqlalchemy.ext.associationproxy import association_proxy

from app.main import db
from app.staff.models import StaffAccount

session_instructors = db.Table('eduqa_session_instructor_assoc',
                               db.Column('session_id', db.Integer, db.ForeignKey('eduqa_course_sessions.id')),
                               db.Column('instructor_id', db.Integer, db.ForeignKey('eduqa_course_instructors.id')),
                               )


class EduQACourseInstructorAssociation(db.Model):
    __tablename__ = 'eduqa_course_instructor_assoc'

    def __init__(self, instructor=None, course=None, role=None):
        self.instructor = instructor
        self.course = course
        self.role = role

    course_id = db.Column('course_id', db.Integer,
                          db.ForeignKey('eduqa_courses.id'), primary_key=True)
    instructor_id = db.Column('instructor_id', db.Integer,
                              db.ForeignKey('eduqa_course_instructors.id'), primary_key=True)
    role_id = db.Column('role_id', db.Integer, db.ForeignKey('eduqa_course_instructor_roles.id'))

    course = db.relationship('EduQACourse', back_populates='course_instructor_associations')
    instructor = db.relationship('EduQAInstructor')
    role = db.relationship('EduQAInstructorRole')


class EduQAProgram(db.Model):
    __tablename__ = 'eduqa_programs'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(255), nullable=False,
                     info={'label': u'ชื่อ'})
    degree = db.Column(db.String(), nullable=False,
                       info={'label': u'ระดับ',
                             'choices': (('undergraduate', 'undergraduate'),
                                         ('graudate', 'graduate'))
                             })


class EduQACurriculum(db.Model):
    __tablename__ = 'eduqa_curriculums'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    program_id = db.Column(db.ForeignKey('eduqa_programs.id'),
                           )
    program = db.relationship(EduQAProgram, backref=db.backref('curriculums'))
    th_name = db.Column(db.String(), nullable=False,
                        info={'label': u'ชื่อ'})
    en_name = db.Column(db.String(), nullable=False,
                        info={'label': 'Title'})

    def __str__(self):
        return self.th_name


class EduQACurriculumnRevision(db.Model):
    __tablename__ = 'eduqa_curriculum_revisions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    curriculum_id = db.Column(db.ForeignKey('eduqa_curriculums.id'))
    curriculum = db.relationship(EduQACurriculum, backref=db.backref('revisions'))
    revision_year = db.Column(db.Date(), nullable=False, info={'label': u'วันที่ปรับปรุงล่าสุด'})

    def __str__(self):
        return u'{}: ปี {}'.format(self.curriculum, self.revision_year)


class EduQAAcademicStaff(db.Model):
    __tablename__ = 'eduqa_academic_staff'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    roles = db.Column(db.String(), info={'label': u'บทบาท',
                                         'choices': (
                                             ('staff', u'อาจารย์ประจำ'),
                                             ('head', u'ประธานหลักสูตร'),
                                             ('committee', u'ผู้รับผิดชอบหลักสูตร')
                                         )})
    curriculumn_id = db.Column(db.ForeignKey('eduqa_curriculum_revisions.id'))
    curriculumn = db.relationship(EduQACurriculumnRevision, backref=db.backref('staff'))


class EduQACourseCategory(db.Model):
    __tablename__ = 'eduqa_course_categories'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category = db.Column(db.String(255), nullable=False)


class EduQACourse(db.Model):
    __tablename__ = 'eduqa_courses'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    th_code = db.Column(db.String(255), nullable=False, info={'label': u'รหัส'})
    en_code = db.Column(db.String(255), nullable=False, info={'label': u'English Code'})
    th_name = db.Column(db.String(255), nullable=False, info={'label': u'ชื่อภาษาไทย'})
    en_name = db.Column(db.String(255), nullable=False, info={'label': u'English Title'})
    semester = db.Column(db.String(), info={'label': u'ภาคการศึกษา'})
    academic_year = db.Column(db.String(), info={'label': u'ปีการศึกษา'})
    th_desc = db.Column(db.Text(), info={'label': u'คำอธิบายรายวิชา'})
    en_desc = db.Column(db.Text(), info={'label': u'Description'})
    lecture_credit = db.Column(db.Numeric(), default=0, info={'label': u'หน่วยกิตบรรยาย'})
    lab_credit = db.Column(db.Numeric(), default=0, info={'label': u'หน่วยกิตปฏิบัติ'})
    created_at = db.Column(db.DateTime(timezone=True))
    updated_at = db.Column(db.DateTime(timezone=True))

    creator_id = db.Column(db.ForeignKey('staff_account.id'))
    updater_id = db.Column(db.ForeignKey('staff_account.id'))

    creator = db.relationship(StaffAccount, foreign_keys=[creator_id])
    updater = db.relationship(StaffAccount, foreign_keys=[updater_id])

    category_id = db.Column(db.ForeignKey('eduqa_course_categories.id'))
    category = db.relationship(EduQACourseCategory,
                               backref=db.backref('courses', lazy='dynamic'))

    revision_id = db.Column(db.ForeignKey('eduqa_curriculum_revisions.id'))
    revision = db.relationship(EduQACurriculumnRevision,
                               backref=db.backref('courses', lazy='dynamic'))

    instructors = association_proxy('course_instructor_associations', 'instructor')
    course_instructor_associations = db.relationship('EduQACourseInstructorAssociation',
                                                    back_populates='course', cascade='all, delete-orphan')

    @property
    def credits(self):
        return self.lecture_credit + self.lab_credit


class EduQAInstructor(db.Model):
    __tablename__ = 'eduqa_course_instructors'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    account_id = db.Column(db.ForeignKey('staff_account.id'))
    account = db.relationship(StaffAccount, backref=db.backref('instructed_courses', lazy='dynamic'))
    # courses = db.relationship(EduQACourseInstructorAssociation, back_populates='instructor')

    def __init__(self, account_id):
        self.account_id = account_id

    @property
    def fullname(self):
        return self.account.personal_info.fullname


class EduQAInstructorRole(db.Model):
    __tablename__ = 'eduqa_course_instructor_roles'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role = db.Column('role', db.String())
    admin = db.Column('admin', db.Boolean(), default=False)
    credit_hour = db.Column('credit_hour', db.Integer(), default=0)


class EduQACourseSession(db.Model):
    __tablename__ = 'eduqa_course_sessions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    course_id = db.Column(db.ForeignKey('eduqa_courses.id'))
    start = db.Column(db.DateTime(timezone=True), nullable=False, info={'label': u'เริ่ม'})
    end = db.Column(db.DateTime(timezone=True), nullable=False, info={'label': u'สิ้นสุด'})
    type_ = db.Column(db.String(255), info={'label': u'รูปแบบการสอน',
                                            'choices': [(c, c) for c in (u'บรรยาย', u'ปฏิบัติการ', u'กิจกรรม', u'สอบ')]})
    desc = db.Column(db.Text())

    course = db.relationship(EduQACourse, backref=db.backref('sessions', lazy='dynamic'))
    instructors = db.relationship('EduQAInstructor',
                                  secondary=session_instructors,
                                  backref=db.backref('sessions', lazy='dynamic'))
    format = db.Column('format', db.String(),
                       info={'label': u'รูปแบบ', 'choices': [(c, c) for c in [u'ออนไซต์', u'ออนไลน์']]})

    @property
    def total_hours(self):
        delta = self.end - self.start
        return u'{} ชม. {} นาที'.format(delta.seconds//3600, (delta.seconds//60)%60)

    @property
    def total_seconds(self):
        delta = self.end - self.start
        return delta.seconds
    @property
    def topics(self):
        topics = []
        for detail in self.details:
            topics += [topic for topic in detail.topics]
        return topics


class EduQACourseSessionTopic(db.Model):
    __tablename__ = 'eduqa_course_session_topics'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column('session_id', db.ForeignKey('eduqa_course_sessions.id'))
    session = db.relationship(EduQACourseSession, backref=db.backref('topics',
                                                                     cascade='all, delete-orphan'))
    topic = db.Column('topic', db.String(), nullable=False, info={'label': u'หัวข้อ'})
    method = db.Column('method', db.String(),
                       info={'label': u'รูปแบบการจัดการสอน',
                             'choices': [(c, c) for c in [u'บรรยาย', u'ปฏิบัติ', u'อภิปราย', u'กิจกรรมกลุ่ม', u'สาธิต']]})


class EduQACourseSessionDetail(db.Model):
    __tablename__ = 'eduqa_course_session_details'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.ForeignKey('eduqa_course_sessions.id'))
    staff_id = db.Column(db.ForeignKey('staff_account.id'))
    session = db.relationship(EduQACourseSession, backref=db.backref('details', cascade='all, delete-orphan'))


class EduQACourseSessionDetailRole(db.Model):
    __tablename__ = 'eduqa_course_session_detail_roles'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_detail_id = db.Column(db.ForeignKey('eduqa_course_session_details.id'))
    detail = db.Column('detail', db.Text(), info={'label': u'รายละเอียด'})
    session_detail = db.relationship(EduQACourseSessionDetail,
                                     backref=db.backref('roles', cascade='all, delete-orphan'))
    role = db.Column('role', db.String(), info={'label': u'บทบาท',
                                                'choices': [(c, c) for c in [u'ผู้บรรยายหลัก',
                                                                             u'ผู้บรรยายเสริม',
                                                                             u'ผู้นำอภิปราย',
                                                                             u'ผู้ร่วมอภิปราย',
                                                                             u'ผู้ดำเนินการอภิปราย',
                                                                             u'ผู้สอนปฏิบัติหลัก',
                                                                             u'ผู้ร่วมสอนปฏิบัติ',
                                                                             u'ผู้คุมสอบ',
                                                                             ]],
                                                })
