from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import require_role
from app.db.deps import get_db
from app.models.student import AttendanceRecord, StudentProfile
from app.models.user import User
from app.schemas.teacher import TeacherClassOut, AttendanceRosterItemOut, SaveAttendanceRequest, SaveAttendanceResponse

router = APIRouter()


@router.get("/classes", response_model=list[TeacherClassOut])
def classes(user: User = Depends(require_role("teacher"))):
    profile = user.teacher_profile
    return [TeacherClassOut(class_name=x.class_name, subject=x.subject, student_count=x.student_count) for x in profile.classes]


@router.get("/attendance/roster", response_model=list[AttendanceRosterItemOut])
def attendance_roster(db: Session = Depends(get_db), user: User = Depends(require_role("teacher"))):
    class_name = user.teacher_profile.classes[0].class_name if user.teacher_profile.classes else None
    rows = []
    if class_name:
        students = db.query(StudentProfile).filter(StudentProfile.class_name == class_name).all()
        for student in students:
            latest = student.attendance_records[-1].status if student.attendance_records else "Absent"
            rows.append(
                AttendanceRosterItemOut(
                    student_profile_id=student.id,
                    student_name=student.user.display_name,
                    is_present=(latest == "Present"),
                )
            )
    return rows


@router.post("/attendance/save", response_model=SaveAttendanceResponse)
def save_attendance(payload: SaveAttendanceRequest, db: Session = Depends(get_db), user: User = Depends(require_role("teacher"))):
    saved_count = 0
    for item in payload.items:
        db.add(AttendanceRecord(student_profile_id=item.student_profile_id, day_label=payload.day_label, status="Present" if item.is_present else "Absent"))
        saved_count += 1
    db.commit()
    return SaveAttendanceResponse(success=True, saved_count=saved_count)
