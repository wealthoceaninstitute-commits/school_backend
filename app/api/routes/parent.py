from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import require_role
from app.models.user import User
from app.schemas.parent import ChildOut, FeeItemOut, ParentFeesOut

router = APIRouter()


@router.get("/children", response_model=list[ChildOut])
def get_children(user: User = Depends(require_role("parent"))):
    profile = user.parent_profile
    if not profile:
        return []

    children = []
    for child in profile.children:
        total_due = sum(item.amount for item in child.fees)
        children.append(
            ChildOut(
                student_profile_id=child.id,
                student_user_id=child.user.id,
                name=child.user.display_name,
                class_name=child.class_name,
                roll_no=child.roll_no,
                attendance="92%" if child.class_name == "8-A" else "95%",
                fees_due=f"₹{total_due:,}",
                pending_homework=len(child.homeworks),
            )
        )
    return children


@router.get("/fees/{student_profile_id}", response_model=ParentFeesOut)
def get_fees(student_profile_id: int, user: User = Depends(require_role("parent"))):
    profile = user.parent_profile
    if not profile:
        raise HTTPException(status_code=404, detail="Parent profile not found")

    child = next((c for c in profile.children if c.id == student_profile_id), None)
    if not child:
        raise HTTPException(status_code=404, detail="Child not found for this parent")

    items = [FeeItemOut(title=f.title, amount=f.amount, due_date=f.due_date) for f in child.fees]
    return ParentFeesOut(
        student_profile_id=child.id,
        student_name=child.user.display_name,
        total_due=sum(x.amount for x in child.fees),
        items=items,
    )
