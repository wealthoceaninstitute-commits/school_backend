from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.deps import get_db
from app.models.notice import Notice
from app.models.user import User
from app.schemas.common import NoticeOut

router = APIRouter()


@router.get("", response_model=list[NoticeOut])
def get_notices(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    audiences = ["all", user.role]
    rows = db.query(Notice).filter(Notice.audience.in_(audiences)).order_by(Notice.id.desc()).all()
    return rows
