from sqlalchemy import ForeignKey, Table, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

parent_student_link = Table(
    "parent_student_link",
    Base.metadata,
    Column("parent_profile_id", ForeignKey("parent_profiles.id"), primary_key=True),
    Column("student_profile_id", ForeignKey("student_profiles.id"), primary_key=True),
)


class ParentProfile(Base):
    __tablename__ = "parent_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)

    user = relationship("User", back_populates="parent_profile")
    children = relationship("StudentProfile", secondary=parent_student_link)
