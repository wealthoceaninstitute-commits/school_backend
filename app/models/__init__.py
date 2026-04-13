from app.models.notice import Notice
from app.models.parent import ParentProfile, parent_student_link
from app.models.school import (
    SchoolClass,
    SchoolSection,
    SchoolStudent,
    SchoolParent,
    SchoolTeacher,
    SchoolAttendance,
    SchoolFee,
    SchoolTimetable,
    SchoolResult,
    SchoolNotice,
    SchoolSubject,
    SchoolRoom,
)
from app.models.student import (
    AttendanceRecord,
    FeeEntry,
    HomeworkEntry,
    ResultEntry,
    StudentProfile,
    TimetableEntry,
)
from app.models.teacher import TeacherClass, TeacherProfile
from app.models.user import User
from app.models.school import SchoolSubject, SchoolRoom

__all__ = [
    "User",
    "StudentProfile",
    "TimetableEntry",
    "ResultEntry",
    "HomeworkEntry",
    "AttendanceRecord",
    "FeeEntry",
    "ParentProfile",
    "parent_student_link",
    "TeacherProfile",
    "TeacherClass",
    "Notice",
    "SchoolClass",
    "SchoolFeeStructure",
    "SchoolSection",
    "SchoolParent",
    "SchoolStudent",
    "SchoolParentStudent",
    "SchoolTeacher",
    "SchoolTeacherAttendance",
    "SchoolTeacherClass",
    "SchoolTimetableEntry",
    "SchoolSubject",
]
