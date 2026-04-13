import json
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.base import Base
from app.db.session import engine
from app.db.seed import seed_demo_data
from app.models import *  # noqa: F401,F403
from app.api.routes import auth, health, mobile, notices, parent, school_admin, student, teacher


def get_cors_origins():
    fallback = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://school-frontend-b3ox.vercel.app",
        "https://school-frontend-cgqj.vercel.app",
    ]

    raw_env = os.getenv("CORS_ORIGINS")
    if raw_env:
        try:
            parsed = json.loads(raw_env)
            if isinstance(parsed, list):
                cleaned = [str(x).strip().rstrip("/") for x in parsed if str(x).strip()]
                if cleaned:
                    return cleaned
        except Exception:
            pass

    cfg_origins = getattr(settings, "cors_origins", None)

    if isinstance(cfg_origins, list) and cfg_origins:
        cleaned = [str(x).strip().rstrip("/") for x in cfg_origins if str(x).strip()]
        if cleaned:
            return cleaned

    return fallback


Base.metadata.create_all(bind=engine)
seed_demo_data()

app = FastAPI(title=settings.app_name, version="1.0.0")

cors_origins = get_cors_origins()
print("CORS origins loaded:", cors_origins)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["health"])
app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(parent.router, prefix="/parent", tags=["parent"])
app.include_router(student.router, prefix="/student", tags=["student"])
app.include_router(teacher.router, prefix="/teacher", tags=["teacher"])
app.include_router(notices.router, prefix="/notices", tags=["notices"])
app.include_router(mobile.router)

# Admin/master-data routes used by frontend pages like:
# /admin/classes, /admin/students, /admin/teachers, /admin/settings/subjects, etc.
app.include_router(school_admin.router, prefix="/admin", tags=["school-admin"])


@app.get("/")
def root():
    return {"status": "ok", "service": "school-backend"}


@app.get("/ping")
def ping():
    return {"message": "pong"}
