from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
def health_check():
    return {"ok": True, "message": "Smart School API running"}
