from datetime import date

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.db.session import Base


class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)

    employees = relationship(
        "Employee",
        back_populates="department",
    )


class Employee(Base):
    __tablename__ = "employees"

    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String(20), unique=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    email = Column(String(150), unique=True, index=True, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    department_id = Column(
        Integer,
        ForeignKey("departments.id"),
        nullable=False,
    )

    department = relationship(
        "Department",
        back_populates="employees",
    )

    attendances = relationship(
        "Attendance",
        back_populates="employee",
    )


class Attendance(Base):
    __tablename__ = "attendances"

    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "attendance_date",
            name="uq_employee_attendance_date",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    employee_id = Column(
        Integer,
        ForeignKey("employees.id"),
        nullable=False,
    )

    attendance_date = Column(
        Date,
        default=date.today,
        nullable=False,
    )

    check_in = Column(DateTime(timezone=True), nullable=True)
    check_out = Column(DateTime(timezone=True), nullable=True)

    status = Column(
        String(20),
        default="PRESENT",
        nullable=False,
    )

    employee = relationship(
        "Employee",
        back_populates="attendances",
    )


class EmailNotification(Base):
    __tablename__ = "email_notifications"

    __table_args__ = (
        UniqueConstraint(
            "employee_id",
            "period_start",
            "period_end",
            name="uq_email_notification_employee_period",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)

    employee_id = Column(
        Integer,
        ForeignKey("employees.id"),
        nullable=False,
    )

    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    status = Column(
        String(20),
        default="PENDING",
        nullable=False,
    )

    sent_at = Column(DateTime(timezone=True), nullable=True)
