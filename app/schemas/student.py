from pydantic import BaseModel


class DashboardOut(BaseModel):
    attendance: str
    homework_pending: int
    upcoming_tests: int


class AttendanceItemOut(BaseModel):
    day_label: str
    status: str


class HomeworkOut(BaseModel):
    title: str
    description: str
    subject: str
    due_date: str


class TimetableOut(BaseModel):
    period: str
    subject: str
    time_slot: str


class ResultOut(BaseModel):
    subject: str
    marks: int
    out_of: int
    grade: str


class StudentProfileOut(BaseModel):
    name: str
    class_name: str
    roll_no: int
    guardian_name: str
    phone: str
