from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(100))
    role: Mapped[str] = mapped_column(String(20), index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(default=True)
    must_change_password: Mapped[bool] = mapped_column(default=True)
    reset_otp_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    reset_otp_expiry: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Legacy demo profile relations
    student_profile = relationship("StudentProfile", back_populates="user", uselist=False)
    parent_profile = relationship("ParentProfile", back_populates="user", uselist=False)
    teacher_profile = relationship("TeacherProfile", back_populates="user", uselist=False)

    # Real school entity mappings for app/backend unification
    school_student_id: Mapped[int | None] = mapped_column(
        ForeignKey("school_students.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    school_parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("school_parents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    school_teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("school_teachers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    school_student = relationship("SchoolStudent", foreign_keys=[school_student_id])
    school_parent = relationship("SchoolParent", foreign_keys=[school_parent_id])
    school_teacher = relationship("SchoolTeacher", foreign_keys=[school_teacher_id])
