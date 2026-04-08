from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, require_role
from app.db.deps import get_db
from app.models.notice import Notice
from app.models.school import (
    SchoolFeeStructure,
    SchoolParentStudent,
    SchoolStudent,
    SchoolTeacherClass,
    SchoolTimetableEntry,
)
from app.models.user import User
from app.schemas.mobile import (
    AppAttendanceOut,
    AppDashboardOut,
    AppFeeItemOut,
    AppFeesOut,
    AppMeOut,
    AppNoticeOut,
    AppStudentProfileOut,
    AppTimetableItemOut,
)

router = APIRouter(prefix="/app", tags=["Mobile App"])


# =========================================================
# Helpers
# =========================================================

def _notice_to_out(item: Notice) -> AppNoticeOut:
    return AppNoticeOut(
        id=item.id,
        title=item.title,
        message=item.message,
        audience=item.audience,
    )


def _student_to_profile_out(student: SchoolStudent) -> AppStudentProfileOut:
    fee_total = int(student.fee_total or 0)
    fee_paid = int(student.fee_paid or 0)

    return AppStudentProfileOut(
        id=student.id,
        name=student.name,
        class_id=student.class_id,
        class_name=student.school_class.name if getattr(student, "school_class", None) else "",
        section=student.section or "",
        roll_no=student.roll_no or "",
        guardian_name=student.guardian_name or "",
        phone=student.phone or "",
        attendance_percentage=int(student.attendance_percentage or 0),
        fee_total=fee_total,
        fee_paid=fee_paid,
        fee_balance=max(fee_total - fee_paid, 0),
    )


def _timetable_to_out(item: SchoolTimetableEntry) -> AppTimetableItemOut:
    return AppTimetableItemOut(
        id=item.id,
        timetable_type=item.timetable_type,
        day_name=item.day_name,
        period_no=item.period_no,
        period_label=item.period_label or "",
        subject=item.subject or "",
        start_time=item.start_time or "",
        end_time=item.end_time or "",
        teacher_name=item.teacher.teacher_name if getattr(item, "teacher", None) else "",
        room=item.room or "",
        remark=item.remark or "",
        status=item.status,
    )


def _require_student_entity(user: User, db: Session) -> SchoolStudent:
    if not user.school_student_id:
        raise HTTPException(
            status_code=400,
            detail="This student user is not linked to a school student record yet",
        )

    student = (
        db.query(SchoolStudent)
        .options(
            joinedload(SchoolStudent.school_class),
            joinedload(SchoolStudent.primary_parent),
        )
        .filter(SchoolStudent.id == user.school_student_id)
        .first()
    )
    if not student:
        raise HTTPException(status_code=404, detail="Linked student record not found")
    return student


def _require_parent_student(user: User, db: Session) -> SchoolStudent:
    if not user.school_parent_id:
        raise HTTPException(
            status_code=400,
            detail="This parent user is not linked to a school parent record yet",
        )

    link = (
        db.query(SchoolParentStudent)
        .options(
            joinedload(SchoolParentStudent.student).joinedload(SchoolStudent.school_class),
            joinedload(SchoolParentStudent.parent),
        )
        .filter(SchoolParentStudent.parent_id == user.school_parent_id)
        .order_by(SchoolParentStudent.is_primary.desc(), SchoolParentStudent.id.asc())
        .first()
    )

    if not link or not link.student:
        raise HTTPException(
            status_code=404,
            detail="No student is linked to this parent record yet",
        )

    return link.student


def _require_teacher_class_ids(user: User, db: Session) -> list[int]:
    if not user.school_teacher_id:
        raise HTTPException(
            status_code=400,
            detail="This teacher user is not linked to a school teacher record yet",
        )

    class_ids = [
        row.class_id
        for row in db.query(SchoolTeacherClass)
        .filter(SchoolTeacherClass.teacher_id == user.school_teacher_id)
        .all()
    ]

    if not class_ids:
        raise HTTPException(
            status_code=404,
            detail="No classes are linked to this teacher record yet",
        )

    return sorted(set(class_ids))


def _build_fees_out(student: SchoolStudent, db: Session) -> AppFeesOut:
    fee_structure = (
        db.query(SchoolFeeStructure)
        .filter(SchoolFeeStructure.class_id == student.class_id)
        .first()
    )

    items = []
    academic_year = ""

    if fee_structure:
        academic_year = fee_structure.academic_year or ""
        raw_items = [
            ("Admission Fee", int(fee_structure.admission_fee or 0)),
            ("Tuition Fee", int(fee_structure.tuition_fee or 0)),
            ("Exam Fee", int(fee_structure.exam_fee or 0)),
            ("Transport Fee", int(fee_structure.transport_fee or 0)),
            ("Miscellaneous Fee", int(fee_structure.misc_fee or 0)),
        ]
        items = [
            AppFeeItemOut(fee_head=head, amount=amount)
            for head, amount in raw_items
            if amount > 0
        ]

    fee_total = int(student.fee_total or 0)
    fee_paid = int(student.fee_paid or 0)

    return AppFeesOut(
        class_name=student.school_class.name if getattr(student, "school_class", None) else "",
        academic_year=academic_year,
        fee_total=fee_total,
        fee_paid=fee_paid,
        fee_balance=max(fee_total - fee_paid, 0),
        items=items,
    )


def _build_attendance_out(student: SchoolStudent) -> AppAttendanceOut:
    percentage = int(student.attendance_percentage or 0)
    total_days = 100
    present_days = round((percentage / 100) * total_days)
    absent_days = max(total_days - present_days, 0)

    return AppAttendanceOut(
        attendance_percentage=percentage,
        present_days=present_days,
        absent_days=absent_days,
        total_days=total_days,
    )


def _build_dashboard_out(student: SchoolStudent, db: Session, audience: str) -> AppDashboardOut:
    notices_count = (
        db.query(Notice)
        .filter(Notice.audience.in_(["all", audience]))
        .count()
    )

    today_name = "Monday"
    periods = (
        db.query(SchoolTimetableEntry)
        .filter(
            SchoolTimetableEntry.class_id == student.class_id,
            SchoolTimetableEntry.timetable_type == "Regular",
            SchoolTimetableEntry.day_name == today_name,
            SchoolTimetableEntry.status == "Active",
        )
        .count()
    )

    fee_total = int(student.fee_total or 0)
    fee_paid = int(student.fee_paid or 0)

    return AppDashboardOut(
        student_name=student.name,
        class_name=student.school_class.name if getattr(student, "school_class", None) else "",
        section=student.section or "",
        roll_no=student.roll_no or "",
        attendance_percentage=int(student.attendance_percentage or 0),
        fee_total=fee_total,
        fee_paid=fee_paid,
        fee_balance=max(fee_total - fee_paid, 0),
        notices_count=notices_count,
        today_periods=periods,
    )


def _list_notices(db: Session, audiences: list[str]) -> list[AppNoticeOut]:
    rows = (
        db.query(Notice)
        .filter(Notice.audience.in_(audiences))
        .order_by(Notice.id.desc())
        .all()
    )
    return [_notice_to_out(x) for x in rows]


def _list_timetable(
    db: Session,
    class_id: int,
    day_name: str,
    timetable_type: str,
    teacher_id: int | None = None,
) -> list[AppTimetableItemOut]:
    query = (
        db.query(SchoolTimetableEntry)
        .options(joinedload(SchoolTimetableEntry.teacher))
        .filter(
            SchoolTimetableEntry.class_id == class_id,
            SchoolTimetableEntry.day_name == day_name.strip().title(),
            SchoolTimetableEntry.timetable_type == timetable_type.strip().title(),
        )
    )

    if teacher_id:
        query = query.filter(SchoolTimetableEntry.teacher_id == teacher_id)

    rows = query.order_by(SchoolTimetableEntry.period_no.asc()).all()
    return [_timetable_to_out(x) for x in rows]


# =========================================================
# Common
# =========================================================

@router.get("/me", response_model=AppMeOut)
def app_me(user: User = Depends(get_current_user)):
    linked_entity_id = None

    if user.role == "student":
        linked_entity_id = user.school_student_id
    elif user.role == "parent":
        linked_entity_id = user.school_parent_id
    elif user.role == "teacher":
        linked_entity_id = user.school_teacher_id

    return AppMeOut(
        user_id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        linked_entity_id=linked_entity_id,
    )


# =========================================================
# Student App
# =========================================================

@router.get("/student/profile", response_model=AppStudentProfileOut)
def student_profile(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    student = _require_student_entity(user, db)
    return _student_to_profile_out(student)


@router.get("/student/dashboard", response_model=AppDashboardOut)
def student_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    student = _require_student_entity(user, db)
    return _build_dashboard_out(student, db, "student")


@router.get("/student/attendance", response_model=AppAttendanceOut)
def student_attendance(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    student = _require_student_entity(user, db)
    return _build_attendance_out(student)


@router.get("/student/fees", response_model=AppFeesOut)
def student_fees(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    student = _require_student_entity(user, db)
    return _build_fees_out(student, db)


@router.get("/student/timetable", response_model=list[AppTimetableItemOut])
def student_timetable(
    day_name: str = Query(default="Monday"),
    timetable_type: str = Query(default="Regular"),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    student = _require_student_entity(user, db)
    return _list_timetable(db, student.class_id, day_name, timetable_type)


@router.get("/student/notices", response_model=list[AppNoticeOut])
def student_notices(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("student")),
):
    _require_student_entity(user, db)
    return _list_notices(db, ["all", "student"])


# =========================================================
# Parent App
# =========================================================

@router.get("/parent/child-profile", response_model=AppStudentProfileOut)
def parent_child_profile(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("parent")),
):
    student = _require_parent_student(user, db)
    return _student_to_profile_out(student)


@router.get("/parent/dashboard", response_model=AppDashboardOut)
def parent_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("parent")),
):
    student = _require_parent_student(user, db)
    return _build_dashboard_out(student, db, "parent")


@router.get("/parent/attendance", response_model=AppAttendanceOut)
def parent_attendance(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("parent")),
):
    student = _require_parent_student(user, db)
    return _build_attendance_out(student)


@router.get("/parent/fees", response_model=AppFeesOut)
def parent_fees(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("parent")),
):
    student = _require_parent_student(user, db)
    return _build_fees_out(student, db)


@router.get("/parent/timetable", response_model=list[AppTimetableItemOut])
def parent_timetable(
    day_name: str = Query(default="Monday"),
    timetable_type: str = Query(default="Regular"),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("parent")),
):
    student = _require_parent_student(user, db)
    return _list_timetable(db, student.class_id, day_name, timetable_type)


@router.get("/parent/notices", response_model=list[AppNoticeOut])
def parent_notices(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("parent")),
):
    _require_parent_student(user, db)
    return _list_notices(db, ["all", "parent"])


# =========================================================
# Teacher App
# =========================================================

@router.get("/teacher/classes")
def teacher_classes(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher")),
):
    class_ids = _require_teacher_class_ids(user, db)

    rows = (
        db.query(SchoolTeacherClass)
        .options(
            joinedload(SchoolTeacherClass.school_class),
        )
        .filter(SchoolTeacherClass.teacher_id == user.school_teacher_id)
        .order_by(SchoolTeacherClass.id.asc())
        .all()
    )

    return [
        {
            "id": row.school_class.id,
            "name": row.school_class.name if row.school_class else "",
            "is_primary": bool(row.is_primary),
        }
        for row in rows
        if row.school_class and row.class_id in class_ids
    ]


@router.get("/teacher/students", response_model=list[AppStudentProfileOut])
def teacher_students(
    class_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher")),
):
    class_ids = _require_teacher_class_ids(user, db)

    if class_id and class_id not in class_ids:
        raise HTTPException(
            status_code=403,
            detail="You are not mapped to the requested class",
        )

    target_class_ids = [class_id] if class_id else class_ids

    rows = (
        db.query(SchoolStudent)
        .options(joinedload(SchoolStudent.school_class))
        .filter(SchoolStudent.class_id.in_(target_class_ids))
        .order_by(SchoolStudent.class_id.asc(), SchoolStudent.roll_no.asc(), SchoolStudent.name.asc())
        .all()
    )

    return [_student_to_profile_out(x) for x in rows]


@router.get("/teacher/timetable", response_model=list[AppTimetableItemOut])
def teacher_timetable(
    class_id: int | None = Query(default=None),
    day_name: str = Query(default="Monday"),
    timetable_type: str = Query(default="Regular"),
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher")),
):
    class_ids = _require_teacher_class_ids(user, db)

    target_class_id = class_id or class_ids[0]

    if target_class_id not in class_ids:
        raise HTTPException(
            status_code=403,
            detail="You are not mapped to the requested class",
        )

    return _list_timetable(
        db=db,
        class_id=target_class_id,
        day_name=day_name,
        timetable_type=timetable_type,
        teacher_id=user.school_teacher_id,
    )


@router.get("/teacher/notices", response_model=list[AppNoticeOut])
def teacher_notices(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher")),
):
    _require_teacher_class_ids(user, db)
    return _list_notices(db, ["all", "teacher"])


@router.get("/teacher/dashboard")
def teacher_dashboard(
    db: Session = Depends(get_db),
    user: User = Depends(require_role("teacher")),
):
    class_ids = _require_teacher_class_ids(user, db)

    total_students = (
        db.query(SchoolStudent)
        .filter(SchoolStudent.class_id.in_(class_ids))
        .count()
    )

    total_notices = (
        db.query(Notice)
        .filter(Notice.audience.in_(["all", "teacher"]))
        .count()
    )

    total_timetable_entries = (
        db.query(SchoolTimetableEntry)
        .filter(
            SchoolTimetableEntry.class_id.in_(class_ids),
            SchoolTimetableEntry.teacher_id == user.school_teacher_id,
            SchoolTimetableEntry.status == "Active",
        )
        .count()
    )

    return {
        "teacher_id": user.school_teacher_id,
        "class_count": len(class_ids),
        "student_count": total_students,
        "notice_count": total_notices,
        "timetable_entries": total_timetable_entries,
    }
