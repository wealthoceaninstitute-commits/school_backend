from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


# -----------------------------
# Common
# -----------------------------

class MessageOut(BaseModel):
    ok: bool = True
    message: str


# -----------------------------
# Classes / Sections
# -----------------------------

class ClassBase(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    sections: list[str] = []
    status: str = "Active"


class ClassCreate(ClassBase):
    class_teacher_id: Optional[int] = None


class ClassUpdate(ClassBase):
    class_teacher_id: Optional[int] = None


class ClassOut(ClassBase):
    id: int
    class_teacher_id: Optional[int] = None
    class_teacher: str = ""
    student_count: int = 0

    class Config:
        from_attributes = True


# -----------------------------
# Parents
# -----------------------------

class ParentBase(BaseModel):
    parent_name: str = Field(min_length=1, max_length=100)
    relation: str = "Guardian"
    phone: str = Field(min_length=1, max_length=20)
    alt_phone: str = ""
    email: str = ""
    address: str = ""
    status: str = "Active"


class ParentCreate(ParentBase):
    student_ids: list[int] = []
    primary_student_id: Optional[int] = None


class ParentUpdate(ParentBase):
    student_ids: list[int] = []
    primary_student_id: Optional[int] = None


class ParentStudentMiniOut(BaseModel):
    id: int
    name: str
    class_id: int
    class_name: str
    section: str = ""
    roll_no: str = ""
    is_primary: bool = False

    class Config:
        from_attributes = True


class ParentOut(ParentBase):
    id: int
    students: list[ParentStudentMiniOut] = []

    class Config:
        from_attributes = True


# -----------------------------
# Students
# -----------------------------

class StudentBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    class_id: int
    section: str = Field(min_length=1, max_length=20)
    roll_no: str = Field(min_length=1, max_length=30)
    guardian_name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=1, max_length=20)
    status: str = "Active"
    attendance_percentage: int = 0
    fee_total: int = 0
    fee_paid: int = 0
    gender: Optional[str] = None
    date_of_birth: Optional[date] = None
    date_of_admission: Optional[date] = None


class StudentCreate(StudentBase):
    parent_ids: list[int] = []
    primary_parent_id: Optional[int] = None


class StudentUpdate(StudentBase):
    parent_ids: list[int] = []
    primary_parent_id: Optional[int] = None


class StudentParentMiniOut(BaseModel):
    id: int
    parent_name: str
    relation: str = "Guardian"
    phone: str = ""
    is_primary: bool = False

    class Config:
        from_attributes = True


class StudentOut(StudentBase):
    id: int
    class_name: str = ""
    pending_fee: int = 0
    parents: list[StudentParentMiniOut] = []

    class Config:
        from_attributes = True


# -----------------------------
# Teachers
# -----------------------------

class TeacherClassLinkIn(BaseModel):
    class_id: int
    is_primary: bool = False


class TeacherClassMiniOut(BaseModel):
    id: int
    name: str
    sections: list[str] = []
    is_primary: bool = False

    class Config:
        from_attributes = True


class TeacherBase(BaseModel):
    teacher_name: str = Field(min_length=1, max_length=100)
    employee_id: str = Field(min_length=1, max_length=50)
    phone: str = ""
    email: str = ""
    subjects: str = ""
    status: str = "Active"


class TeacherCreate(TeacherBase):
    set_as_primary_teacher: bool = True
    class_links: list[TeacherClassLinkIn] = []


class TeacherUpdate(TeacherBase):
    set_as_primary_teacher: bool = True
    class_links: list[TeacherClassLinkIn] = []


class TeacherAttendanceUpsertIn(BaseModel):
    attendance_date: date
    status: str = "Present"


class TeacherOut(TeacherBase):
    id: int
    classes: list[TeacherClassMiniOut] = []
    class_count: int = 0
    present_days: int = 0
    working_days: int = 0
    attendance_percentage: int = 0

    class Config:
        from_attributes = True


class TeacherListOut(BaseModel):
    items: list[TeacherOut]
    total: int


# -----------------------------
# Subjects master
# -----------------------------

class SubjectBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    status: str = "Active"


class SubjectCreate(SubjectBase):
    pass


class SubjectUpdate(SubjectBase):
    pass


class SubjectOut(SubjectBase):
    id: int

    class Config:
        from_attributes = True


# -----------------------------
# Rooms master
# -----------------------------

class RoomBase(BaseModel):
    room_no: str = Field(min_length=1, max_length=50)
    room_name: Optional[str] = None
    status: str = "Active"


class RoomCreate(RoomBase):
    pass


class RoomUpdate(RoomBase):
    pass


class RoomOut(RoomBase):
    id: int

    class Config:
        from_attributes = True


# -----------------------------
# Timetable
# -----------------------------

class TimetableEntryBase(BaseModel):
    class_id: int
    teacher_id: Optional[int] = None
    timetable_type: str = "Regular"
    day_name: str = "Monday"
    period_no: int = 1
    period_label: str = ""
    subject: str = Field(min_length=1, max_length=100)
    start_time: str = ""
    end_time: str = ""
    room: str = ""
    remark: str = ""
    status: str = "Active"


class TimetableEntryCreate(TimetableEntryBase):
    pass


class TimetableEntryUpdate(TimetableEntryBase):
    pass


class TimetableEntryOut(TimetableEntryBase):
    id: int
    class_name: str = ""
    teacher_name: str = ""

    class Config:
        from_attributes = True


class TimetableListOut(BaseModel):
    items: list[TimetableEntryOut]
    total: int


# -----------------------------
# Fee structure
# -----------------------------

class FeeStructureBase(BaseModel):
    class_id: int
    academic_year: str = ""
    admission_fee: int = 0
    tuition_fee: int = 0
    exam_fee: int = 0
    transport_fee: int = 0
    misc_fee: int = 0
    due_day: int = 10
    status: str = "Active"


class FeeStructureCreate(FeeStructureBase):
    pass


class FeeStructureUpdate(FeeStructureBase):
    pass


class FeeStructureOut(FeeStructureBase):
    id: int
    class_name: str = ""

    class Config:
        from_attributes = True
