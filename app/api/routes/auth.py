from datetime import datetime, timedelta, timezone
import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.db.deps import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordConfirmRequest,
    ForgotPasswordRequest,
    ForgotPasswordRequestResponse,
    LoginRequest,
    MessageResponse,
    TokenResponse,
)

router = APIRouter()


def _login_identity_label(user: User) -> str:
    if user.role == "parent":
        return "registered phone/email"
    if user.role == "teacher":
        return "registered phone/email"
    return "registered username"


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    query = db.query(User).filter(User.username == payload.username.strip().lower())
    if payload.role:
        query = query.filter(User.role == payload.role)
    user = query.first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is inactive. Contact school administration")

    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    token = create_access_token(subject=user.username, role=user.role)
    return TokenResponse(
        access_token=token,
        role=user.role,
        display_name=user.display_name,
        user_id=user.id,
        must_change_password=bool(user.must_change_password),
        school_student_id=user.school_student_id,
        school_parent_id=user.school_parent_id,
        school_teacher_id=user.school_teacher_id,
    )


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Old password is incorrect")

    if payload.old_password == payload.new_password:
        raise HTTPException(status_code=400, detail="New password must be different from old password")

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.reset_otp_code = None
    user.reset_otp_expiry = None
    db.commit()
    return MessageResponse(message="Password changed successfully")


@router.post("/forgot-password/request", response_model=ForgotPasswordRequestResponse)
def forgot_password_request(payload: ForgotPasswordRequest, db: Session = Depends(get_db)):
    if payload.role == "student":
        raise HTTPException(status_code=400, detail="Students must contact school administration or parent for password reset")

    user = (
        db.query(User)
        .filter(
            User.username == payload.username.strip().lower(),
            User.role == payload.role,
        )
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")

    otp = f"{random.randint(100000, 999999)}"
    user.reset_otp_code = otp
    user.reset_otp_expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.commit()

    otp_sent_to = _login_identity_label(user)
    debug_otp = otp if settings.app_env.lower() != "production" else None

    return ForgotPasswordRequestResponse(
        message="OTP generated successfully",
        otp_sent_to=otp_sent_to,
        otp_debug=debug_otp,
    )


@router.post("/forgot-password/confirm", response_model=MessageResponse)
def forgot_password_confirm(payload: ForgotPasswordConfirmRequest, db: Session = Depends(get_db)):
    user = (
        db.query(User)
        .filter(
            User.username == payload.username.strip().lower(),
            User.role == payload.role,
        )
        .first()
    )
    if not user:
        raise HTTPException(status_code=404, detail="Account not found")

    if not user.reset_otp_code or not user.reset_otp_expiry:
        raise HTTPException(status_code=400, detail="No password reset request found")

    expiry = user.reset_otp_expiry
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) > expiry:
        user.reset_otp_code = None
        user.reset_otp_expiry = None
        db.commit()
        raise HTTPException(status_code=400, detail="OTP expired. Please request a new one")

    if user.reset_otp_code != payload.otp.strip():
        raise HTTPException(status_code=400, detail="Invalid OTP")

    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.reset_otp_code = None
    user.reset_otp_expiry = None
    db.commit()
    return MessageResponse(message="Password reset successfully")
