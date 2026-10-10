from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.db.session import Base, engine
from app.models import (  # noqa: F401
    Attendance,
    Department,
    EmailNotification,
    Employee,
)
from app.routers.attendance import router as attendance_router
from app.routers.reports import router as reports_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Central Attendance Management System",
    description="Backend APIs for employee attendance, reporting, and policy compliance.",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(attendance_router)
app.include_router(reports_router)


@app.get("/")
def home():
    return {
        "message": "Central Attendance Management System API is running",
        "status": "success",
    }


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "attendance-management-api",
    }
