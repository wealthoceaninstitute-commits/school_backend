import re
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.db.deps import get_db
from app.core.security import hash_password
from app.api.deps import require_role

from app.models.school import (
    SchoolClass,
    SchoolSection,
    SchoolStudent,
    SchoolParent,
    SchoolParentStudent,
    SchoolTeacher,
    SchoolTeacherAttendance,
    SchoolTeacherClass,
    SchoolFeeStructure,
    SchoolSubject,
    SchoolTimetableEntry,
)

from app.schemas.school import (
    ClassCreate,
    ClassUpdate,
    ClassOut,
    StudentCreate,
    StudentUpdate,
    StudentOut,
    StudentListResponse,
    ParentCreate,
    ParentUpdate,
    ParentOut,
    ParentListResponse,
    ParentLinkedStudentOut,
    TeacherCreate,
    TeacherUpdate,
    TeacherOut,
    TeacherListResponse,
    TeacherClassOut,
    SubjectCreate,
    SubjectUpdate,
    SubjectOut,
    SubjectListResponse,
    TeacherAttendanceUpsertIn,
    TeacherAttendanceOut,
    ClassFeePlanCreate,
    ClassFeePlanUpdate,
    ClassFeePlanOut,
    ClassFeePlanListResponse,
    FeeComponentOut,
    AssignClassFeeToStudentsIn,
    TimetableEntryCreate,
    TimetableEntryUpdate,
    TimetableEntryOut,
    TimetableEntryListResponse,
)

router = APIRouter(
    prefix="/admin",
    tags=["School Admin"],
    dependencies=[Depends(require_role("admin"))],
)


from app.models.user import User
from app.schemas.school import (
    AppUserCreate,
    AppUserOut,
    AppUserListResponse,
    UserLinkResultOut,
)


# =========================================================
# Helpers
# =========================================================

def _get_section_names(class_obj: SchoolClass) -> list[str]:
    sections = getattr(class_obj, "sections", []) or []
    return sorted([s.name for s in sections if s.name])


def _class_to_out(item: SchoolClass) -> ClassOut:
    teacher_name = ""
    teacher_id = None

    if getattr(item, "class_teacher_id", None):
        teacher = getattr(item, "primary_teacher", None)
        if teacher:
            teacher_name = teacher.teacher_name
            teacher_id = teacher.id

    return ClassOut(
        id=item.id,
        name=item.name,
        sections=_get_section_names(item),
        class_teacher_id=teacher_id,
        class_teacher=teacher_name,
        status=item.status,
    )


def _student_to_out(item: SchoolStudent) -> StudentOut:
    class_name = item.school_class.name if getattr(item, "school_class", None) else ""
    primary_parent_id = None
    primary_parent_name = ""

    if getattr(item, "primary_parent", None):
        primary_parent_id = item.primary_parent.id
        primary_parent_name = item.primary_parent.parent_name

    return StudentOut(
        id=item.id,
        name=item.name,
        class_id=item.class_id,
        class_name=class_name,
        section=item.section,
        roll_no=item.roll_no,
        guardian_name=item.guardian_name,
        phone=item.phone,
        status=item.status,
        attendance_percentage=item.attendance_percentage or 0,
        fee_total=item.fee_total or 0,
        fee_paid=item.fee_paid or 0,
        primary_parent_id=primary_parent_id,
        primary_parent_name=primary_parent_name,
    )


def _parent_to_out(item: SchoolParent) -> ParentOut:
    students = []
    for link in getattr(item, "student_links", []) or []:
        student = getattr(link, "student", None)
        if not student:
            continue
        students.append(
            ParentLinkedStudentOut(
                id=student.id,
                name=student.name,
                class_id=student.class_id,
                class_name=student.school_class.name if getattr(student, "school_class", None) else "",
                section=student.section,
                roll_no=student.roll_no,
                guardian_name=student.guardian_name,
                phone=student.phone,
                is_primary=bool(getattr(link, "is_primary", False)),
                relation_label=getattr(link, "relation_label", "Guardian") or "Guardian",
            )
        )

    return ParentOut(
        id=item.id,
        parent_name=item.parent_name,
        relation=item.relation,
        phone=item.phone,
        alt_phone=item.alt_phone or "",
        email=item.email or "",
        address=item.address or "",
        status=item.status,
        student_count=len(students),
        students=students,
    )


def _teacher_to_out(item: SchoolTeacher) -> TeacherOut:
    classes = []
    for link in getattr(item, "class_links", []) or []:
        class_obj = getattr(link, "school_class", None)
        if not class_obj:
            continue
        classes.append(
            TeacherClassOut(
                id=class_obj.id,
                name=class_obj.name,
                sections=_get_section_names(class_obj),
                is_primary=bool(getattr(link, "is_primary", False)),
            )
        )

    return TeacherOut(
        id=item.id,
        teacher_name=item.teacher_name,
        employee_id=item.employee_id,
        phone=item.phone or "",
        email=item.email or "",
        subjects=item.subjects or "",
        status=item.status,
        class_count=len(classes),
        classes=classes,
    )


def _fee_structure_to_out(item: SchoolFeeStructure) -> ClassFeePlanOut:
    fee_heads = [
        ("Admission Fee", item.admission_fee),
        ("Tuition Fee", item.tuition_fee),
        ("Exam Fee", item.exam_fee),
        ("Transport Fee", item.transport_fee),
        ("Miscellaneous Fee", item.misc_fee),
    ]

    components = [
        FeeComponentOut(
            id=idx + 1,
            fee_head=head,
            amount=amount or 0,
            is_optional=False,
            remark="",
        )
        for idx, (head, amount) in enumerate(fee_heads)
    ]

    class_name = item.school_class.name if getattr(item, "school_class", None) else ""

    return ClassFeePlanOut(
        id=item.id,
        class_id=item.class_id,
        class_name=class_name,
        academic_year=item.academic_year or "",
        plan_name="Standard Fee Plan",
        description="",
        status=item.status,
        components=components,
    )


def _timetable_to_out(item: SchoolTimetableEntry) -> TimetableEntryOut:
    return TimetableEntryOut(
        id=item.id,
        class_id=item.class_id,
        class_name=item.school_class.name if getattr(item, "school_class", None) else "",
        teacher_id=item.teacher_id,
        teacher_name=item.teacher.teacher_name if getattr(item, "teacher", None) else "",
        timetable_type=item.timetable_type,
        day_name=item.day_name,
        period_no=item.period_no,
        period_label=item.period_label or "",
        subject=item.subject or "",
        start_time=item.start_time or "",
        end_time=item.end_time or "",
        room=item.room or "",
        remark=item.remark or "",
        status=item.status,
    )


def _sync_primary_parent_to_student(db: Session, student_id: int):
    student = db.query(SchoolStudent).filter(SchoolStudent.id == student_id).first()
    if not student:
        return

    link = (
        db.query(SchoolParentStudent)
        .options(joinedload(SchoolParentStudent.parent))
        .filter(
            SchoolParentStudent.student_id == student_id,
            SchoolParentStudent.is_primary == True,
        )
        .first()
    )

    if link and link.parent:
        student.guardian_name = link.parent.parent_name
        student.primary_parent_id = link.parent.id
        if link.parent.phone:
            student.phone = link.parent.phone
    else:
        student.primary_parent_id = None


def _refresh_class_primary_teacher(db: Session, class_id: int):
    class_obj = db.query(SchoolClass).filter(SchoolClass.id == class_id).first()
    if not class_obj:
        return

    link = (
        db.query(SchoolTeacherClass)
        .filter(
            SchoolTeacherClass.class_id == class_id,
            SchoolTeacherClass.is_primary == True,
        )
        .first()
    )

    class_obj.class_teacher_id = link.teacher_id if link else None


def _apply_primary_teacher_to_class(db: Session, class_obj: SchoolClass, teacher_id: int | None):
    db.query(SchoolTeacherClass).filter(
        SchoolTeacherClass.class_id == class_obj.id
    ).update({"is_primary": False})

    if not teacher_id:
        class_obj.class_teacher_id = None
        return

    teacher = db.query(SchoolTeacher).filter(SchoolTeacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Selected class teacher not found")

    link = (
        db.query(SchoolTeacherClass)
        .filter(
            SchoolTeacherClass.teacher_id == teacher_id,
            SchoolTeacherClass.class_id == class_obj.id,
        )
        .first()
    )
    if not link:
        link = SchoolTeacherClass(teacher_id=teacher_id, class_id=class_obj.id, is_primary=True)
        db.add(link)
        db.flush()
    else:
        link.is_primary = True

    class_obj.class_teacher_id = teacher_id


def _parse_teacher_attendance_date(value: str) -> date:
    raw = (value or "").strip()
    if not raw:
        raise HTTPException(status_code=400, detail="attendance_date is required")
    try:
        return date.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="attendance_date must be in YYYY-MM-DD format") from exc


def _normalize_teacher_attendance_status(value: str) -> str:
    normalized = (value or "Present").strip().title()
    allowed = {"Present", "Absent", "Leave", "Half Day"}
    if normalized not in allowed:
        raise HTTPException(status_code=400, detail="Teacher attendance status must be Present, Absent, Leave, or Half Day")
    return normalized


def _normalize_username(value: str) -> str:
    return (value or "").strip().lower()


ROLE_DEFAULT_PASSWORDS = {
    "student": "Student@123",
    "parent": "Parent@123",
    "teacher": "Teacher@123",
}


def _default_password_for_role(role: str) -> str:
    key = (role or "").strip().lower()
    if key not in ROLE_DEFAULT_PASSWORDS:
        raise ValueError(f"Unsupported role for default password: {role}")
    return ROLE_DEFAULT_PASSWORDS[key]


def _ensure_unique_username(db: Session, username: str) -> str:
    base = _normalize_username(username)
    candidate = base
    counter = 1
    while db.query(User).filter(func.lower(User.username) == candidate.lower()).first():
        counter += 1
        candidate = f"{base}{counter}"
    return candidate


def _student_login_username(student: SchoolStudent) -> str:
    return _normalize_username(student.roll_no)


def _teacher_login_username(teacher: SchoolTeacher) -> str:
    return _normalize_username(teacher.employee_id)


def _parent_login_username(parent: SchoolParent) -> str:
    if parent.phone and parent.phone.strip():
        return _normalize_username(parent.phone)
    if parent.email and parent.email.strip():
        return _normalize_username(parent.email)
    return _normalize_username(f"parent{parent.id}")


def _create_linked_user(
    db: Session,
    *,
    role: str,
    username: str,
    display_name: str,
    temp_password: str,
    school_student_id: int | None = None,
    school_parent_id: int | None = None,
    school_teacher_id: int | None = None,
) -> User:
    item = User(
        username=_ensure_unique_username(db, username),
        display_name=(display_name or "").strip(),
        role=role,
        password_hash=hash_password(temp_password),
        is_active=True,
        must_change_password=True,
        school_student_id=school_student_id,
        school_parent_id=school_parent_id,
        school_teacher_id=school_teacher_id,
    )
    db.add(item)
    db.flush()
    return item


def _sync_student_user(db: Session, student: SchoolStudent) -> User | None:
    user = db.query(User).filter(User.school_student_id == student.id).first()
    if user:
        user.display_name = student.name.strip()
        user.username = _ensure_unique_username(
            db,
            _student_login_username(student) if _normalize_username(user.username) != _normalize_username(_student_login_username(student)) else user.username,
        ) if _normalize_username(user.username) != _normalize_username(_student_login_username(student)) else user.username
        return user
    temp_password = _default_password_for_role("student")
    return _create_linked_user(
        db,
        role="student",
        username=_student_login_username(student),
        display_name=student.name,
        temp_password=temp_password,
        school_student_id=student.id,
    )


def _sync_teacher_user(db: Session, teacher: SchoolTeacher) -> User | None:
    user = db.query(User).filter(User.school_teacher_id == teacher.id).first()
    if user:
        user.display_name = teacher.teacher_name.strip()
        desired_username = _teacher_login_username(teacher)
        if _normalize_username(user.username) != desired_username:
            user.username = _ensure_unique_username(db, desired_username)
        return user
    temp_password = _default_password_for_role("teacher")
    return _create_linked_user(
        db,
        role="teacher",
        username=_teacher_login_username(teacher),
        display_name=teacher.teacher_name,
        temp_password=temp_password,
        school_teacher_id=teacher.id,
    )


def _sync_parent_user(db: Session, parent: SchoolParent) -> User | None:
    user = db.query(User).filter(User.school_parent_id == parent.id).first()
    if user:
        user.display_name = parent.parent_name.strip()
        desired_username = _parent_login_username(parent)
        if _normalize_username(user.username) != desired_username:
            user.username = _ensure_unique_username(db, desired_username)
        return user
    temp_password = _default_password_for_role("parent")
    return _create_linked_user(
        db,
        role="parent",
        username=_parent_login_username(parent),
        display_name=parent.parent_name,
        temp_password=temp_password,
        school_parent_id=parent.id,
    )


def _reset_user_password(user: User, new_password: str):
    user.password_hash = hash_password(new_password)
    user.must_change_password = True
    user.reset_otp_code = None
    user.reset_otp_expiry = None





def _user_to_out(item: User) -> AppUserOut:
    return AppUserOut(
        id=item.id,
        username=item.username,
        display_name=item.display_name,
        role=item.role,
        school_student_id=getattr(item, "school_student_id", None),
        school_parent_id=getattr(item, "school_parent_id", None),
        school_teacher_id=getattr(item, "school_teacher_id", None),
    )


# =========================================================
# Dropdowns
# =========================================================

@router.get("/dropdown/classes")
def dropdown_classes(db: Session = Depends(get_db)):
    items = (
        db.query(SchoolClass)
        .order_by(SchoolClass.name.asc())
        .all()
    )
    return [{"label": x.name, "value": x.id} for x in items]


@router.get("/dropdown/teachers")
def dropdown_teachers(db: Session = Depends(get_db)):
    items = (
        db.query(SchoolTeacher)
        .order_by(SchoolTeacher.teacher_name.asc())
        .all()
    )
    return [{"label": x.teacher_name, "value": x.id} for x in items]


# =========================================================
# Settings / Subjects
# =========================================================

@router.get("/settings/subjects", response_model=list[SubjectOut])
@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(db: Session = Depends(get_db)):
    items = db.query(SchoolSubject).order_by(SchoolSubject.name.asc()).all()
    return items


@router.post("/settings/subjects", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
@router.post("/subjects", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
def create_subject(payload: SubjectCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(SchoolSubject)
        .filter(func.lower(SchoolSubject.name) == payload.name.strip().lower())
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Subject already exists")

    item = SchoolSubject(name=payload.name.strip(), status=payload.status)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/settings/subjects/{subject_id}", response_model=SubjectOut)
@router.put("/subjects/{subject_id}", response_model=SubjectOut)
def update_subject(subject_id: int, payload: SubjectUpdate, db: Session = Depends(get_db)):
    item = db.query(SchoolSubject).filter(SchoolSubject.id == subject_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Subject not found")

    duplicate = (
        db.query(SchoolSubject)
        .filter(
            func.lower(SchoolSubject.name) == payload.name.strip().lower(),
            SchoolSubject.id != subject_id,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Another subject with same name already exists")

    item.name = payload.name.strip()
    item.status = payload.status
    db.commit()
    db.refresh(item)
    return item


@router.delete("/settings/subjects/{subject_id}")
@router.delete("/subjects/{subject_id}")
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    item = db.query(SchoolSubject).filter(SchoolSubject.id == subject_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Subject not found")

    db.delete(item)
    db.commit()
    return {"ok": True, "message": "Subject deleted successfully"}


# =========================================================
# Classes
# =========================================================

@router.get("/classes", response_model=list[ClassOut])
def list_classes(db: Session = Depends(get_db)):
    items = (
        db.query(SchoolClass)
        .options(
            joinedload(SchoolClass.primary_teacher),
            joinedload(SchoolClass.sections),
            joinedload(SchoolClass.students),
        )
        .order_by(SchoolClass.name.asc())
        .all()
    )
    return [_class_to_out(x) for x in items]


@router.post("/classes", response_model=ClassOut, status_code=status.HTTP_201_CREATED)
def create_class(payload: ClassCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(SchoolClass)
        .filter(func.lower(SchoolClass.name) == payload.name.strip().lower())
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Class already exists")

    if payload.class_teacher_id:
        teacher = db.query(SchoolTeacher).filter(SchoolTeacher.id == payload.class_teacher_id).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Selected class teacher not found")

    item = SchoolClass(
        name=payload.name.strip(),
        status=payload.status,
    )
    db.add(item)
    db.flush()

    for sec_name in payload.sections:
        sec_name = sec_name.strip()
        if sec_name:
            db.add(SchoolSection(class_id=item.id, name=sec_name))

    _apply_primary_teacher_to_class(db, item, payload.class_teacher_id)

    db.commit()

    item = (
        db.query(SchoolClass)
        .options(
            joinedload(SchoolClass.primary_teacher),
            joinedload(SchoolClass.sections),
            joinedload(SchoolClass.students),
        )
        .filter(SchoolClass.id == item.id)
        .first()
    )
    return _class_to_out(item)


@router.put("/classes/{class_id}", response_model=ClassOut)
def update_class(class_id: int, payload: ClassUpdate, db: Session = Depends(get_db)):
    item = db.query(SchoolClass).filter(SchoolClass.id == class_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Class not found")

    duplicate = (
        db.query(SchoolClass)
        .filter(
            func.lower(SchoolClass.name) == payload.name.strip().lower(),
            SchoolClass.id != class_id,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Another class with same name already exists")

    if payload.class_teacher_id:
        teacher = db.query(SchoolTeacher).filter(SchoolTeacher.id == payload.class_teacher_id).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Selected class teacher not found")

    item.name = payload.name.strip()
    item.status = payload.status

    db.query(SchoolSection).filter(SchoolSection.class_id == class_id).delete()
    for sec_name in payload.sections:
        sec_name = sec_name.strip()
        if sec_name:
            db.add(SchoolSection(class_id=class_id, name=sec_name))

    _apply_primary_teacher_to_class(db, item, payload.class_teacher_id)

    db.commit()

    item = (
        db.query(SchoolClass)
        .options(
            joinedload(SchoolClass.primary_teacher),
            joinedload(SchoolClass.sections),
            joinedload(SchoolClass.students),
        )
        .filter(SchoolClass.id == class_id)
        .first()
    )
    return _class_to_out(item)


@router.delete("/classes/{class_id}")
def delete_class(class_id: int, db: Session = Depends(get_db)):
    item = db.query(SchoolClass).filter(SchoolClass.id == class_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Class not found")

    student_count = db.query(SchoolStudent).filter(SchoolStudent.class_id == class_id).count()
    if student_count > 0:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete class because students are mapped to it",
        )

    db.delete(item)
    db.commit()
    return {"ok": True, "message": "Class deleted successfully"}


# =========================================================
# Students
# =========================================================

@router.get("/students", response_model=StudentListResponse)
def list_students(
    search: Optional[str] = Query(default=None),
    class_id: Optional[int] = Query(default=None),
    section: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = (
        db.query(SchoolStudent)
        .options(
            joinedload(SchoolStudent.school_class),
            joinedload(SchoolStudent.primary_parent),
            joinedload(SchoolStudent.parent_links).joinedload(SchoolParentStudent.parent),
        )
    )

    if class_id:
        query = query.filter(SchoolStudent.class_id == class_id)

    if section:
        query = query.filter(func.lower(SchoolStudent.section) == section.strip().lower())

    if search and search.strip():
        s = f"%{search.strip()}%"
        query = query.join(SchoolClass, SchoolStudent.class_id == SchoolClass.id).filter(
            or_(
                SchoolStudent.name.ilike(s),
                SchoolStudent.roll_no.ilike(s),
                SchoolStudent.guardian_name.ilike(s),
                SchoolStudent.phone.ilike(s),
                SchoolStudent.section.ilike(s),
                SchoolStudent.status.ilike(s),
                SchoolClass.name.ilike(s),
            )
        )

    items = query.order_by(SchoolStudent.id.desc()).all()
    return StudentListResponse(
        items=[_student_to_out(x) for x in items],
        total=len(items),
    )


@router.post("/students", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    class_obj = db.query(SchoolClass).filter(SchoolClass.id == payload.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")

    existing_roll = (
        db.query(SchoolStudent)
        .filter(
            SchoolStudent.class_id == payload.class_id,
            func.lower(SchoolStudent.section) == payload.section.strip().lower(),
            func.lower(SchoolStudent.roll_no) == payload.roll_no.strip().lower(),
        )
        .first()
    )
    if existing_roll:
        raise HTTPException(
            status_code=400,
            detail="Roll number already exists in this class and section",
        )

    item = SchoolStudent(
        name=payload.name.strip(),
        class_id=payload.class_id,
        section=payload.section.strip(),
        roll_no=payload.roll_no.strip(),
        guardian_name=payload.guardian_name.strip(),
        phone=payload.phone.strip(),
        status=payload.status,
        attendance_percentage=payload.attendance_percentage,
        fee_total=payload.fee_total,
        fee_paid=payload.fee_paid,
    )
    db.add(item)
    db.flush()
    _sync_student_user(db, item)
    db.commit()
    db.refresh(item)

    item = (
        db.query(SchoolStudent)
        .options(
            joinedload(SchoolStudent.school_class),
            joinedload(SchoolStudent.primary_parent),
            joinedload(SchoolStudent.parent_links).joinedload(SchoolParentStudent.parent),
        )
        .filter(SchoolStudent.id == item.id)
        .first()
    )
    return _student_to_out(item)


@router.put("/students/{student_id}", response_model=StudentOut)
def update_student(student_id: int, payload: StudentUpdate, db: Session = Depends(get_db)):
    item = db.query(SchoolStudent).filter(SchoolStudent.id == student_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Student not found")

    class_obj = db.query(SchoolClass).filter(SchoolClass.id == payload.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")

    existing_roll = (
        db.query(SchoolStudent)
        .filter(
            SchoolStudent.class_id == payload.class_id,
            func.lower(SchoolStudent.section) == payload.section.strip().lower(),
            func.lower(SchoolStudent.roll_no) == payload.roll_no.strip().lower(),
            SchoolStudent.id != student_id,
        )
        .first()
    )
    if existing_roll:
        raise HTTPException(
            status_code=400,
            detail="Roll number already exists in this class and section",
        )

    item.name = payload.name.strip()
    item.class_id = payload.class_id
    item.section = payload.section.strip()
    item.roll_no = payload.roll_no.strip()
    item.guardian_name = payload.guardian_name.strip()
    item.phone = payload.phone.strip()
    item.status = payload.status
    item.attendance_percentage = payload.attendance_percentage
    item.fee_total = payload.fee_total
    item.fee_paid = payload.fee_paid

    _sync_student_user(db, item)
    db.commit()

    item = (
        db.query(SchoolStudent)
        .options(
            joinedload(SchoolStudent.school_class),
            joinedload(SchoolStudent.primary_parent),
            joinedload(SchoolStudent.parent_links).joinedload(SchoolParentStudent.parent),
        )
        .filter(SchoolStudent.id == student_id)
        .first()
    )
    return _student_to_out(item)


@router.delete("/students/{student_id}")
def delete_student(student_id: int, db: Session = Depends(get_db)):
    item = db.query(SchoolStudent).filter(SchoolStudent.id == student_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Student not found")

    db.query(SchoolParentStudent).filter(SchoolParentStudent.student_id == student_id).delete()
    db.query(User).filter(User.school_student_id == student_id).delete()
    db.delete(item)
    db.commit()
    return {"ok": True, "message": "Student deleted successfully"}


# =========================================================
# Parents
# =========================================================

@router.get("/parents", response_model=ParentListResponse)
def list_parents(
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = (
        db.query(SchoolParent)
        .options(
            joinedload(SchoolParent.student_links)
            .joinedload(SchoolParentStudent.student)
            .joinedload(SchoolStudent.school_class)
        )
        .order_by(SchoolParent.id.desc())
    )

    if search and search.strip():
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                SchoolParent.parent_name.ilike(s),
                SchoolParent.phone.ilike(s),
                SchoolParent.alt_phone.ilike(s),
                SchoolParent.email.ilike(s),
                SchoolParent.relation.ilike(s),
                SchoolParent.status.ilike(s),
            )
        )

    items = query.all()
    return ParentListResponse(
        items=[_parent_to_out(x) for x in items],
        total=len(items),
    )


@router.post("/parents", response_model=ParentOut, status_code=status.HTTP_201_CREATED)
def create_parent(payload: ParentCreate, db: Session = Depends(get_db)):
    item = SchoolParent(
        parent_name=payload.parent_name.strip(),
        relation=payload.relation.strip(),
        phone=payload.phone.strip(),
        alt_phone=(payload.alt_phone or "").strip(),
        email=(payload.email or "").strip(),
        address=(payload.address or "").strip(),
        status=payload.status,
    )
    db.add(item)
    db.flush()

    seen_students = set()
    primary_assigned = False

    for link_in in payload.student_links:
        if link_in.student_id in seen_students:
            continue
        seen_students.add(link_in.student_id)

        student = db.query(SchoolStudent).filter(SchoolStudent.id == link_in.student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail=f"Student not found: {link_in.student_id}")

        is_primary = bool(link_in.is_primary) and not primary_assigned
        if is_primary:
            primary_assigned = True

        db.add(SchoolParentStudent(
            parent_id=item.id,
            student_id=link_in.student_id,
            is_primary=is_primary,
            relation_label=link_in.relation_label or payload.relation or "Guardian",
        ))

    db.flush()

    if payload.sync_to_students:
        for link_in in payload.student_links:
            if payload.set_as_primary_parent:
                db.query(SchoolParentStudent).filter(
                    SchoolParentStudent.student_id == link_in.student_id
                ).update({"is_primary": False})
                db.query(SchoolParentStudent).filter(
                    SchoolParentStudent.parent_id == item.id,
                    SchoolParentStudent.student_id == link_in.student_id,
                ).update({"is_primary": True})

            _sync_primary_parent_to_student(db, link_in.student_id)

    _sync_parent_user(db, item)
    db.commit()

    item = (
        db.query(SchoolParent)
        .options(
            joinedload(SchoolParent.student_links)
            .joinedload(SchoolParentStudent.student)
            .joinedload(SchoolStudent.school_class)
        )
        .filter(SchoolParent.id == item.id)
        .first()
    )
    return _parent_to_out(item)


@router.put("/parents/{parent_id}", response_model=ParentOut)
def update_parent(parent_id: int, payload: ParentUpdate, db: Session = Depends(get_db)):
    item = db.query(SchoolParent).filter(SchoolParent.id == parent_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Parent not found")

    item.parent_name = payload.parent_name.strip()
    item.relation = payload.relation.strip()
    item.phone = payload.phone.strip()
    item.alt_phone = (payload.alt_phone or "").strip()
    item.email = (payload.email or "").strip()
    item.address = (payload.address or "").strip()
    item.status = payload.status

    db.query(SchoolParentStudent).filter(SchoolParentStudent.parent_id == parent_id).delete()

    seen_students = set()
    primary_assigned = False

    for link_in in payload.student_links:
        if link_in.student_id in seen_students:
            continue
        seen_students.add(link_in.student_id)

        student = db.query(SchoolStudent).filter(SchoolStudent.id == link_in.student_id).first()
        if not student:
            raise HTTPException(status_code=404, detail=f"Student not found: {link_in.student_id}")

        is_primary = bool(link_in.is_primary) and not primary_assigned
        if is_primary:
            primary_assigned = True

        db.add(SchoolParentStudent(
            parent_id=parent_id,
            student_id=link_in.student_id,
            is_primary=is_primary,
            relation_label=link_in.relation_label or payload.relation or "Guardian",
        ))

    db.flush()

    if payload.sync_to_students:
        for link_in in payload.student_links:
            if payload.set_as_primary_parent:
                db.query(SchoolParentStudent).filter(
                    SchoolParentStudent.student_id == link_in.student_id
                ).update({"is_primary": False})
                db.query(SchoolParentStudent).filter(
                    SchoolParentStudent.parent_id == parent_id,
                    SchoolParentStudent.student_id == link_in.student_id,
                ).update({"is_primary": True})

            _sync_primary_parent_to_student(db, link_in.student_id)

    _sync_parent_user(db, item)
    db.commit()

    item = (
        db.query(SchoolParent)
        .options(
            joinedload(SchoolParent.student_links)
            .joinedload(SchoolParentStudent.student)
            .joinedload(SchoolStudent.school_class)
        )
        .filter(SchoolParent.id == parent_id)
        .first()
    )
    return _parent_to_out(item)


@router.delete("/parents/{parent_id}")
def delete_parent(parent_id: int, db: Session = Depends(get_db)):
    item = db.query(SchoolParent).filter(SchoolParent.id == parent_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Parent not found")

    affected_student_ids = [
        x.student_id
        for x in db.query(SchoolParentStudent).filter(SchoolParentStudent.parent_id == parent_id).all()
    ]

    db.query(SchoolParentStudent).filter(SchoolParentStudent.parent_id == parent_id).delete()
    db.query(User).filter(User.school_parent_id == parent_id).delete()
    db.delete(item)
    db.commit()

    for student_id in affected_student_ids:
        _sync_primary_parent_to_student(db, student_id)
    db.commit()

    return {"ok": True, "message": "Parent deleted successfully"}


# =========================================================
# Teachers
# =========================================================

@router.get("/teachers", response_model=TeacherListResponse)
def list_teachers(
    search: Optional[str] = Query(default=None),
    class_id: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = (
        db.query(SchoolTeacher)
        .options(
            joinedload(SchoolTeacher.class_links)
            .joinedload(SchoolTeacherClass.school_class)
            .joinedload(SchoolClass.sections),
            joinedload(SchoolTeacher.attendance_entries),
        )
        .order_by(SchoolTeacher.id.desc())
    )

    if search and search.strip():
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                SchoolTeacher.teacher_name.ilike(s),
                SchoolTeacher.employee_id.ilike(s),
                SchoolTeacher.phone.ilike(s),
                SchoolTeacher.email.ilike(s),
                SchoolTeacher.subjects.ilike(s),
                SchoolTeacher.status.ilike(s),
            )
        )

    if class_id:
        query = query.join(
            SchoolTeacherClass,
            SchoolTeacherClass.teacher_id == SchoolTeacher.id,
        ).filter(SchoolTeacherClass.class_id == class_id)

    if status and status.strip():
        query = query.filter(SchoolTeacher.status == status.strip().title())

    items = query.all()
    return TeacherListResponse(
        items=[_teacher_to_out(x) for x in items],
        total=len(items),
    )


@router.post("/teachers", response_model=TeacherOut, status_code=status.HTTP_201_CREATED)
def create_teacher(payload: TeacherCreate, db: Session = Depends(get_db)):
    duplicate = (
        db.query(SchoolTeacher)
        .filter(func.lower(SchoolTeacher.employee_id) == payload.employee_id.strip().lower())
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Employee ID already exists")

    item = SchoolTeacher(
        teacher_name=payload.teacher_name.strip(),
        employee_id=payload.employee_id.strip(),
        phone=(payload.phone or "").strip(),
        email=(payload.email or "").strip(),
        subjects=(payload.subjects or "").strip(),
        status=payload.status,
    )
    db.add(item)
    db.flush()

    seen_classes = set()
    primary_assigned = False

    for link_in in payload.class_links:
        if link_in.class_id in seen_classes:
            continue
        seen_classes.add(link_in.class_id)

        class_obj = db.query(SchoolClass).filter(SchoolClass.id == link_in.class_id).first()
        if not class_obj:
            raise HTTPException(status_code=404, detail=f"Class not found: {link_in.class_id}")

        is_primary = bool(link_in.is_primary) and not primary_assigned
        if is_primary:
            primary_assigned = True

        db.add(SchoolTeacherClass(
            teacher_id=item.id,
            class_id=link_in.class_id,
            is_primary=is_primary,
        ))

    db.flush()

    if payload.set_as_primary_teacher:
        for link_in in payload.class_links:
            db.query(SchoolTeacherClass).filter(
                SchoolTeacherClass.class_id == link_in.class_id
            ).update({"is_primary": False})
            db.query(SchoolTeacherClass).filter(
                SchoolTeacherClass.teacher_id == item.id,
                SchoolTeacherClass.class_id == link_in.class_id,
            ).update({"is_primary": True})
            _refresh_class_primary_teacher(db, link_in.class_id)

    _sync_teacher_user(db, item)
    db.commit()

    item = (
        db.query(SchoolTeacher)
        .options(
            joinedload(SchoolTeacher.class_links)
            .joinedload(SchoolTeacherClass.school_class)
            .joinedload(SchoolClass.sections),
            joinedload(SchoolTeacher.attendance_entries)
        )
        .filter(SchoolTeacher.id == item.id)
        .first()
    )
    return _teacher_to_out(item)


@router.put("/teachers/{teacher_id}", response_model=TeacherOut)
def update_teacher(teacher_id: int, payload: TeacherUpdate, db: Session = Depends(get_db)):
    item = db.query(SchoolTeacher).filter(SchoolTeacher.id == teacher_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Teacher not found")

    duplicate = (
        db.query(SchoolTeacher)
        .filter(
            func.lower(SchoolTeacher.employee_id) == payload.employee_id.strip().lower(),
            SchoolTeacher.id != teacher_id,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Employee ID already exists")

    old_class_ids = [
        x.class_id for x in db.query(SchoolTeacherClass).filter(SchoolTeacherClass.teacher_id == teacher_id).all()
    ]

    item.teacher_name = payload.teacher_name.strip()
    item.employee_id = payload.employee_id.strip()
    item.phone = (payload.phone or "").strip()
    item.email = (payload.email or "").strip()
    item.subjects = (payload.subjects or "").strip()
    item.status = payload.status

    db.query(SchoolTeacherClass).filter(SchoolTeacherClass.teacher_id == teacher_id).delete()

    seen_classes = set()
    primary_assigned = False

    for link_in in payload.class_links:
        if link_in.class_id in seen_classes:
            continue
        seen_classes.add(link_in.class_id)

        class_obj = db.query(SchoolClass).filter(SchoolClass.id == link_in.class_id).first()
        if not class_obj:
            raise HTTPException(status_code=404, detail=f"Class not found: {link_in.class_id}")

        is_primary = bool(link_in.is_primary) and not primary_assigned
        if is_primary:
            primary_assigned = True

        db.add(SchoolTeacherClass(
            teacher_id=teacher_id,
            class_id=link_in.class_id,
            is_primary=is_primary,
        ))

    db.flush()

    all_class_ids = sorted(set(old_class_ids + [x.class_id for x in payload.class_links]))

    if payload.set_as_primary_teacher:
        for class_id in [x.class_id for x in payload.class_links]:
            db.query(SchoolTeacherClass).filter(
                SchoolTeacherClass.class_id == class_id
            ).update({"is_primary": False})
            db.query(SchoolTeacherClass).filter(
                SchoolTeacherClass.teacher_id == teacher_id,
                SchoolTeacherClass.class_id == class_id,
            ).update({"is_primary": True})

    for class_id in all_class_ids:
        _refresh_class_primary_teacher(db, class_id)

    db.commit()

    item = (
        db.query(SchoolTeacher)
        .options(
            joinedload(SchoolTeacher.class_links)
            .joinedload(SchoolTeacherClass.school_class)
            .joinedload(SchoolClass.sections),
            joinedload(SchoolTeacher.attendance_entries)
        )
        .filter(SchoolTeacher.id == teacher_id)
        .first()
    )
    return _teacher_to_out(item)


@router.delete("/teachers/{teacher_id}")
def delete_teacher(teacher_id: int, db: Session = Depends(get_db)):
    item = db.query(SchoolTeacher).filter(SchoolTeacher.id == teacher_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Teacher not found")

    affected_class_ids = [
        x.class_id for x in db.query(SchoolTeacherClass).filter(SchoolTeacherClass.teacher_id == teacher_id).all()
    ]

    db.query(SchoolTeacherClass).filter(SchoolTeacherClass.teacher_id == teacher_id).delete()
    db.query(User).filter(User.school_teacher_id == teacher_id).delete()
    db.delete(item)
    db.commit()

    for class_id in affected_class_ids:
        _refresh_class_primary_teacher(db, class_id)
    db.commit()

    return {"ok": True, "message": "Teacher deleted successfully"}


# =========================================================
# Teacher Attendance
# =========================================================

@router.post("/teachers/{teacher_id}/attendance", response_model=TeacherAttendanceOut)
def upsert_teacher_attendance(teacher_id: int, payload: TeacherAttendanceUpsertIn, db: Session = Depends(get_db)):
    teacher = db.query(SchoolTeacher).filter(SchoolTeacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    attendance_date = _parse_teacher_attendance_date(payload.attendance_date)
    attendance_status = _normalize_teacher_attendance_status(payload.status)

    item = (
        db.query(SchoolTeacherAttendance)
        .filter(
            SchoolTeacherAttendance.teacher_id == teacher_id,
            SchoolTeacherAttendance.attendance_date == attendance_date,
        )
        .first()
    )

    if item:
        item.status = attendance_status
    else:
        item = SchoolTeacherAttendance(
            teacher_id=teacher_id,
            attendance_date=attendance_date,
            status=attendance_status,
        )
        db.add(item)

    db.commit()
    db.refresh(item)

    return TeacherAttendanceOut(
        id=item.id,
        teacher_id=item.teacher_id,
        attendance_date=item.attendance_date.isoformat(),
        status=item.status,
    )


# =========================================================
# Fee Plans
# =========================================================

@router.get("/fee-plans", response_model=ClassFeePlanListResponse)
def list_fee_plans(
    class_id: Optional[int] = Query(default=None),
    academic_year: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = (
        db.query(SchoolFeeStructure)
        .options(joinedload(SchoolFeeStructure.school_class))
        .order_by(SchoolFeeStructure.id.desc())
    )

    if class_id:
        query = query.filter(SchoolFeeStructure.class_id == class_id)

    if academic_year and academic_year.strip():
        query = query.filter(SchoolFeeStructure.academic_year == academic_year.strip())

    items = query.all()
    return ClassFeePlanListResponse(
        items=[_fee_structure_to_out(x) for x in items],
        total=len(items),
    )


@router.post("/fee-plans", response_model=ClassFeePlanOut, status_code=status.HTTP_201_CREATED)
def create_fee_plan(payload: ClassFeePlanCreate, db: Session = Depends(get_db)):
    class_obj = db.query(SchoolClass).filter(SchoolClass.id == payload.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")

    existing = (
        db.query(SchoolFeeStructure)
        .filter(SchoolFeeStructure.class_id == payload.class_id)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="Fee plan already exists for this class. Use PUT to update it.",
        )

    fee_map = {c.fee_head.strip().lower(): c.amount for c in payload.components}

    item = SchoolFeeStructure(
        class_id=payload.class_id,
        academic_year=payload.academic_year.strip(),
        admission_fee=fee_map.get("admission fee", 0),
        tuition_fee=fee_map.get("tuition fee", 0),
        exam_fee=fee_map.get("exam fee", 0),
        transport_fee=fee_map.get("transport fee", 0),
        misc_fee=fee_map.get("miscellaneous fee", fee_map.get("misc fee", 0)),
        status=payload.status,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    item = (
        db.query(SchoolFeeStructure)
        .options(joinedload(SchoolFeeStructure.school_class))
        .filter(SchoolFeeStructure.id == item.id)
        .first()
    )
    return _fee_structure_to_out(item)


@router.put("/fee-plans/{fee_plan_id}", response_model=ClassFeePlanOut)
def update_fee_plan(fee_plan_id: int, payload: ClassFeePlanUpdate, db: Session = Depends(get_db)):
    item = db.query(SchoolFeeStructure).filter(SchoolFeeStructure.id == fee_plan_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Fee plan not found")

    class_obj = db.query(SchoolClass).filter(SchoolClass.id == payload.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")

    fee_map = {c.fee_head.strip().lower(): c.amount for c in payload.components}

    item.class_id = payload.class_id
    item.academic_year = payload.academic_year.strip()
    item.admission_fee = fee_map.get("admission fee", item.admission_fee)
    item.tuition_fee = fee_map.get("tuition fee", item.tuition_fee)
    item.exam_fee = fee_map.get("exam fee", item.exam_fee)
    item.transport_fee = fee_map.get("transport fee", item.transport_fee)
    item.misc_fee = fee_map.get("miscellaneous fee", fee_map.get("misc fee", item.misc_fee))
    item.status = payload.status

    db.commit()

    item = (
        db.query(SchoolFeeStructure)
        .options(joinedload(SchoolFeeStructure.school_class))
        .filter(SchoolFeeStructure.id == fee_plan_id)
        .first()
    )
    return _fee_structure_to_out(item)


@router.delete("/fee-plans/{fee_plan_id}")
def delete_fee_plan(fee_plan_id: int, db: Session = Depends(get_db)):
    item = db.query(SchoolFeeStructure).filter(SchoolFeeStructure.id == fee_plan_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Fee plan not found")

    db.delete(item)
    db.commit()
    return {"ok": True, "message": "Fee plan deleted successfully"}


@router.post("/fee-plans/assign")
def assign_fee_plan_to_students(payload: AssignClassFeeToStudentsIn, db: Session = Depends(get_db)):
    class_obj = db.query(SchoolClass).filter(SchoolClass.id == payload.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")

    fee_plan = (
        db.query(SchoolFeeStructure)
        .filter(
            SchoolFeeStructure.id == payload.fee_plan_id,
            SchoolFeeStructure.class_id == payload.class_id,
        )
        .first()
    )
    if not fee_plan:
        raise HTTPException(status_code=404, detail="Fee plan not found for this class")

    total_amount = (
        (fee_plan.admission_fee or 0)
        + (fee_plan.tuition_fee or 0)
        + (fee_plan.exam_fee or 0)
        + (fee_plan.transport_fee or 0)
        + (fee_plan.misc_fee or 0)
    )

    updated = 0
    if payload.apply_to_existing_students:
        students = db.query(SchoolStudent).filter(SchoolStudent.class_id == payload.class_id).all()
        for student in students:
            if payload.overwrite_student_fee_total:
                student.fee_total = total_amount
                if payload.reset_student_fee_paid_if_exceeds_total and (student.fee_paid or 0) > total_amount:
                    student.fee_paid = 0
                updated += 1

    db.commit()

    return {
        "ok": True,
        "message": "Fee plan assigned successfully",
        "class_id": payload.class_id,
        "fee_plan_id": payload.fee_plan_id,
        "assigned_total_fee": total_amount,
        "students_updated": updated,
    }


# =========================================================
# Timetable
# =========================================================

@router.get("/timetables", response_model=TimetableEntryListResponse)
def list_timetables(
    class_id: Optional[int] = Query(default=None),
    timetable_type: Optional[str] = Query(default=None),
    day_name: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = (
        db.query(SchoolTimetableEntry)
        .options(
            joinedload(SchoolTimetableEntry.school_class),
            joinedload(SchoolTimetableEntry.teacher),
        )
    )

    if class_id:
        query = query.filter(SchoolTimetableEntry.class_id == class_id)

    if timetable_type and timetable_type.strip():
        query = query.filter(
            func.lower(SchoolTimetableEntry.timetable_type) == timetable_type.strip().lower()
        )

    if day_name and day_name.strip():
        query = query.filter(
            func.lower(SchoolTimetableEntry.day_name) == day_name.strip().lower()
        )

    if search and search.strip():
        s = f"%{search.strip()}%"
        query = query.join(
            SchoolClass, SchoolTimetableEntry.class_id == SchoolClass.id
        ).outerjoin(
            SchoolTeacher, SchoolTimetableEntry.teacher_id == SchoolTeacher.id
        ).filter(
            or_(
                SchoolTimetableEntry.timetable_type.ilike(s),
                SchoolTimetableEntry.day_name.ilike(s),
                SchoolTimetableEntry.period_label.ilike(s),
                SchoolTimetableEntry.subject.ilike(s),
                SchoolTimetableEntry.room.ilike(s),
                SchoolTimetableEntry.remark.ilike(s),
                SchoolTimetableEntry.status.ilike(s),
                SchoolTimetableEntry.start_time.ilike(s),
                SchoolTimetableEntry.end_time.ilike(s),
                SchoolClass.name.ilike(s),
                SchoolTeacher.teacher_name.ilike(s),
            )
        )

    items = (
        query.order_by(
            SchoolTimetableEntry.class_id.asc(),
            SchoolTimetableEntry.timetable_type.asc(),
            SchoolTimetableEntry.day_name.asc(),
            SchoolTimetableEntry.period_no.asc(),
        )
        .all()
    )

    return TimetableEntryListResponse(
        items=[_timetable_to_out(x) for x in items],
        total=len(items),
    )


@router.post("/timetables", response_model=TimetableEntryOut, status_code=status.HTTP_201_CREATED)
def create_timetable(payload: TimetableEntryCreate, db: Session = Depends(get_db)):
    class_obj = db.query(SchoolClass).filter(SchoolClass.id == payload.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")

    if payload.teacher_id:
        teacher_obj = db.query(SchoolTeacher).filter(SchoolTeacher.id == payload.teacher_id).first()
        if not teacher_obj:
            raise HTTPException(status_code=404, detail="Teacher not found")

    existing = (
        db.query(SchoolTimetableEntry)
        .filter(
            SchoolTimetableEntry.class_id == payload.class_id,
            func.lower(SchoolTimetableEntry.timetable_type) == payload.timetable_type.strip().lower(),
            func.lower(SchoolTimetableEntry.day_name) == payload.day_name.strip().lower(),
            SchoolTimetableEntry.period_no == payload.period_no,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="This period slot already exists for the selected class, timetable type, and day",
        )

    item = SchoolTimetableEntry(
        class_id=payload.class_id,
        teacher_id=payload.teacher_id,
        timetable_type=payload.timetable_type.strip().title(),
        day_name=payload.day_name.strip().title(),
        period_no=payload.period_no,
        period_label=(payload.period_label or "").strip(),
        subject=(payload.subject or "").strip(),
        start_time=(payload.start_time or "").strip(),
        end_time=(payload.end_time or "").strip(),
        room=(payload.room or "").strip(),
        remark=(payload.remark or "").strip(),
        status=payload.status,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    item = (
        db.query(SchoolTimetableEntry)
        .options(
            joinedload(SchoolTimetableEntry.school_class),
            joinedload(SchoolTimetableEntry.teacher),
        )
        .filter(SchoolTimetableEntry.id == item.id)
        .first()
    )
    return _timetable_to_out(item)


@router.put("/timetables/{entry_id}", response_model=TimetableEntryOut)
def update_timetable(entry_id: int, payload: TimetableEntryUpdate, db: Session = Depends(get_db)):
    item = db.query(SchoolTimetableEntry).filter(SchoolTimetableEntry.id == entry_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Timetable entry not found")

    class_obj = db.query(SchoolClass).filter(SchoolClass.id == payload.class_id).first()
    if not class_obj:
        raise HTTPException(status_code=404, detail="Class not found")

    if payload.teacher_id:
        teacher_obj = db.query(SchoolTeacher).filter(SchoolTeacher.id == payload.teacher_id).first()
        if not teacher_obj:
            raise HTTPException(status_code=404, detail="Teacher not found")

    existing = (
        db.query(SchoolTimetableEntry)
        .filter(
            SchoolTimetableEntry.class_id == payload.class_id,
            func.lower(SchoolTimetableEntry.timetable_type) == payload.timetable_type.strip().lower(),
            func.lower(SchoolTimetableEntry.day_name) == payload.day_name.strip().lower(),
            SchoolTimetableEntry.period_no == payload.period_no,
            SchoolTimetableEntry.id != entry_id,
        )
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=400,
            detail="This period slot already exists for the selected class, timetable type, and day",
        )

    item.class_id = payload.class_id
    item.teacher_id = payload.teacher_id
    item.timetable_type = payload.timetable_type.strip().title()
    item.day_name = payload.day_name.strip().title()
    item.period_no = payload.period_no
    item.period_label = (payload.period_label or "").strip()
    item.subject = (payload.subject or "").strip()
    item.start_time = (payload.start_time or "").strip()
    item.end_time = (payload.end_time or "").strip()
    item.room = (payload.room or "").strip()
    item.remark = (payload.remark or "").strip()
    item.status = payload.status

    db.commit()

    item = (
        db.query(SchoolTimetableEntry)
        .options(
            joinedload(SchoolTimetableEntry.school_class),
            joinedload(SchoolTimetableEntry.teacher),
        )
        .filter(SchoolTimetableEntry.id == entry_id)
        .first()
    )
    return _timetable_to_out(item)


@router.delete("/timetables/{entry_id}")
def delete_timetable(entry_id: int, db: Session = Depends(get_db)):
    item = db.query(SchoolTimetableEntry).filter(SchoolTimetableEntry.id == entry_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Timetable entry not found")

    db.delete(item)
    db.commit()
    return {"ok": True, "message": "Timetable entry deleted successfully"}


# =========================================================
# App Users / Login Linking
# =========================================================

@router.get("/users", response_model=AppUserListResponse)
def list_app_users(
    search: Optional[str] = Query(default=None),
    role: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(User)

    if role and role.strip():
        query = query.filter(func.lower(User.role) == role.strip().lower())

    if search and search.strip():
        s = f"%{search.strip()}%"
        query = query.filter(
            or_(
                User.username.ilike(s),
                User.display_name.ilike(s),
                User.role.ilike(s),
            )
        )

    items = query.order_by(User.id.desc()).all()
    return AppUserListResponse(
        items=[_user_to_out(x) for x in items],
        total=len(items),
    )


@router.post("/users", response_model=AppUserOut, status_code=status.HTTP_201_CREATED)
def create_app_user(payload: AppUserCreate, db: Session = Depends(get_db)):
    existing = (
        db.query(User)
        .filter(func.lower(User.username) == payload.username.strip().lower())
        .first()
    )
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")

    item = User(
        username=payload.username.strip().lower(),
        display_name=payload.display_name.strip(),
        role=payload.role.strip().lower(),
        password_hash=hash_password(payload.password),
        is_active=True,
        must_change_password=False,
        school_student_id=None,
        school_parent_id=None,
        school_teacher_id=None,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _user_to_out(item)


@router.post("/users/{user_id}/link-student/{student_id}", response_model=UserLinkResultOut)
def link_user_to_student(user_id: int, student_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role != "student":
        raise HTTPException(status_code=400, detail="Only users with student role can be linked to a student")

    student = db.query(SchoolStudent).filter(SchoolStudent.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    user.school_student_id = student.id
    user.school_parent_id = None
    user.school_teacher_id = None

    db.commit()
    db.refresh(user)

    return UserLinkResultOut(
        message="User linked to student successfully",
        user=_user_to_out(user),
    )


@router.post("/users/{user_id}/link-parent/{parent_id}", response_model=UserLinkResultOut)
def link_user_to_parent(user_id: int, parent_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role != "parent":
        raise HTTPException(status_code=400, detail="Only users with parent role can be linked to a parent")

    parent = db.query(SchoolParent).filter(SchoolParent.id == parent_id).first()
    if not parent:
        raise HTTPException(status_code=404, detail="Parent not found")

    user.school_student_id = None
    user.school_parent_id = parent.id
    user.school_teacher_id = None

    db.commit()
    db.refresh(user)

    return UserLinkResultOut(
        message="User linked to parent successfully",
        user=_user_to_out(user),
    )


@router.post("/users/{user_id}/link-teacher/{teacher_id}", response_model=UserLinkResultOut)
def link_user_to_teacher(user_id: int, teacher_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if user.role != "teacher":
        raise HTTPException(status_code=400, detail="Only users with teacher role can be linked to a teacher")

    teacher = db.query(SchoolTeacher).filter(SchoolTeacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    user.school_student_id = None
    user.school_parent_id = None
    user.school_teacher_id = teacher.id

    db.commit()
    db.refresh(user)

    return UserLinkResultOut(
        message="User linked to teacher successfully",
        user=_user_to_out(user),
    )


@router.get("/students/{student_id}/login")
def get_student_login(student_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.school_student_id == student_id, User.role == "student").first()
    if not user:
        raise HTTPException(status_code=404, detail="Student login account not found")
    return {
        "ok": True,
        "role": user.role,
        "username": user.username,
        "display_name": user.display_name,
        "must_change_password": bool(user.must_change_password),
        "is_active": bool(user.is_active),
        "default_password": _default_password_for_role(user.role),
    }


@router.get("/parents/{parent_id}/login")
def get_parent_login(parent_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.school_parent_id == parent_id, User.role == "parent").first()
    if not user:
        raise HTTPException(status_code=404, detail="Parent login account not found")
    return {
        "ok": True,
        "role": user.role,
        "username": user.username,
        "display_name": user.display_name,
        "must_change_password": bool(user.must_change_password),
        "is_active": bool(user.is_active),
        "default_password": _default_password_for_role(user.role),
    }


@router.get("/teachers/{teacher_id}/login")
def get_teacher_login(teacher_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.school_teacher_id == teacher_id, User.role == "teacher").first()
    if not user:
        raise HTTPException(status_code=404, detail="Teacher login account not found")
    return {
        "ok": True,
        "role": user.role,
        "username": user.username,
        "display_name": user.display_name,
        "must_change_password": bool(user.must_change_password),
        "is_active": bool(user.is_active),
        "default_password": _default_password_for_role(user.role),
    }


@router.post("/students/{student_id}/reset-password")
def reset_student_password(student_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.school_student_id == student_id, User.role == "student").first()
    if not user:
        raise HTTPException(status_code=404, detail="Student login account not found")
    temp_password = _default_password_for_role("student")
    _reset_user_password(user, temp_password)
    db.commit()
    return {"ok": True, "username": user.username, "temporary_password": temp_password, "message": "Student password reset successfully"}


@router.post("/parents/{parent_id}/reset-password")
def reset_parent_password(parent_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.school_parent_id == parent_id, User.role == "parent").first()
    if not user:
        raise HTTPException(status_code=404, detail="Parent login account not found")
    temp_password = _default_password_for_role("parent")
    _reset_user_password(user, temp_password)
    db.commit()
    return {"ok": True, "username": user.username, "temporary_password": temp_password, "message": "Parent password reset successfully"}


@router.post("/teachers/{teacher_id}/reset-password")
def reset_teacher_password(teacher_id: int, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.school_teacher_id == teacher_id, User.role == "teacher").first()
    if not user:
        raise HTTPException(status_code=404, detail="Teacher login account not found")
    temp_password = _default_password_for_role("teacher")
    _reset_user_password(user, temp_password)
    db.commit()
    return {"ok": True, "username": user.username, "temporary_password": temp_password, "message": "Teacher password reset successfully"}
