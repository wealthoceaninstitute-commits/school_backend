from pydantic import BaseModel


class NoticeOut(BaseModel):
    id: int
    title: str
    message: str

    model_config = {"from_attributes": True}
