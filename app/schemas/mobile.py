from pydantic import BaseModel, Field


class AppMeOut(BaseModel):
    user_id: int
    username: str
    display_name: str
    role: str
    linked_entity_id: int | None = None


class AppDashboardOut(BaseModel):
    student_name: str
    class_name: str
    section: str
    roll_no: str
    attendance_percentage: int
    fee_total: int
    fee_paid: int
    fee_balance: int
    notices_count: int
    today_periods: int


class AppAttendanceOut(BaseModel):
    attendance_percentage: int
    present_days: int
    absent_days: int
    total_days: int


class AppFeeItemOut(BaseModel):
    fee_head: str
    amount: int


class AppFeesOut(BaseModel):
    class_name: str
    academic_year: str
    fee_total: int
    fee_paid: int
    fee_balance: int
    items: list[AppFeeItemOut] = Field(default_factory=list)


class AppTimetableItemOut(BaseModel):
    id: int
    timetable_type: str
    day_name: str
    period_no: int
    period_label: str
    subject: str
    start_time: str
    end_time: str
    teacher_name: str
    room: str
    remark: str
    status: str


class AppStudentProfileOut(BaseModel):
    id: int
    name: str
    class_id: int
    class_name: str
    section: str
    roll_no: str
    guardian_name: str
    phone: str
    attendance_percentage: int
    fee_total: int
    fee_paid: int
    fee_balance: int


class AppNoticeOut(BaseModel):
    id: int
    title: str
    message: str
    audience: str
