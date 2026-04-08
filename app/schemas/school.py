from typing import Optional
from pydantic import BaseModel, Field, computed_field, model_validator


# =========================
# Classes
# =========================

class ClassBase(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    sections: list[str] = Field(default_factory=list)
    class_teacher: str = ""
    status: str = "Active"


class ClassCreate(ClassBase):
    pass


class ClassUpdate(ClassBase):
    pass


class ClassOut(ClassBase):
    id: int
    class_teacher_id: Optional[int] = None
    class_teacher: str = ""

    class Config:
        from_attributes = True


# =========================
# Fee Models
# =========================

class FeeComponentBase(BaseModel):
    fee_head: str = Field(min_length=1, max_length=100)
    amount: int = Field(ge=0, default=0)
    is_optional: bool = False
    remark: str = Field(default="", max_length=255)


class FeeComponentCreate(FeeComponentBase):
    pass


class FeeComponentUpdate(FeeComponentBase):
    pass


class FeeComponentOut(FeeComponentBase):
    id: int

    class Config:
        from_attributes = True


class ClassFeePlanBase(BaseModel):
    class_id: int
    academic_year: str = Field(min_length=1, max_length=20, default="2025-26")
    plan_name: str = Field(min_length=1, max_length=100, default="Standard Fee Plan")
    description: str = Field(default="", max_length=255)
    status: str = "Active"
    components: list[FeeComponentCreate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_components(self):
        seen = set()
        cleaned = []
        for item in self.components:
            key = item.fee_head.strip().lower()
            if not key:
                continue
            if key in seen:
                raise ValueError(f"Duplicate fee head not allowed: {item.fee_head}")
            seen.add(key)
            cleaned.append(item)
        self.components = cleaned
        return self


class ClassFeePlanCreate(ClassFeePlanBase):
    pass


class ClassFeePlanUpdate(ClassFeePlanBase):
    pass


class ClassFeePlanOut(BaseModel):
    id: int
    class_id: int
    class_name: str = ""
    academic_year: str
    plan_name: str
    description: str = ""
    status: str
    components: list[FeeComponentOut] = Field(default_factory=list)

    @computed_field
    @property
    def total_amount(self) -> int:
        return sum(int(item.amount or 0) for item in self.components)

    class Config:
        from_attributes = True


class ClassFeePlanListResponse(BaseModel):
    items: list[ClassFeePlanOut]
    total: int


class AssignClassFeeToStudentsIn(BaseModel):
    class_id: int
    fee_plan_id: int
    apply_to_existing_students: bool = True
    overwrite_student_fee_total: bool = True
    reset_student_fee_paid_if_exceeds_total: bool = False


# =========================
# Students
# =========================

class StudentBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    class_id: int
    section: str = Field(min_length=1, max_length=20)
    roll_no: str = Field(min_length=1, max_length=30)
    guardian_name: str = Field(min_length=1, max_length=100)
    phone: str = Field(min_length=10, max_length=20)
    status: str = "Active"
    attendance_percentage: int = Field(ge=0, le=100, default=0)
    fee_total: int = Field(ge=0, default=0)
    fee_paid: int = Field(ge=0, default=0)

    @model_validator(mode="after")
    def validate_fee_values(self):
        if self.fee_paid > self.fee_total:
            raise ValueError("fee_paid cannot be greater than fee_total")
        return self


class StudentCreate(StudentBase):
    pass


class StudentUpdate(StudentBase):
    pass


class StudentOut(StudentBase):
    id: int
    class_name: str
    primary_parent_id: Optional[int] = None
    primary_parent_name: str = ""

    @computed_field
    @property
    def fee_balance(self) -> int:
        return max(int(self.fee_total or 0) - int(self.fee_paid or 0), 0)

    @computed_field
    @property
    def fee_status(self) -> str:
        if self.fee_total <= 0:
            return "Pending"
        if self.fee_paid <= 0:
            return "Pending"
        if self.fee_paid >= self.fee_total:
            return "Paid"
        return "Partial"

    class Config:
        from_attributes = True


class StudentListResponse(BaseModel):
    items: list[StudentOut]
    total: int


class StudentOptionOut(BaseModel):
    id: int
    name: str
    class_id: int
    class_name: str
    section: str
    roll_no: str
    guardian_name: str
    phone: str

    class Config:
        from_attributes = True


# =========================
# Parents
# =========================

class ParentStudentLinkIn(BaseModel):
    student_id: int
    is_primary: bool = False
    relation_label: str = "Guardian"


class ParentBase(BaseModel):
    parent_name: str = Field(min_length=1, max_length=100)
    relation: str = Field(min_length=1, max_length=30, default="Guardian")
    phone: str = Field(min_length=10, max_length=20)
    alt_phone: str = ""
    email: str = ""
    address: str = ""
    status: str = "Active"
    student_links: list[ParentStudentLinkIn] = Field(default_factory=list)
    sync_to_students: bool = True
    set_as_primary_parent: bool = True


class ParentCreate(ParentBase):
    pass


class ParentUpdate(ParentBase):
    pass


class ParentLinkedStudentOut(BaseModel):
    id: int
    name: str
    class_id: int
    class_name: str
    section: str
    roll_no: str
    guardian_name: str
    phone: str
    is_primary: bool
    relation_label: str

    class Config:
        from_attributes = True


class ParentOut(BaseModel):
    id: int
    parent_name: str
    relation: str
    phone: str
    alt_phone: str
    email: str
    address: str
    status: str
    student_count: int
    students: list[ParentLinkedStudentOut]

    class Config:
        from_attributes = True


class ParentListResponse(BaseModel):
    items: list[ParentOut]
    total: int


# =========================
# Teachers
# =========================

class TeacherClassLinkIn(BaseModel):
    class_id: int
    is_primary: bool = False


class TeacherClassOut(BaseModel):
    id: int
    name: str
    sections: list[str] = Field(default_factory=list)
    is_primary: bool = False


class TeacherBase(BaseModel):
    teacher_name: str = Field(min_length=1, max_length=100)
    employee_id: str = Field(min_length=1, max_length=50)
    phone: str = ""
    email: str = ""
    subjects: str = ""
    status: str = "Active"
    class_links: list[TeacherClassLinkIn] = Field(default_factory=list)
    set_as_primary_teacher: bool = True


class TeacherCreate(TeacherBase):
    pass


class TeacherUpdate(TeacherBase):
    pass


class TeacherOut(BaseModel):
    id: int
    teacher_name: str
    employee_id: str
    phone: str
    email: str
    subjects: str
    status: str
    class_count: int
    classes: list[TeacherClassOut] = Field(default_factory=list)

    class Config:
        from_attributes = True


class TeacherListResponse(BaseModel):
    items: list[TeacherOut]
    total: int

# =========================
# Timetable
# =========================

class TimetableEntryBase(BaseModel):
    class_id: int
    teacher_id: Optional[int] = None
    timetable_type: str = Field(min_length=1, max_length=20, default="Regular")
    day_name: str = Field(min_length=1, max_length=20)
    period_no: int = Field(ge=1, le=20, default=1)
    period_label: str = Field(default="", max_length=50)
    subject: str = Field(default="", max_length=100)
    start_time: str = Field(default="", max_length=10)
    end_time: str = Field(default="", max_length=10)
    room: str = Field(default="", max_length=50)
    remark: str = Field(default="", max_length=255)
    status: str = "Active"

    @model_validator(mode="after")
    def validate_timetable_type(self):
        allowed = {"Regular", "Test", "Exam"}
        value = (self.timetable_type or "").strip().title()
        if value not in allowed:
            raise ValueError("timetable_type must be one of: Regular, Test, Exam")
        self.timetable_type = value

        day_value = (self.day_name or "").strip().title()
        self.day_name = day_value
        return self


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


class TimetableEntryListResponse(BaseModel):
    items: list[TimetableEntryOut]
    total: int

# =========================
# App Users / Login Linking
# =========================

class AppUserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=6, max_length=100)
    role: str = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def validate_role(self):
        value = (self.role or "").strip().lower()
        allowed = {"admin", "student", "parent", "teacher"}
        if value not in allowed:
            raise ValueError("role must be one of: admin, student, parent, teacher")
        self.role = value
        self.username = self.username.strip().lower()
        self.display_name = self.display_name.strip()
        return self


class AppUserOut(BaseModel):
    id: int
    username: str
    display_name: str
    role: str
    school_student_id: Optional[int] = None
    school_parent_id: Optional[int] = None
    school_teacher_id: Optional[int] = None

    class Config:
        from_attributes = True


class AppUserListResponse(BaseModel):
    items: list[AppUserOut]
    total: int


class UserLinkResultOut(BaseModel):
    ok: bool = True
    message: str
    user: AppUserOut
