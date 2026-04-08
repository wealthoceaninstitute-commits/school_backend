from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class TeacherProfile(Base):
    __tablename__ = "teacher_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    department: Mapped[str] = mapped_column(String(100))
    employee_code: Mapped[str] = mapped_column(String(50), unique=True)

    user = relationship("User", back_populates="teacher_profile")
    classes = relationship("TeacherClass", back_populates="teacher_profile", cascade="all, delete-orphan")


class TeacherClass(Base):
    __tablename__ = "teacher_classes"

    id: Mapped[int] = mapped_column(primary_key=True)
    teacher_profile_id: Mapped[int] = mapped_column(ForeignKey("teacher_profiles.id"))
    class_name: Mapped[str] = mapped_column(String(20))
    subject: Mapped[str] = mapped_column(String(100))
    student_count: Mapped[int] = mapped_column()

    teacher_profile = relationship("TeacherProfile", back_populates="classes")
