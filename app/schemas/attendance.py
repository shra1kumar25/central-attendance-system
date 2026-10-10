from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# Department schemas
class DepartmentCreate(BaseModel):
    name: str = Field(min_length=2, max_length=100)


class DepartmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str


# Employee schemas
class EmployeeCreate(BaseModel):
    employee_code: str = Field(min_length=2, max_length=20)
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    department_id: int = Field(gt=0)


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_code: str
    full_name: str
    email: EmailStr
    is_active: bool
    department_id: int


# Attendance schemas
class AttendanceCreate(BaseModel):
    employee_id: int = Field(gt=0)
    attendance_date: date = Field(default_factory=date.today)
    status: Literal["PRESENT", "ABSENT", "LEAVE"] = "PRESENT"


class AttendanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_id: int
    attendance_date: date
    check_in: datetime | None
    check_out: datetime | None
    status: str
