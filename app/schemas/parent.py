from pydantic import BaseModel


class ChildOut(BaseModel):
    student_profile_id: int
    student_user_id: int
    name: str
    class_name: str
    roll_no: int
    attendance: str
    fees_due: str
    pending_homework: int


class FeeItemOut(BaseModel):
    title: str
    amount: int
    due_date: str


class ParentFeesOut(BaseModel):
    student_profile_id: int
    student_name: str
    total_due: int
    items: list[FeeItemOut]
