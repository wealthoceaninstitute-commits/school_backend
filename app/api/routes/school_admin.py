from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.db.session import get_db
from app.models.school import (
    SchoolClass,
    SchoolFeeStructure,
    SchoolParent,
    SchoolParentStudent,
    SchoolRoom,
    SchoolSection,
    SchoolStudent,
    SchoolSubject,
    SchoolTeacher,
    SchoolTeacherAttendance,
    SchoolTeacherClass,
    SchoolTimetableEntry,
)
from app.schemas.school import (
    ClassCreate,
    ClassOut,
    ClassUpdate,
    FeeStructureCreate,
    FeeStructureOut,
    FeeStructureUpdate,
    MessageOut,
    ParentCreate,
    ParentOut,
    ParentStudentMiniOut,
    ParentUpdate,
    RoomCreate,
    RoomOut,
    RoomUpdate,
    SectionListOut,
    SectionOut,
    StudentCreate,
    StudentOut,
    StudentParentMiniOut,
    StudentUpdate,
    SubjectCreate,
    SubjectOut,
    SubjectUpdate,
    TeacherAttendanceUpsertIn,
    TeacherClassMiniOut,
    TeacherCreate,
    TeacherListOut,
    TeacherOut,
    TeacherUpdate,
    TimetableEntryCreate,
    TimetableEntryOut,
    TimetableEntryUpdate,
    TimetableListOut,
)

router = APIRouter()


# --------------------------------------------------
# Helpers
# --------------------------------------------------

def _normalize_text(value: Optional[str]) -> str:
    return (value or "").strip()


def _normalize_list(values: list[str]) -> list[str]:
    out: list[str] = []
    seen = set()
    for raw in values or []:
        name = _normalize_text(raw)
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out


def _get_section_names(item: SchoolClass) -> list[str]:
    return [s.name for s in (item.sections or [])]


def _set_class_sections(db: Session, school_class: SchoolClass, sections: list[str]) -> None:
    names = _normalize_list(sections)
    school_class.sections.clear()
    for name in names:
        school_class.sections.append(SchoolSection(name=name))


def _section_to_out(item: SchoolSection) -> SectionOut:
    return SectionOut(
        id=item.id,
        class_id=item.class_id,
        name=item.name,
    )


def _validate_section_for_class(db: Session, class_id: int, section_id: int) -> SchoolSection:
    section = (
        db.query(SchoolSection)
        .filter(
            SchoolSection.id == section_id,
            SchoolSection.class_id == class_id,
        )
        .first()
    )
    if not section:
        raise HTTPException(status_code=404, detail="Section not found for selected class")
    return section


def _class_to_out(item: SchoolClass) -> ClassOut:
    teacher_name = ""
    teacher_id = None

    if item.primary_teacher:
        teacher_name = item.primary_teacher.teacher_name or ""
        teacher_id = item.primary_teacher.id

    active_student_count = len(
        [s for s in (item.students or []) if (s.status or "").strip().lower() == "active"]
    )

    return ClassOut(
        id=item.id,
        name=item.name,
        sections=_get_section_names(item),
        class_teacher_id=teacher_id,
        class_teacher=teacher_name,
        status=item.status,
        student_count=active_student_count,
    )


def _parent_to_out(item: SchoolParent) -> ParentOut:
    students: list[ParentStudentMiniOut] = []

    for link in item.student_links or []:
        student = link.student
        if not student:
            continue
        students.append(
            ParentStudentMiniOut(
                id=student.id,
                name=student.name,
                class_id=student.class_id,
                class_name=student.school_class.name if student.school_class else "",
                section=student.section or "",
                roll_no=student.roll_no or "",
                is_primary=bool(link.is_primary),
            )
        )

    return ParentOut(
        id=item.id,
        parent_name=item.parent_name,
        relation=item.relation,
        phone=item.phone,
        alt_phone=item.alt_phone,
        email=item.email,
        address=item.address,
        status=item.status,
        students=students,
    )


def _student_to_out(item: SchoolStudent) -> StudentOut:
    parents: list[StudentParentMiniOut] = []

    for link in item.parent_links or []:
        parent = link.parent
        if not parent:
            continue
        parents.append(
            StudentParentMiniOut(
                id=parent.id,
                parent_name=parent.parent_name,
                relation=link.relation_label or parent.relation or "Guardian",
                phone=parent.phone or "",
                is_primary=bool(link.is_primary),
            )
        )

    return StudentOut(
        id=item.id,
        name=item.name,
        class_id=item.class_id,
        class_name=item.school_class.name if item.school_class else "",
        section=item.section,
        roll_no=item.roll_no,
        guardian_name=item.guardian_name,
        phone=item.phone,
        status=item.status,
        attendance_percentage=item.attendance_percentage,
        fee_total=item.fee_total,
        fee_paid=item.fee_paid,
        pending_fee=max((item.fee_total or 0) - (item.fee_paid or 0), 0),
        gender=getattr(item, "gender", None),
        date_of_birth=getattr(item, "date_of_birth", None),
        date_of_admission=getattr(item, "date_of_admission", None),
        parents=parents,
    )


def _teacher_attendance_stats(item: SchoolTeacher) -> tuple[int, int, int]:
    entries = item.attendance_entries or []
    working_days = len(entries)
    present_days = len([x for x in entries if (x.status or "").strip().lower() == "present"])
    attendance_percentage = round((present_days / working_days) * 100) if working_days > 0 else 0
    return present_days, working_days, attendance_percentage


def _teacher_to_out(item: SchoolTeacher) -> TeacherOut:
    classes: list[TeacherClassMiniOut] = []

    for link in item.class_links or []:
        school_class = link.school_class
        if not school_class:
            continue
        classes.append(
            TeacherClassMiniOut(
                id=school_class.id,
                name=school_class.name,
                sections=_get_section_names(school_class),
                is_primary=bool(link.is_primary),
            )
        )

    present_days, working_days, attendance_percentage = _teacher_attendance_stats(item)

    return TeacherOut(
        id=item.id,
        teacher_name=item.teacher_name,
        employee_id=item.employee_id,
        phone=item.phone,
        email=item.email,
        subjects=item.subjects,
        status=item.status,
        classes=classes,
        class_count=len(classes),
        present_days=present_days,
        working_days=working_days,
        attendance_percentage=attendance_percentage,
    )


def _timetable_to_out(item: SchoolTimetableEntry) -> TimetableEntryOut:
    return TimetableEntryOut(
        id=item.id,
        class_id=item.class_id,
        section_id=item.section_id,
        class_name=item.school_class.name if item.school_class else "",
        section_name=item.section.name if item.section else "",
        teacher_id=item.teacher_id,
        teacher_name=item.teacher.teacher_name if item.teacher else "",
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


def _fee_structure_to_out(item: SchoolFeeStructure) -> FeeStructureOut:
    return FeeStructureOut(
        id=item.id,
        class_id=item.class_id,
        class_name=item.school_class.name if item.school_class else "",
        academic_year=item.academic_year,
        admission_fee=item.admission_fee,
        tuition_fee=item.tuition_fee,
        exam_fee=item.exam_fee,
        transport_fee=item.transport_fee,
        misc_fee=item.misc_fee,
        due_day=item.due_day,
        status=item.status,
    )


def _sync_teacher_class_links(
    db: Session,
    teacher: SchoolTeacher,
    class_links_payload: list,
    set_as_primary_teacher: bool = True,
) -> None:
    requested_class_ids = [x.class_id for x in class_links_payload]

    # remove stale links
    for existing in list(teacher.class_links or []):
        if existing.class_id not in requested_class_ids:
            db.delete(existing)

    # add/update requested links
    for link_in in class_links_payload:
        school_class = (
            db.query(SchoolClass)
            .filter(SchoolClass.id == link_in.class_id)
            .first()
        )
        if not school_class:
            raise HTTPException(
                status_code=404,
                detail=f"Class not found for class_id={link_in.class_id}",
            )

        existing_link = next(
            (x for x in (teacher.class_links or []) if x.class_id == link_in.class_id),
            None,
        )

        if existing_link:
            existing_link.is_primary = bool(link_in.is_primary)
        else:
            teacher.class_links.append(
                SchoolTeacherClass(
                    class_id=link_in.class_id,
                    is_primary=bool(link_in.is_primary),
                )
            )

    # ensure only one primary flag among teacher links
    primary_links = [x for x in (teacher.class_links or []) if x.is_primary]
    if len(primary_links) > 1:
        first = primary_links[0]
        for x in primary_links[1:]:
            x.is_primary = False

    # sync primary class teacher on class side
    if set_as_primary_teacher:
        primary_link = next((x for x in (teacher.class_links or []) if x.is_primary), None)

        # clear classes currently pointing to this teacher but not primary anymore
        linked_class_ids = {x.class_id for x in (teacher.class_links or [])}
        old_primary_classes = (
            db.query(SchoolClass)
            .filter(SchoolClass.class_teacher_id == teacher.id)
            .all()
        )
        for c in old_primary_classes:
            if not primary_link or c.id != primary_link.class_id:
                c.class_teacher_id = None

        if primary_link:
            primary_class = (
                db.query(SchoolClass)
                .filter(SchoolClass.id == primary_link.class_id)
                .first()
            )
            if primary_class:
                primary_class.class_teacher_id = teacher.id

        # if teacher has no links, clear any class primary assignment
        if not linked_class_ids:
            classes_with_teacher = (
                db.query(SchoolClass)
                .filter(SchoolClass.class_teacher_id == teacher.id)
                .all()
            )
            for c in classes_with_teacher:
                c.class_teacher_id = None


# --------------------------------------------------
# Classes
# --------------------------------------------------

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
    name = _normalize_text(payload.name)
    if not name:
        raise HTTPException(status_code=400, detail="Class name is required")

    existing = db.query(SchoolClass).filter(func.lower(SchoolClass.name) == name.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Class already exists")

    teacher = None
    if payload.class_teacher_id:
        teacher = db.query(SchoolTeacher).filter(SchoolTeacher.id == payload.class_teacher_id).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Class teacher not found")

    item = SchoolClass(
        name=name,
        class_teacher_id=payload.class_teacher_id,
        status=payload.status or "Active",
    )
    db.add(item)
    db.flush()

    _set_class_sections(db, item, payload.sections or [])

    # ensure reverse teacher link exists when teacher selected from class side
    if payload.class_teacher_id:
        link = (
            db.query(SchoolTeacherClass)
            .filter(
                SchoolTeacherClass.teacher_id == payload.class_teacher_id,
                SchoolTeacherClass.class_id == item.id,
            )
            .first()
        )
        if not link:
            db.add(
                SchoolTeacherClass(
                    teacher_id=payload.class_teacher_id,
                    class_id=item.id,
                    is_primary=True,
                )
            )
        else:
            link.is_primary = True

    db.commit()
    db.refresh(item)

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
    item = (
        db.query(SchoolClass)
        .options(joinedload(SchoolClass.sections))
        .filter(SchoolClass.id == class_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Class not found")

    name = _normalize_text(payload.name)
    duplicate = (
        db.query(SchoolClass)
        .filter(func.lower(SchoolClass.name) == name.lower(), SchoolClass.id != class_id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Another class with same name already exists")

    if payload.class_teacher_id:
        teacher = db.query(SchoolTeacher).filter(SchoolTeacher.id == payload.class_teacher_id).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Class teacher not found")

    old_teacher_id = item.class_teacher_id

    item.name = name
    item.status = payload.status or "Active"
    item.class_teacher_id = payload.class_teacher_id

    _set_class_sections(db, item, payload.sections or [])

    # old teacher unlink on class side
    if old_teacher_id and old_teacher_id != payload.class_teacher_id:
        old_link = (
            db.query(SchoolTeacherClass)
            .filter(
                SchoolTeacherClass.teacher_id == old_teacher_id,
                SchoolTeacherClass.class_id == item.id,
            )
            .first()
        )
        if old_link and old_link.is_primary:
            old_link.is_primary = False

    # new teacher link on class side
    if payload.class_teacher_id:
        link = (
            db.query(SchoolTeacherClass)
            .filter(
                SchoolTeacherClass.teacher_id == payload.class_teacher_id,
                SchoolTeacherClass.class_id == item.id,
            )
            .first()
        )
        if not link:
            db.add(
                SchoolTeacherClass(
                    teacher_id=payload.class_teacher_id,
                    class_id=item.id,
                    is_primary=True,
                )
            )
        else:
            link.is_primary = True

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


@router.delete("/classes/{class_id}", response_model=MessageOut)
def delete_class(class_id: int, db: Session = Depends(get_db)):
    item = db.query(SchoolClass).filter(SchoolClass.id == class_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Class not found")

    db.delete(item)
    db.commit()
    return MessageOut(message="Class deleted successfully")


# --------------------------------------------------
# Sections
# --------------------------------------------------

@router.get("/sections", response_model=SectionListOut)
def list_sections(
    class_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(SchoolSection)

    if class_id:
        query = query.filter(SchoolSection.class_id == class_id)

    items = query.order_by(SchoolSection.name.asc()).all()
    out = [_section_to_out(x) for x in items]
    return SectionListOut(items=out, total=len(out))


# --------------------------------------------------
# Students
# --------------------------------------------------

@router.get("/students", response_model=list[StudentOut])
def list_students(
    search: str = Query(default=""),
    class_id: Optional[int] = Query(default=None),
    section: str = Query(default=""),
    status_filter: str = Query(default="", alias="status"),
    db: Session = Depends(get_db),
):
    query = (
        db.query(SchoolStudent)
        .options(
            joinedload(SchoolStudent.school_class),
            joinedload(SchoolStudent.parent_links).joinedload(SchoolParentStudent.parent),
        )
    )

    if class_id:
        query = query.filter(SchoolStudent.class_id == class_id)

    if section.strip():
        query = query.filter(SchoolStudent.section == section.strip())

    if status_filter:
        query = query.filter(SchoolStudent.status == status_filter)

    if search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                SchoolStudent.name.ilike(term),
                SchoolStudent.roll_no.ilike(term),
                SchoolStudent.guardian_name.ilike(term),
                SchoolStudent.phone.ilike(term),
                SchoolStudent.section.ilike(term),
            )
        )

    items = query.order_by(SchoolStudent.name.asc()).all()
    return [_student_to_out(x) for x in items]


@router.post("/students", response_model=StudentOut, status_code=status.HTTP_201_CREATED)
def create_student(payload: StudentCreate, db: Session = Depends(get_db)):
    school_class = db.query(SchoolClass).filter(SchoolClass.id == payload.class_id).first()
    if not school_class:
        raise HTTPException(status_code=404, detail="Class not found")

    primary_parent = None
    if payload.primary_parent_id:
        primary_parent = db.query(SchoolParent).filter(SchoolParent.id == payload.primary_parent_id).first()
        if not primary_parent:
            raise HTTPException(status_code=404, detail="Primary parent not found")

    item = SchoolStudent(
        name=_normalize_text(payload.name),
        class_id=payload.class_id,
        section=_normalize_text(payload.section),
        roll_no=_normalize_text(payload.roll_no),
        guardian_name=_normalize_text(payload.guardian_name),
        phone=_normalize_text(payload.phone),
        status=payload.status or "Active",
        attendance_percentage=payload.attendance_percentage or 0,
        fee_total=payload.fee_total or 0,
        fee_paid=payload.fee_paid or 0,
        primary_parent_id=payload.primary_parent_id,
    )

    if hasattr(item, "gender"):
        item.gender = payload.gender
    if hasattr(item, "date_of_birth"):
        item.date_of_birth = payload.date_of_birth
    if hasattr(item, "date_of_admission"):
        item.date_of_admission = payload.date_of_admission

    db.add(item)
    db.flush()

    for parent_id in payload.parent_ids or []:
        parent = db.query(SchoolParent).filter(SchoolParent.id == parent_id).first()
        if not parent:
            continue
        db.add(
            SchoolParentStudent(
                parent_id=parent_id,
                student_id=item.id,
                is_primary=parent_id == payload.primary_parent_id,
                relation_label=parent.relation or "Guardian",
            )
        )

    db.commit()

    item = (
        db.query(SchoolStudent)
        .options(
            joinedload(SchoolStudent.school_class),
            joinedload(SchoolStudent.parent_links).joinedload(SchoolParentStudent.parent),
        )
        .filter(SchoolStudent.id == item.id)
        .first()
    )
    return _student_to_out(item)


@router.put("/students/{student_id}", response_model=StudentOut)
def update_student(student_id: int, payload: StudentUpdate, db: Session = Depends(get_db)):
    item = (
        db.query(SchoolStudent)
        .options(joinedload(SchoolStudent.parent_links))
        .filter(SchoolStudent.id == student_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Student not found")

    school_class = db.query(SchoolClass).filter(SchoolClass.id == payload.class_id).first()
    if not school_class:
        raise HTTPException(status_code=404, detail="Class not found")

    if payload.primary_parent_id:
        primary_parent = db.query(SchoolParent).filter(SchoolParent.id == payload.primary_parent_id).first()
        if not primary_parent:
            raise HTTPException(status_code=404, detail="Primary parent not found")

    item.name = _normalize_text(payload.name)
    item.class_id = payload.class_id
    item.section = _normalize_text(payload.section)
    item.roll_no = _normalize_text(payload.roll_no)
    item.guardian_name = _normalize_text(payload.guardian_name)
    item.phone = _normalize_text(payload.phone)
    item.status = payload.status or "Active"
    item.attendance_percentage = payload.attendance_percentage or 0
    item.fee_total = payload.fee_total or 0
    item.fee_paid = payload.fee_paid or 0
    item.primary_parent_id = payload.primary_parent_id

    if hasattr(item, "gender"):
        item.gender = payload.gender
    if hasattr(item, "date_of_birth"):
        item.date_of_birth = payload.date_of_birth
    if hasattr(item, "date_of_admission"):
        item.date_of_admission = payload.date_of_admission

    for link in list(item.parent_links or []):
        db.delete(link)
    db.flush()

    for parent_id in payload.parent_ids or []:
        parent = db.query(SchoolParent).filter(SchoolParent.id == parent_id).first()
        if not parent:
            continue
        db.add(
            SchoolParentStudent(
                parent_id=parent_id,
                student_id=item.id,
                is_primary=parent_id == payload.primary_parent_id,
                relation_label=parent.relation or "Guardian",
            )
        )

    db.commit()

    item = (
        db.query(SchoolStudent)
        .options(
            joinedload(SchoolStudent.school_class),
            joinedload(SchoolStudent.parent_links).joinedload(SchoolParentStudent.parent),
        )
        .filter(SchoolStudent.id == item.id)
        .first()
    )
    return _student_to_out(item)


@router.delete("/students/{student_id}", response_model=MessageOut)
def delete_student(student_id: int, db: Session = Depends(get_db)):
    item = db.query(SchoolStudent).filter(SchoolStudent.id == student_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Student not found")

    db.delete(item)
    db.commit()
    return MessageOut(message="Student deleted successfully")


# --------------------------------------------------
# Parents
# --------------------------------------------------

@router.get("/parents", response_model=list[ParentOut])
def list_parents(
    search: str = Query(default=""),
    status_filter: str = Query(default="", alias="status"),
    db: Session = Depends(get_db),
):
    query = (
        db.query(SchoolParent)
        .options(
            joinedload(SchoolParent.student_links)
            .joinedload(SchoolParentStudent.student)
            .joinedload(SchoolStudent.school_class)
        )
    )

    if status_filter:
        query = query.filter(SchoolParent.status == status_filter)

    if search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                SchoolParent.parent_name.ilike(term),
                SchoolParent.phone.ilike(term),
                SchoolParent.email.ilike(term),
                SchoolParent.relation.ilike(term),
            )
        )

    items = query.order_by(SchoolParent.parent_name.asc()).all()
    return [_parent_to_out(x) for x in items]


@router.post("/parents", response_model=ParentOut, status_code=status.HTTP_201_CREATED)
def create_parent(payload: ParentCreate, db: Session = Depends(get_db)):
    item = SchoolParent(
        parent_name=_normalize_text(payload.parent_name),
        relation=_normalize_text(payload.relation) or "Guardian",
        phone=_normalize_text(payload.phone),
        alt_phone=_normalize_text(payload.alt_phone),
        email=_normalize_text(payload.email),
        address=_normalize_text(payload.address),
        status=payload.status or "Active",
    )
    db.add(item)
    db.flush()

    for student_id in payload.student_ids or []:
        student = db.query(SchoolStudent).filter(SchoolStudent.id == student_id).first()
        if not student:
            continue
        db.add(
            SchoolParentStudent(
                parent_id=item.id,
                student_id=student_id,
                is_primary=student_id == payload.primary_student_id,
                relation_label=item.relation or "Guardian",
            )
        )
        if student_id == payload.primary_student_id:
            student.primary_parent_id = item.id

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
    item = (
        db.query(SchoolParent)
        .options(joinedload(SchoolParent.student_links))
        .filter(SchoolParent.id == parent_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Parent not found")

    item.parent_name = _normalize_text(payload.parent_name)
    item.relation = _normalize_text(payload.relation) or "Guardian"
    item.phone = _normalize_text(payload.phone)
    item.alt_phone = _normalize_text(payload.alt_phone)
    item.email = _normalize_text(payload.email)
    item.address = _normalize_text(payload.address)
    item.status = payload.status or "Active"

    for link in list(item.student_links or []):
        student = db.query(SchoolStudent).filter(SchoolStudent.id == link.student_id).first()
        if student and student.primary_parent_id == item.id:
            student.primary_parent_id = None
        db.delete(link)
    db.flush()

    for student_id in payload.student_ids or []:
        student = db.query(SchoolStudent).filter(SchoolStudent.id == student_id).first()
        if not student:
            continue
        db.add(
            SchoolParentStudent(
                parent_id=item.id,
                student_id=student_id,
                is_primary=student_id == payload.primary_student_id,
                relation_label=item.relation or "Guardian",
            )
        )
        if student_id == payload.primary_student_id:
            student.primary_parent_id = item.id

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


@router.delete("/parents/{parent_id}", response_model=MessageOut)
def delete_parent(parent_id: int, db: Session = Depends(get_db)):
    item = db.query(SchoolParent).filter(SchoolParent.id == parent_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Parent not found")

    students = db.query(SchoolStudent).filter(SchoolStudent.primary_parent_id == parent_id).all()
    for student in students:
        student.primary_parent_id = None

    db.delete(item)
    db.commit()
    return MessageOut(message="Parent deleted successfully")


# --------------------------------------------------
# Teachers
# --------------------------------------------------

@router.get("/teachers", response_model=TeacherListOut)
def list_teachers(
    search: str = Query(default=""),
    class_id: Optional[int] = Query(default=None),
    status_filter: str = Query(default="", alias="status"),
    db: Session = Depends(get_db),
):
    query = (
        db.query(SchoolTeacher)
        .options(
            joinedload(SchoolTeacher.class_links).joinedload(SchoolTeacherClass.school_class).joinedload(SchoolClass.sections),
            joinedload(SchoolTeacher.attendance_entries),
        )
    )

    if status_filter:
        query = query.filter(SchoolTeacher.status == status_filter)

    if class_id:
        query = query.join(SchoolTeacher.class_links).filter(SchoolTeacherClass.class_id == class_id)

    if search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                SchoolTeacher.teacher_name.ilike(term),
                SchoolTeacher.employee_id.ilike(term),
                SchoolTeacher.phone.ilike(term),
                SchoolTeacher.email.ilike(term),
                SchoolTeacher.subjects.ilike(term),
            )
        )

    items = query.order_by(SchoolTeacher.teacher_name.asc()).all()
    out = [_teacher_to_out(x) for x in items]
    return TeacherListOut(items=out, total=len(out))


@router.post("/teachers", response_model=TeacherOut, status_code=status.HTTP_201_CREATED)
def create_teacher(payload: TeacherCreate, db: Session = Depends(get_db)):
    employee_id = _normalize_text(payload.employee_id)
    duplicate = db.query(SchoolTeacher).filter(func.lower(SchoolTeacher.employee_id) == employee_id.lower()).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="Employee ID already exists")

    item = SchoolTeacher(
        teacher_name=_normalize_text(payload.teacher_name),
        employee_id=employee_id,
        phone=_normalize_text(payload.phone),
        email=_normalize_text(payload.email),
        subjects=_normalize_text(payload.subjects),
        status=payload.status or "Active",
    )
    db.add(item)
    db.flush()

    _sync_teacher_class_links(
        db=db,
        teacher=item,
        class_links_payload=payload.class_links or [],
        set_as_primary_teacher=payload.set_as_primary_teacher,
    )

    db.commit()

    item = (
        db.query(SchoolTeacher)
        .options(
            joinedload(SchoolTeacher.class_links).joinedload(SchoolTeacherClass.school_class).joinedload(SchoolClass.sections),
            joinedload(SchoolTeacher.attendance_entries),
        )
        .filter(SchoolTeacher.id == item.id)
        .first()
    )
    return _teacher_to_out(item)


@router.put("/teachers/{teacher_id}", response_model=TeacherOut)
def update_teacher(teacher_id: int, payload: TeacherUpdate, db: Session = Depends(get_db)):
    item = (
        db.query(SchoolTeacher)
        .options(joinedload(SchoolTeacher.class_links))
        .filter(SchoolTeacher.id == teacher_id)
        .first()
    )
    if not item:
        raise HTTPException(status_code=404, detail="Teacher not found")

    employee_id = _normalize_text(payload.employee_id)
    duplicate = (
        db.query(SchoolTeacher)
        .filter(func.lower(SchoolTeacher.employee_id) == employee_id.lower(), SchoolTeacher.id != teacher_id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Another teacher with same employee ID already exists")

    item.teacher_name = _normalize_text(payload.teacher_name)
    item.employee_id = employee_id
    item.phone = _normalize_text(payload.phone)
    item.email = _normalize_text(payload.email)
    item.subjects = _normalize_text(payload.subjects)
    item.status = payload.status or "Active"

    _sync_teacher_class_links(
        db=db,
        teacher=item,
        class_links_payload=payload.class_links or [],
        set_as_primary_teacher=payload.set_as_primary_teacher,
    )

    db.commit()

    item = (
        db.query(SchoolTeacher)
        .options(
            joinedload(SchoolTeacher.class_links).joinedload(SchoolTeacherClass.school_class).joinedload(SchoolClass.sections),
            joinedload(SchoolTeacher.attendance_entries),
        )
        .filter(SchoolTeacher.id == teacher_id)
        .first()
    )
    return _teacher_to_out(item)


@router.delete("/teachers/{teacher_id}", response_model=MessageOut)
def delete_teacher(teacher_id: int, db: Session = Depends(get_db)):
    item = db.query(SchoolTeacher).filter(SchoolTeacher.id == teacher_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Teacher not found")

    classes = db.query(SchoolClass).filter(SchoolClass.class_teacher_id == teacher_id).all()
    for school_class in classes:
        school_class.class_teacher_id = None

    db.delete(item)
    db.commit()
    return MessageOut(message="Teacher deleted successfully")


@router.post("/teachers/{teacher_id}/attendance", response_model=MessageOut)
def upsert_teacher_attendance(
    teacher_id: int,
    payload: TeacherAttendanceUpsertIn,
    db: Session = Depends(get_db),
):
    teacher = db.query(SchoolTeacher).filter(SchoolTeacher.id == teacher_id).first()
    if not teacher:
        raise HTTPException(status_code=404, detail="Teacher not found")

    item = (
        db.query(SchoolTeacherAttendance)
        .filter(
            SchoolTeacherAttendance.teacher_id == teacher_id,
            SchoolTeacherAttendance.attendance_date == payload.attendance_date,
        )
        .first()
    )

    if item:
        item.status = payload.status or "Present"
        message = "Teacher attendance updated successfully"
    else:
        db.add(
            SchoolTeacherAttendance(
                teacher_id=teacher_id,
                attendance_date=payload.attendance_date,
                status=payload.status or "Present",
            )
        )
        message = "Teacher attendance saved successfully"

    db.commit()
    return MessageOut(message=message)


# --------------------------------------------------
# Subject master
# --------------------------------------------------

@router.get("/settings/subjects", response_model=list[SubjectOut])
@router.get("/subjects", response_model=list[SubjectOut])
def list_subjects(db: Session = Depends(get_db)):
    items = db.query(SchoolSubject).order_by(SchoolSubject.name.asc()).all()
    return items


@router.post("/settings/subjects", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
@router.post("/subjects", response_model=SubjectOut, status_code=status.HTTP_201_CREATED)
def create_subject(payload: SubjectCreate, db: Session = Depends(get_db)):
    name = _normalize_text(payload.name)
    existing = db.query(SchoolSubject).filter(func.lower(SchoolSubject.name) == name.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Subject already exists")

    item = SchoolSubject(name=name, status=payload.status or "Active")
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

    name = _normalize_text(payload.name)
    duplicate = (
        db.query(SchoolSubject)
        .filter(func.lower(SchoolSubject.name) == name.lower(), SchoolSubject.id != subject_id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Another subject with same name already exists")

    item.name = name
    item.status = payload.status or "Active"
    db.commit()
    db.refresh(item)
    return item


@router.delete("/settings/subjects/{subject_id}", response_model=MessageOut)
@router.delete("/subjects/{subject_id}", response_model=MessageOut)
def delete_subject(subject_id: int, db: Session = Depends(get_db)):
    item = db.query(SchoolSubject).filter(SchoolSubject.id == subject_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Subject not found")

    db.delete(item)
    db.commit()
    return MessageOut(message="Subject deleted successfully")


# --------------------------------------------------
# Room master
# --------------------------------------------------

@router.get("/settings/rooms", response_model=list[RoomOut])
@router.get("/rooms", response_model=list[RoomOut])
def list_rooms(db: Session = Depends(get_db)):
    items = db.query(SchoolRoom).order_by(SchoolRoom.room_no.asc()).all()
    return items


@router.post("/settings/rooms", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
@router.post("/rooms", response_model=RoomOut, status_code=status.HTTP_201_CREATED)
def create_room(payload: RoomCreate, db: Session = Depends(get_db)):
    room_no = _normalize_text(payload.room_no)
    existing = db.query(SchoolRoom).filter(func.lower(SchoolRoom.room_no) == room_no.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Room already exists")

    item = SchoolRoom(
        room_no=room_no,
        room_name=_normalize_text(payload.room_name) or None,
        status=payload.status or "Active",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put("/settings/rooms/{room_id}", response_model=RoomOut)
@router.put("/rooms/{room_id}", response_model=RoomOut)
def update_room(room_id: int, payload: RoomUpdate, db: Session = Depends(get_db)):
    item = db.query(SchoolRoom).filter(SchoolRoom.id == room_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Room not found")

    room_no = _normalize_text(payload.room_no)
    duplicate = (
        db.query(SchoolRoom)
        .filter(func.lower(SchoolRoom.room_no) == room_no.lower(), SchoolRoom.id != room_id)
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Another room with same number already exists")

    item.room_no = room_no
    item.room_name = _normalize_text(payload.room_name) or None
    item.status = payload.status or "Active"
    db.commit()
    db.refresh(item)
    return item


@router.delete("/settings/rooms/{room_id}", response_model=MessageOut)
@router.delete("/rooms/{room_id}", response_model=MessageOut)
def delete_room(room_id: int, db: Session = Depends(get_db)):
    item = db.query(SchoolRoom).filter(SchoolRoom.id == room_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Room not found")

    db.delete(item)
    db.commit()
    return MessageOut(message="Room deleted successfully")


# --------------------------------------------------
# Timetable
# --------------------------------------------------

@router.get("/timetables", response_model=TimetableListOut)
def list_timetables(
    class_id: Optional[int] = Query(default=None),
    section_id: Optional[int] = Query(default=None),
    timetable_type: str = Query(default=""),
    day_name: str = Query(default=""),
    search: str = Query(default=""),
    db: Session = Depends(get_db),
):
    query = (
        db.query(SchoolTimetableEntry)
        .options(
            joinedload(SchoolTimetableEntry.school_class),
            joinedload(SchoolTimetableEntry.section),
            joinedload(SchoolTimetableEntry.teacher),
        )
    )

    if class_id:
        query = query.filter(SchoolTimetableEntry.class_id == class_id)

    if section_id:
        query = query.filter(SchoolTimetableEntry.section_id == section_id)

    if timetable_type:
        query = query.filter(SchoolTimetableEntry.timetable_type == timetable_type)

    if day_name:
        query = query.filter(SchoolTimetableEntry.day_name == day_name)

    if search.strip():
        term = f"%{search.strip()}%"
        query = query.outerjoin(SchoolTimetableEntry.teacher).filter(
            or_(
                SchoolTimetableEntry.subject.ilike(term),
                SchoolTimetableEntry.room.ilike(term),
                SchoolTimetableEntry.remark.ilike(term),
                SchoolTimetableEntry.period_label.ilike(term),
                SchoolTeacher.teacher_name.ilike(term),
            )
        )

    items = (
        query.order_by(
            SchoolTimetableEntry.day_name.asc(),
            SchoolTimetableEntry.period_no.asc(),
        )
        .all()
    )

    out = [_timetable_to_out(x) for x in items]
    return TimetableListOut(items=out, total=len(out))


@router.post("/timetables", response_model=TimetableEntryOut, status_code=status.HTTP_201_CREATED)
def create_timetable(payload: TimetableEntryCreate, db: Session = Depends(get_db)):
    school_class = db.query(SchoolClass).filter(SchoolClass.id == payload.class_id).first()
    if not school_class:
        raise HTTPException(status_code=404, detail="Class not found")

    _validate_section_for_class(db, payload.class_id, payload.section_id)

    if payload.teacher_id:
        teacher = db.query(SchoolTeacher).filter(SchoolTeacher.id == payload.teacher_id).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")

    duplicate = (
        db.query(SchoolTimetableEntry)
        .filter(
            SchoolTimetableEntry.class_id == payload.class_id,
            SchoolTimetableEntry.section_id == payload.section_id,
            SchoolTimetableEntry.timetable_type == payload.timetable_type,
            SchoolTimetableEntry.day_name == payload.day_name,
            SchoolTimetableEntry.period_no == payload.period_no,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(
            status_code=400,
            detail="Timetable slot already exists for this class/section/type/day/period",
        )

    item = SchoolTimetableEntry(
        class_id=payload.class_id,
        section_id=payload.section_id,
        teacher_id=payload.teacher_id,
        timetable_type=payload.timetable_type,
        day_name=payload.day_name,
        period_no=payload.period_no,
        period_label=_normalize_text(payload.period_label),
        subject=_normalize_text(payload.subject),
        start_time=_normalize_text(payload.start_time),
        end_time=_normalize_text(payload.end_time),
        room=_normalize_text(payload.room),
        remark=_normalize_text(payload.remark),
        status=payload.status or "Active",
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    item = (
        db.query(SchoolTimetableEntry)
        .options(
            joinedload(SchoolTimetableEntry.school_class),
            joinedload(SchoolTimetableEntry.section),
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

    school_class = db.query(SchoolClass).filter(SchoolClass.id == payload.class_id).first()
    if not school_class:
        raise HTTPException(status_code=404, detail="Class not found")

    _validate_section_for_class(db, payload.class_id, payload.section_id)

    if payload.teacher_id:
        teacher = db.query(SchoolTeacher).filter(SchoolTeacher.id == payload.teacher_id).first()
        if not teacher:
            raise HTTPException(status_code=404, detail="Teacher not found")

    duplicate = (
        db.query(SchoolTimetableEntry)
        .filter(
            SchoolTimetableEntry.class_id == payload.class_id,
            SchoolTimetableEntry.section_id == payload.section_id,
            SchoolTimetableEntry.timetable_type == payload.timetable_type,
            SchoolTimetableEntry.day_name == payload.day_name,
            SchoolTimetableEntry.period_no == payload.period_no,
            SchoolTimetableEntry.id != entry_id,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(
            status_code=400,
            detail="Another timetable slot already exists for this class/section/type/day/period",
        )

    item.class_id = payload.class_id
    item.section_id = payload.section_id
    item.teacher_id = payload.teacher_id
    item.timetable_type = payload.timetable_type
    item.day_name = payload.day_name
    item.period_no = payload.period_no
    item.period_label = _normalize_text(payload.period_label)
    item.subject = _normalize_text(payload.subject)
    item.start_time = _normalize_text(payload.start_time)
    item.end_time = _normalize_text(payload.end_time)
    item.room = _normalize_text(payload.room)
    item.remark = _normalize_text(payload.remark)
    item.status = payload.status or "Active"

    db.commit()

    item = (
        db.query(SchoolTimetableEntry)
        .options(
            joinedload(SchoolTimetableEntry.school_class),
            joinedload(SchoolTimetableEntry.section),
            joinedload(SchoolTimetableEntry.teacher),
        )
        .filter(SchoolTimetableEntry.id == entry_id)
        .first()
    )
    return _timetable_to_out(item)


@router.delete("/timetables/{entry_id}", response_model=MessageOut)
def delete_timetable(entry_id: int, db: Session = Depends(get_db)):
    item = db.query(SchoolTimetableEntry).filter(SchoolTimetableEntry.id == entry_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Timetable entry not found")

    db.delete(item)
    db.commit()
    return MessageOut(message="Timetable entry deleted successfully")


# --------------------------------------------------
# Fee structure
# --------------------------------------------------

@router.get("/fee-structures", response_model=list[FeeStructureOut])
def list_fee_structures(db: Session = Depends(get_db)):
    items = (
        db.query(SchoolFeeStructure)
        .options(joinedload(SchoolFeeStructure.school_class))
        .order_by(SchoolFeeStructure.class_id.asc())
        .all()
    )
    return [_fee_structure_to_out(x) for x in items]


@router.post("/fee-structures", response_model=FeeStructureOut, status_code=status.HTTP_201_CREATED)
def create_fee_structure(payload: FeeStructureCreate, db: Session = Depends(get_db)):
    school_class = db.query(SchoolClass).filter(SchoolClass.id == payload.class_id).first()
    if not school_class:
        raise HTTPException(status_code=404, detail="Class not found")

    duplicate = db.query(SchoolFeeStructure).filter(SchoolFeeStructure.class_id == payload.class_id).first()
    if duplicate:
        raise HTTPException(status_code=400, detail="Fee structure already exists for this class")

    item = SchoolFeeStructure(
        class_id=payload.class_id,
        academic_year=_normalize_text(payload.academic_year),
        admission_fee=payload.admission_fee or 0,
        tuition_fee=payload.tuition_fee or 0,
        exam_fee=payload.exam_fee or 0,
        transport_fee=payload.transport_fee or 0,
        misc_fee=payload.misc_fee or 0,
        due_day=payload.due_day or 10,
        status=payload.status or "Active",
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


@router.put("/fee-structures/{fee_structure_id}", response_model=FeeStructureOut)
def update_fee_structure(fee_structure_id: int, payload: FeeStructureUpdate, db: Session = Depends(get_db)):
    item = db.query(SchoolFeeStructure).filter(SchoolFeeStructure.id == fee_structure_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Fee structure not found")

    school_class = db.query(SchoolClass).filter(SchoolClass.id == payload.class_id).first()
    if not school_class:
        raise HTTPException(status_code=404, detail="Class not found")

    duplicate = (
        db.query(SchoolFeeStructure)
        .filter(
            SchoolFeeStructure.class_id == payload.class_id,
            SchoolFeeStructure.id != fee_structure_id,
        )
        .first()
    )
    if duplicate:
        raise HTTPException(status_code=400, detail="Another fee structure already exists for this class")

    item.class_id = payload.class_id
    item.academic_year = _normalize_text(payload.academic_year)
    item.admission_fee = payload.admission_fee or 0
    item.tuition_fee = payload.tuition_fee or 0
    item.exam_fee = payload.exam_fee or 0
    item.transport_fee = payload.transport_fee or 0
    item.misc_fee = payload.misc_fee or 0
    item.due_day = payload.due_day or 10
    item.status = payload.status or "Active"

    db.commit()

    item = (
        db.query(SchoolFeeStructure)
        .options(joinedload(SchoolFeeStructure.school_class))
        .filter(SchoolFeeStructure.id == fee_structure_id)
        .first()
    )
    return _fee_structure_to_out(item)


@router.delete("/fee-structures/{fee_structure_id}", response_model=MessageOut)
def delete_fee_structure(fee_structure_id: int, db: Session = Depends(get_db)):
    item = db.query(SchoolFeeStructure).filter(SchoolFeeStructure.id == fee_structure_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Fee structure not found")

    db.delete(item)
    db.commit()
    return MessageOut(message="Fee structure deleted successfully")
