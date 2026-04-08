from pydantic import BaseModel, Field, field_validator


class LoginRequest(BaseModel):
    role: str | None = None
    username: str
    password: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value):
        if value is None:
            return value
        value = value.strip().lower()
        allowed = {"admin", "student", "parent", "teacher"}
        if value not in allowed:
            raise ValueError("role must be one of: admin, student, parent, teacher")
        return value


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    display_name: str
    user_id: int
    must_change_password: bool = False
    school_student_id: int | None = None
    school_parent_id: int | None = None
    school_teacher_id: int | None = None


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str = Field(min_length=6, max_length=100)


class ForgotPasswordRequest(BaseModel):
    role: str
    username: str

    @field_validator("role")
    @classmethod
    def validate_role(cls, value):
        value = value.strip().lower()
        allowed = {"parent", "teacher"}
        if value not in allowed:
            raise ValueError("Forgot password is supported only for parent and teacher")
        return value


class ForgotPasswordConfirmRequest(BaseModel):
    role: str
    username: str
    otp: str = Field(min_length=4, max_length=10)
    new_password: str = Field(min_length=6, max_length=100)

    @field_validator("role")
    @classmethod
    def validate_role(cls, value):
        value = value.strip().lower()
        allowed = {"parent", "teacher"}
        if value not in allowed:
            raise ValueError("Forgot password is supported only for parent and teacher")
        return value


class MessageResponse(BaseModel):
    ok: bool = True
    message: str


class ForgotPasswordRequestResponse(MessageResponse):
    otp_sent_to: str = ""
    otp_debug: str | None = None
