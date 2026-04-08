from fastapi import APIRouter, Depends

from app.api.deps import require_role
from app.models.user import User
from app.schemas.student import DashboardOut, AttendanceItemOut, HomeworkOut, TimetableOut, ResultOut, StudentProfileOut

router = APIRouter()


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(user: User = Depends(require_role("student"))):
    profile = user.student_profile
    return DashboardOut(attendance="92%", homework_pending=len(profile.homeworks), upcoming_tests=2)


@router.get("/attendance", response_model=list[AttendanceItemOut])
def attendance(user: User = Depends(require_role("student"))):
    return [AttendanceItemOut(day_label=x.day_label, status=x.status) for x in user.student_profile.attendance_records]


@router.get("/homework", response_model=list[HomeworkOut])
def homework(user: User = Depends(require_role("student"))):
    return [HomeworkOut(title=x.title, description=x.description, subject=x.subject, due_date=x.due_date) for x in user.student_profile.homeworks]


@router.get("/timetable", response_model=list[TimetableOut])
def timetable(user: User = Depends(require_role("student"))):
    return [TimetableOut(period=x.period, subject=x.subject, time_slot=x.time_slot) for x in user.student_profile.timetables]


@router.get("/results", response_model=list[ResultOut])
def results(user: User = Depends(require_role("student"))):
    return [ResultOut(subject=x.subject, marks=x.marks, out_of=x.out_of, grade=x.grade) for x in user.student_profile.results]


@router.get("/profile", response_model=StudentProfileOut)
def profile(user: User = Depends(require_role("student"))):
    p = user.student_profile
    return StudentProfileOut(name=user.display_name, class_name=p.class_name, roll_no=p.roll_no, guardian_name=p.guardian_name, phone=p.phone)
