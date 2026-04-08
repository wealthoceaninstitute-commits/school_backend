from sqlalchemy import ForeignKey, String, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class StudentProfile(Base):
    __tablename__ = "student_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    class_name: Mapped[str] = mapped_column(String(20))
    roll_no: Mapped[int] = mapped_column(Integer)
    guardian_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))

    user = relationship("User", back_populates="student_profile")
    timetables = relationship("TimetableEntry", back_populates="student_profile", cascade="all, delete-orphan")
    results = relationship("ResultEntry", back_populates="student_profile", cascade="all, delete-orphan")
    homeworks = relationship("HomeworkEntry", back_populates="student_profile", cascade="all, delete-orphan")
    attendance_records = relationship("AttendanceRecord", back_populates="student_profile", cascade="all, delete-orphan")
    fees = relationship("FeeEntry", back_populates="student_profile", cascade="all, delete-orphan")


class TimetableEntry(Base):
    __tablename__ = "timetable_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_profile_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"))
    period: Mapped[str] = mapped_column(String(50))
    subject: Mapped[str] = mapped_column(String(100))
    time_slot: Mapped[str] = mapped_column(String(50))

    student_profile = relationship("StudentProfile", back_populates="timetables")


class ResultEntry(Base):
    __tablename__ = "result_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_profile_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"))
    subject: Mapped[str] = mapped_column(String(100))
    marks: Mapped[int] = mapped_column(Integer)
    out_of: Mapped[int] = mapped_column(Integer)
    grade: Mapped[str] = mapped_column(String(10))

    student_profile = relationship("StudentProfile", back_populates="results")


class HomeworkEntry(Base):
    __tablename__ = "homework_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_profile_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"))
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(255))
    subject: Mapped[str] = mapped_column(String(100))
    due_date: Mapped[str] = mapped_column(String(30))

    student_profile = relationship("StudentProfile", back_populates="homeworks")


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_profile_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"))
    day_label: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))

    student_profile = relationship("StudentProfile", back_populates="attendance_records")


class FeeEntry(Base):
    __tablename__ = "fee_entries"

    id: Mapped[int] = mapped_column(primary_key=True)
    student_profile_id: Mapped[int] = mapped_column(ForeignKey("student_profiles.id"))
    title: Mapped[str] = mapped_column(String(100))
    amount: Mapped[int] = mapped_column(Integer)
    due_date: Mapped[str] = mapped_column(String(30))

    student_profile = relationship("StudentProfile", back_populates="fees")
