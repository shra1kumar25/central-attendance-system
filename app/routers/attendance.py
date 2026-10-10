
import os
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    Attendance,
    Department,
    Employee,
    EmailNotification,
)
from app.schemas.attendance import (
    AttendanceCreate,
    AttendanceResponse,
    DepartmentCreate,
    DepartmentResponse,
    EmployeeCreate,
    EmployeeResponse,
)
from app.services.email_service import send_policy_warning
from app.services.policy import calculate_weekly_compliance


router = APIRouter()


# --------------------------------------------------
# DEPARTMENT APIs
# --------------------------------------------------

@router.post(
    "/departments",
    response_model=DepartmentResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_department(
    department_data: DepartmentCreate,
    db: Session = Depends(get_db),
):
    existing = (
        db.query(Department)
        .filter(Department.name == department_data.name)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Department already exists",
        )

    department = Department(name=department_data.name)
    db.add(department)
    db.commit()
    db.refresh(department)

    return department


@router.get(
    "/departments",
    response_model=list[DepartmentResponse],
)
def list_departments(db: Session = Depends(get_db)):
    return db.query(Department).order_by(Department.id).all()


# --------------------------------------------------
# EMPLOYEE APIs
# --------------------------------------------------

@router.post(
    "/employees",
    response_model=EmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_employee(
    employee_data: EmployeeCreate,
    db: Session = Depends(get_db),
):
    existing = (
        db.query(Employee)
        .filter(
            (Employee.employee_code == employee_data.employee_code)
            | (Employee.email == employee_data.email)
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Employee code or email already exists",
        )

    department = (
        db.query(Department)
        .filter(Department.id == employee_data.department_id)
        .first()
    )

    if not department:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Department not found",
        )

    employee = Employee(**employee_data.model_dump())
    db.add(employee)
    db.commit()
    db.refresh(employee)

    return employee


@router.get(
    "/employees",
    response_model=list[EmployeeResponse],
)
def list_employees(db: Session = Depends(get_db)):
    return db.query(Employee).order_by(Employee.id).all()


# --------------------------------------------------
# ATTENDANCE CREATION AND LISTING
# --------------------------------------------------

@router.post(
    "/attendance",
    response_model=AttendanceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_attendance(
    attendance_data: AttendanceCreate,
    db: Session = Depends(get_db),
):
    employee = (
        db.query(Employee)
        .filter(Employee.id == attendance_data.employee_id)
        .first()
    )

    if not employee:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Employee not found",
        )

    if not employee.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot record attendance for an inactive employee",
        )

    existing = (
        db.query(Attendance)
        .filter(
            Attendance.employee_id == attendance_data.employee_id,
            Attendance.attendance_date == attendance_data.attendance_date,
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Attendance already recorded for this employee and date",
        )

    attendance = Attendance(**attendance_data.model_dump())
    db.add(attendance)
    db.commit()
    db.refresh(attendance)

    return attendance


@router.get(
    "/attendance",
    response_model=list[AttendanceResponse],
)
def list_attendance(
    employee_id: int | None = None,
    attendance_date: date | None = None,
    status_filter: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    if employee_id is not None and employee_id < 1:
        raise HTTPException(
            status_code=400,
            detail="Employee ID must be greater than zero",
        )

    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 100",
        )

    if offset < 0:
        raise HTTPException(
            status_code=400,
            detail="Offset cannot be negative",
        )

    allowed_statuses = {"PRESENT", "ABSENT", "LEAVE"}

    if status_filter is not None:
        status_filter = status_filter.upper()
        if status_filter not in allowed_statuses:
            raise HTTPException(
                status_code=400,
                detail="Status must be PRESENT, ABSENT, or LEAVE",
            )

    query = db.query(Attendance)

    if employee_id is not None:
        query = query.filter(Attendance.employee_id == employee_id)

    if attendance_date is not None:
        query = query.filter(
            Attendance.attendance_date == attendance_date
        )

    if status_filter is not None:
        query = query.filter(Attendance.status == status_filter)

    return (
        query.order_by(
            Attendance.attendance_date.desc(),
            Attendance.id.desc(),
        )
        .offset(offset)
        .limit(limit)
        .all()
    )


# --------------------------------------------------
# EMPLOYEE CHECK-IN
# --------------------------------------------------

@router.post(
    "/attendance/{employee_id}/check-in",
    response_model=AttendanceResponse,
)
def check_in(
    employee_id: int,
    db: Session = Depends(get_db),
):
    if employee_id < 1:
        raise HTTPException(
            status_code=400,
            detail="Employee ID must be greater than zero",
        )

    employee = (
        db.query(Employee)
        .filter(
            Employee.id == employee_id,
            Employee.is_active.is_(True),
        )
        .first()
    )

    if not employee:
        raise HTTPException(
            status_code=404,
            detail="Active employee not found",
        )

    today = date.today()

    attendance = (
        db.query(Attendance)
        .filter(
            Attendance.employee_id == employee_id,
            Attendance.attendance_date == today,
        )
        .first()
    )

    if attendance and attendance.check_in is not None:
        raise HTTPException(
            status_code=409,
            detail="Employee has already checked in today",
        )

    now = datetime.now(timezone.utc)

    if attendance is None:
        attendance = Attendance(
            employee_id=employee_id,
            attendance_date=today,
            check_in=now,
            status="PRESENT",
        )
        db.add(attendance)
    else:
        if attendance.status in {"ABSENT", "LEAVE"}:
            raise HTTPException(
                status_code=400,
                detail=(
                    "Cannot check in when attendance is marked absent "
                    "or on leave"
                ),
            )

        attendance.check_in = now
        attendance.status = "PRESENT"

    db.commit()
    db.refresh(attendance)

    return attendance


# --------------------------------------------------
# EMPLOYEE CHECK-OUT
# --------------------------------------------------

@router.post(
    "/attendance/{employee_id}/check-out",
    response_model=AttendanceResponse,
)
def check_out(
    employee_id: int,
    db: Session = Depends(get_db),
):
    if employee_id < 1:
        raise HTTPException(
            status_code=400,
            detail="Employee ID must be greater than zero",
        )

    employee = (
        db.query(Employee)
        .filter(
            Employee.id == employee_id,
            Employee.is_active.is_(True),
        )
        .first()
    )

    if not employee:
        raise HTTPException(
            status_code=404,
            detail="Active employee not found",
        )

    today = date.today()

    attendance = (
        db.query(Attendance)
        .filter(
            Attendance.employee_id == employee_id,
            Attendance.attendance_date == today,
        )
        .first()
    )

    if attendance is None or attendance.check_in is None:
        raise HTTPException(
            status_code=400,
            detail="Employee must check in before checking out",
        )

    if attendance.check_out is not None:
        raise HTTPException(
            status_code=409,
            detail="Employee has already checked out today",
        )

    now = datetime.now(timezone.utc)

    if now < attendance.check_in:
        raise HTTPException(
            status_code=400,
            detail="Check-out time cannot be earlier than check-in time",
        )

    attendance.check_out = now
    db.commit()
    db.refresh(attendance)

    return attendance


# --------------------------------------------------
# INDIVIDUAL EMPLOYEE ATTENDANCE SUMMARY
# --------------------------------------------------

@router.get("/attendance/summary")
def attendance_summary(
    employee_id: int,
    db: Session = Depends(get_db),
):
    if employee_id < 1:
        raise HTTPException(
            status_code=400,
            detail="Employee ID must be greater than zero",
        )

    employee = (
        db.query(Employee)
        .filter(Employee.id == employee_id)
        .first()
    )

    if not employee:
        raise HTTPException(
            status_code=404,
            detail="Employee not found",
        )

    records = (
        db.query(Attendance)
        .filter(Attendance.employee_id == employee_id)
        .all()
    )

    return {
        "employee_id": employee.id,
        "employee_code": employee.employee_code,
        "employee_name": employee.full_name,
        "total_recorded_days": len(records),
        "present_days": sum(
            1 for record in records if record.status == "PRESENT"
        ),
        "absent_days": sum(
            1 for record in records if record.status == "ABSENT"
        ),
        "leave_days": sum(
            1 for record in records if record.status == "LEAVE"
        ),
    }


# --------------------------------------------------
# DATE-RANGE ATTENDANCE REPORT
# --------------------------------------------------

@router.get("/attendance/report")
def attendance_report(
    start_date: date,
    end_date: date,
    employee_id: int | None = None,
    db: Session = Depends(get_db),
):
    if start_date > end_date:
        raise HTTPException(
            status_code=400,
            detail="start_date cannot be later than end_date",
        )

    if employee_id is not None and employee_id < 1:
        raise HTTPException(
            status_code=400,
            detail="Employee ID must be greater than zero",
        )

    if employee_id is not None:
        employee = (
            db.query(Employee)
            .filter(Employee.id == employee_id)
            .first()
        )
        if not employee:
            raise HTTPException(
                status_code=404,
                detail="Employee not found",
            )

    query = db.query(Attendance).filter(
        Attendance.attendance_date >= start_date,
        Attendance.attendance_date <= end_date,
    )

    if employee_id is not None:
        query = query.filter(Attendance.employee_id == employee_id)

    records = (
        query.order_by(
            Attendance.attendance_date,
            Attendance.employee_id,
        )
        .all()
    )

    return {
        "start_date": start_date,
        "end_date": end_date,
        "employee_id": employee_id,
        "total_recorded_days": len(records),
        "present_days": sum(
            1 for record in records if record.status == "PRESENT"
        ),
        "absent_days": sum(
            1 for record in records if record.status == "ABSENT"
        ),
        "leave_days": sum(
            1 for record in records if record.status == "LEAVE"
        ),
        "records": [
            {
                "attendance_id": record.id,
                "employee_id": record.employee_id,
                "attendance_date": record.attendance_date,
                "check_in": record.check_in,
                "check_out": record.check_out,
                "status": record.status,
            }
            for record in records
        ],
    }


# --------------------------------------------------
# WEEKLY COMPLIANCE REPORT FOR ALL ACTIVE EMPLOYEES
# --------------------------------------------------

@router.get("/attendance/weekly-compliance")
def weekly_compliance(
    week_start: date | None = None,
    db: Session = Depends(get_db),
):
    today = date.today()
    start_date = week_start or (
        today - timedelta(days=today.weekday())
    )
    end_date = start_date + timedelta(days=6)

    employees = (
        db.query(Employee)
        .filter(Employee.is_active.is_(True))
        .order_by(Employee.id)
        .all()
    )

    results = []

    for employee in employees:
        records = (
            db.query(Attendance)
            .filter(
                Attendance.employee_id == employee.id,
                Attendance.attendance_date >= start_date,
                Attendance.attendance_date <= end_date,
            )
            .all()
        )

        compliance = calculate_weekly_compliance(
            attendance_records=records,
            period_start=start_date,
            period_end=end_date,
        )

        results.append({
            "employee_id": employee.id,
            "employee_code": employee.employee_code,
            "employee_name": employee.full_name,
            "email": employee.email,
            **compliance,
        })

    return {
        "report_type": "weekly_compliance",
        "week_start": start_date.isoformat(),
        "week_end": end_date.isoformat(),
        "total_employees": len(results),
        "compliant_employees": sum(
            1 for item in results
            if item["policy_status"] == "COMPLIANT"
        ),
        "non_compliant_employees": sum(
            1 for item in results
            if item["policy_status"] == "NON_COMPLIANT"
        ),
        "pending_employees": sum(
            1 for item in results
            if item["policy_status"] == "PENDING"
        ),
        "employees": results,
    }


# --------------------------------------------------
# WEEKLY POLICY NOTIFICATIONS WITH HISTORY
# --------------------------------------------------

@router.post("/attendance/weekly-policy-notifications")
def send_weekly_policy_notifications(
    week_start: date | None = None,
    db: Session = Depends(get_db),
):
    today = date.today()
    start_date = week_start or (
        today - timedelta(days=today.weekday())
    )
    end_date = start_date + timedelta(days=6)

    if end_date >= today:
        raise HTTPException(
            status_code=400,
            detail=(
                "The selected week has not fully ended. "
                "Warnings can only be evaluated for completed weeks."
            ),
        )

    employees = (
        db.query(Employee)
        .filter(Employee.is_active.is_(True))
        .order_by(Employee.id)
        .all()
    )

    results = []

    for employee in employees:
        records = (
            db.query(Attendance)
            .filter(
                Attendance.employee_id == employee.id,
                Attendance.attendance_date >= start_date,
                Attendance.attendance_date <= end_date,
            )
            .all()
        )

        compliance = calculate_weekly_compliance(
            attendance_records=records,
            period_start=start_date,
            period_end=end_date,
        )

        if compliance["policy_status"] != "NON_COMPLIANT":
            results.append({
                "employee_id": employee.id,
                "employee_name": employee.full_name,
                "policy_status": compliance["policy_status"],
                "notification": "SKIPPED",
                "reason": "Employee is not non-compliant",
            })
            continue

        notification = (
            db.query(EmailNotification)
            .filter(
                EmailNotification.employee_id == employee.id,
                EmailNotification.period_start == start_date,
                EmailNotification.period_end == end_date,
            )
            .first()
        )

        if notification and notification.status in {"PREVIEWED", "SENT"}:
            results.append({
                "employee_id": employee.id,
                "employee_name": employee.full_name,
                "policy_status": compliance["policy_status"],
                "notification": "SKIPPED_DUPLICATE",
                "reason": "A notification is already recorded for this week",
            })
            continue

        if notification is None:
            notification = EmailNotification(
                employee_id=employee.id,
                period_start=start_date,
                period_end=end_date,
                status="PENDING",
            )
            db.add(notification)

            try:
                db.commit()
                db.refresh(notification)
            except IntegrityError:
                db.rollback()
                results.append({
                    "employee_id": employee.id,
                    "employee_name": employee.full_name,
                    "policy_status": compliance["policy_status"],
                    "notification": "SKIPPED_DUPLICATE",
                    "reason": "A notification record already exists",
                })
                continue
        else:
            notification.status = "PENDING"
            db.commit()

        try:
            send_policy_warning(
                employee_name=employee.full_name,
                employee_email=employee.email,
                week_start=start_date.isoformat(),
                week_end=end_date.isoformat(),
                days_attended=compliance["days_attended"],
                total_hours=compliance["total_hours"],
            )

            email_mode = os.getenv("EMAIL_MODE", "console").lower()

            if email_mode == "smtp":
                notification.status = "SENT"
                notification.sent_at = datetime.now(timezone.utc)
            else:
                notification.status = "PREVIEWED"
                notification.sent_at = None

            db.commit()

            results.append({
                "employee_id": employee.id,
                "employee_name": employee.full_name,
                "policy_status": compliance["policy_status"],
                "notification": notification.status,
            })

        except Exception:
            db.rollback()

            saved_notification = (
                db.query(EmailNotification)
                .filter(
                    EmailNotification.employee_id == employee.id,
                    EmailNotification.period_start == start_date,
                    EmailNotification.period_end == end_date,
                )
                .first()
            )

            if saved_notification is not None:
                saved_notification.status = "FAILED"
                db.commit()

            results.append({
                "employee_id": employee.id,
                "employee_name": employee.full_name,
                "policy_status": compliance["policy_status"],
                "notification": "FAILED",
                "reason": "Notification preview failed",
            })

    return {
        "report_type": "weekly_policy_notifications",
        "week_start": start_date.isoformat(),
        "week_end": end_date.isoformat(),
        "total_employees": len(results),
        "notifications_previewed": sum(
            1 for item in results
            if item["notification"] == "PREVIEWED"
        ),
        "notifications_skipped": sum(
            1 for item in results
            if item["notification"] in {"SKIPPED", "SKIPPED_DUPLICATE"}
        ),
        "notifications_failed": sum(
            1 for item in results
            if item["notification"] == "FAILED"
        ),
        "employees": results,
    }
