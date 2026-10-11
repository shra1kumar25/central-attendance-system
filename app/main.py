from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# Allow the React frontend to communicate with the FastAPI backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routers.
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
