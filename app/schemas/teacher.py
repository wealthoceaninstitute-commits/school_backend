from pydantic import BaseModel


class TeacherClassOut(BaseModel):
    class_name: str
    subject: str
    student_count: int


class AttendanceRosterItemOut(BaseModel):
    student_profile_id: int
    student_name: str
    is_present: bool


class SaveAttendanceItem(BaseModel):
    student_profile_id: int
    is_present: bool


class SaveAttendanceRequest(BaseModel):
    day_label: str
    items: list[SaveAttendanceItem]


class SaveAttendanceResponse(BaseModel):
    success: bool
    saved_count: int
