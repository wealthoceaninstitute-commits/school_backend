from app.models.notice import Notice
from app.models.parent import ParentProfile, parent_student_link
from app.models.school import (
    SchoolClass,
    SchoolSection,
    SchoolFeeStructure,
    SchoolParent,
    SchoolStudent,
    SchoolParentStudent,
    SchoolTeacher,
    SchoolTeacherClass,
    SchoolTeacherAttendance,
    SchoolTimetableEntry,
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
    "SchoolSection",
    "SchoolFeeStructure",
    "SchoolParent",
    "SchoolStudent",
    "SchoolParentStudent",
    "SchoolTeacher",
    "SchoolTeacherClass",
    "SchoolTeacherAttendance",
    "SchoolTimetableEntry",
    "SchoolSubject",
    "SchoolRoom",
]
