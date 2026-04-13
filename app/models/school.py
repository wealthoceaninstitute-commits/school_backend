from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class SchoolClass(Base):
    __tablename__ = "school_classes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(50), index=True, unique=True)

    class_teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("school_teachers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status: Mapped[str] = mapped_column(String(20), default="Active")

    primary_teacher = relationship(
        "SchoolTeacher",
        back_populates="primary_for_classes",
        foreign_keys=[class_teacher_id],
    )

    teacher_links = relationship(
        "SchoolTeacherClass",
        back_populates="school_class",
        cascade="all, delete-orphan",
    )

    sections = relationship(
        "SchoolSection",
        back_populates="school_class",
        cascade="all, delete-orphan",
        order_by="SchoolSection.name",
    )

    students = relationship(
        "SchoolStudent",
        back_populates="school_class",
        cascade="all, delete-orphan",
    )

    fee_structure = relationship(
        "SchoolFeeStructure",
        back_populates="school_class",
        uselist=False,
        cascade="all, delete-orphan",
    )

    timetable_entries = relationship(
        "SchoolTimetableEntry",
        back_populates="school_class",
        cascade="all, delete-orphan",
        order_by="SchoolTimetableEntry.day_name, SchoolTimetableEntry.period_no",
    )


class SchoolSection(Base):
    __tablename__ = "school_sections"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("school_classes.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(String(20), index=True)

    school_class = relationship("SchoolClass", back_populates="sections")


class SchoolFeeStructure(Base):
    __tablename__ = "school_fee_structures"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("school_classes.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )
    academic_year: Mapped[str] = mapped_column(String(20), default="")
    admission_fee: Mapped[int] = mapped_column(Integer, default=0)
    tuition_fee: Mapped[int] = mapped_column(Integer, default=0)
    exam_fee: Mapped[int] = mapped_column(Integer, default=0)
    transport_fee: Mapped[int] = mapped_column(Integer, default=0)
    misc_fee: Mapped[int] = mapped_column(Integer, default=0)
    due_day: Mapped[int] = mapped_column(Integer, default=10)
    status: Mapped[str] = mapped_column(String(20), default="Active")

    school_class = relationship("SchoolClass", back_populates="fee_structure")


class SchoolParent(Base):
    __tablename__ = "school_parents"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    parent_name: Mapped[str] = mapped_column(String(100), index=True)
    relation: Mapped[str] = mapped_column(String(30), default="Guardian")
    phone: Mapped[str] = mapped_column(String(20), index=True)
    alt_phone: Mapped[str] = mapped_column(String(20), default="")
    email: Mapped[str] = mapped_column(String(120), default="")
    address: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="Active")

    student_links = relationship(
        "SchoolParentStudent",
        back_populates="parent",
        cascade="all, delete-orphan",
    )

    primary_for_students = relationship(
        "SchoolStudent",
        back_populates="primary_parent",
        foreign_keys="SchoolStudent.primary_parent_id",
    )


class SchoolStudent(Base):
    __tablename__ = "school_students"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), index=True)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("school_classes.id", ondelete="RESTRICT"),
        index=True,
    )
    section: Mapped[str] = mapped_column(String(20), index=True)
    roll_no: Mapped[str] = mapped_column(String(30), index=True)
    guardian_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="Active")
    attendance_percentage: Mapped[int] = mapped_column(Integer, default=0)
    fee_total: Mapped[int] = mapped_column(Integer, default=0)
    fee_paid: Mapped[int] = mapped_column(Integer, default=0)

    primary_parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("school_parents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    school_class = relationship("SchoolClass", back_populates="students")

    primary_parent = relationship(
        "SchoolParent",
        back_populates="primary_for_students",
        foreign_keys=[primary_parent_id],
    )

    parent_links = relationship(
        "SchoolParentStudent",
        back_populates="student",
        cascade="all, delete-orphan",
    )


class SchoolParentStudent(Base):
    __tablename__ = "school_parent_students"
    __table_args__ = (
        UniqueConstraint("parent_id", "student_id", name="uq_parent_student"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    parent_id: Mapped[int] = mapped_column(
        ForeignKey("school_parents.id", ondelete="CASCADE"),
        index=True,
    )
    student_id: Mapped[int] = mapped_column(
        ForeignKey("school_students.id", ondelete="CASCADE"),
        index=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)
    relation_label: Mapped[str] = mapped_column(String(30), default="Guardian")

    parent = relationship("SchoolParent", back_populates="student_links")
    student = relationship("SchoolStudent", back_populates="parent_links")


class SchoolTeacher(Base):
    __tablename__ = "school_teachers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    teacher_name: Mapped[str] = mapped_column(String(100), index=True)
    employee_id: Mapped[str] = mapped_column(String(50), index=True, unique=True)
    phone: Mapped[str] = mapped_column(String(20), default="")
    email: Mapped[str] = mapped_column(String(120), default="")
    subjects: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="Active")

    class_links = relationship(
        "SchoolTeacherClass",
        back_populates="teacher",
        cascade="all, delete-orphan",
    )

    primary_for_classes = relationship(
        "SchoolClass",
        back_populates="primary_teacher",
        foreign_keys="SchoolClass.class_teacher_id",
    )

    timetable_entries = relationship(
        "SchoolTimetableEntry",
        back_populates="teacher",
        foreign_keys="SchoolTimetableEntry.teacher_id",
    )

    attendance_entries = relationship(
        "SchoolTeacherAttendance",
        back_populates="teacher",
        cascade="all, delete-orphan",
        order_by="SchoolTeacherAttendance.attendance_date.desc()",
    )


class SchoolTeacherClass(Base):
    __tablename__ = "school_teacher_classes"
    __table_args__ = (
        UniqueConstraint("teacher_id", "class_id", name="uq_teacher_class"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("school_teachers.id", ondelete="CASCADE"),
        index=True,
    )
    class_id: Mapped[int] = mapped_column(
        ForeignKey("school_classes.id", ondelete="CASCADE"),
        index=True,
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False)

    teacher = relationship("SchoolTeacher", back_populates="class_links")
    school_class = relationship("SchoolClass", back_populates="teacher_links")


class SchoolSubject(Base):
    __tablename__ = "school_subjects"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="Active")


class SchoolTeacherAttendance(Base):
    __tablename__ = "school_teacher_attendance"
    __table_args__ = (
        UniqueConstraint("teacher_id", "attendance_date", name="uq_teacher_attendance_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    teacher_id: Mapped[int] = mapped_column(
        ForeignKey("school_teachers.id", ondelete="CASCADE"),
        index=True,
    )
    attendance_date: Mapped[Date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20), default="Present")

    teacher = relationship("SchoolTeacher", back_populates="attendance_entries")


class SchoolTimetableEntry(Base):
    __tablename__ = "school_timetable_entries"
    __table_args__ = (
        UniqueConstraint(
            "class_id",
            "timetable_type",
            "day_name",
            "period_no",
            name="uq_school_timetable_slot",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    class_id: Mapped[int] = mapped_column(
        ForeignKey("school_classes.id", ondelete="CASCADE"),
        index=True,
    )
    teacher_id: Mapped[int | None] = mapped_column(
        ForeignKey("school_teachers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    timetable_type: Mapped[str] = mapped_column(String(20), index=True, default="Regular")
    day_name: Mapped[str] = mapped_column(String(20), index=True)
    period_no: Mapped[int] = mapped_column(Integer, default=1)
    period_label: Mapped[str] = mapped_column(String(50), default="")
    subject: Mapped[str] = mapped_column(String(100), default="")
    start_time: Mapped[str] = mapped_column(String(10), default="")
    end_time: Mapped[str] = mapped_column(String(10), default="")
    room: Mapped[str] = mapped_column(String(50), default="")
    remark: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(20), default="Active")

    school_class = relationship("SchoolClass", back_populates="timetable_entries")
    teacher = relationship("SchoolTeacher", back_populates="timetable_entries")
