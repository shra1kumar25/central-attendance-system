import calendar
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Attendance, Employee
from app.services.email_service import send_attendance_report
from app.services.policy import calculate_weekly_compliance

router = APIRouter(prefix="/reports", tags=["Reports"])


def get_report_dates(
    period: str,
    report_date: date | None,
    start_date: date | None,
    end_date: date | None,
) -> tuple[date, date]:
    """Resolve the start and end dates for a report."""

    selected_date = report_date or date.today()

    if period == "daily":
        return selected_date, selected_date

    if period == "weekly":
        monday = selected_date - timedelta(days=selected_date.weekday())
        return monday, monday + timedelta(days=6)

    if period == "monthly":
        first_day = selected_date.replace(day=1)
        last_day_number = calendar.monthrange(selected_date.year, selected_date.month)[
            1
        ]
        last_day = selected_date.replace(day=last_day_number)
        return first_day, last_day

    if period == "yearly":
        return (
            date(selected_date.year, 1, 1),
            date(selected_date.year, 12, 31),
        )

    if period == "custom":
        if start_date is None or end_date is None:
            raise HTTPException(
                status_code=400,
                detail=("start_date and end_date are required for a custom report"),
            )

        if start_date > end_date:
            raise HTTPException(
                status_code=400,
                detail="start_date cannot be later than end_date",
            )

        return start_date, end_date

    raise HTTPException(
        status_code=400,
        detail="period must be daily, weekly, monthly, yearly, or custom",
    )


def format_attendance_time(value) -> str | None:
    """Format a timestamp for the report."""

    if value is None:
        return None

    return value.strftime("%B %d, %Y %-I:%M:%S %p")


@router.get("/attendance")
def unified_attendance_report(
    period: str = Query(
        ...,
        description="daily, weekly, monthly, yearly, or custom",
    ),
    report_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    employee_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
):
    """Return attendance records and compliance information."""

    period = period.lower()

    allowed_periods = {"daily", "weekly", "monthly", "yearly", "custom"}

    if period not in allowed_periods:
        raise HTTPException(
            status_code=400,
            detail=("period must be daily, weekly, monthly, yearly, or custom"),
        )

    period_start, period_end = get_report_dates(
        period=period,
        report_date=report_date,
        start_date=start_date,
        end_date=end_date,
    )

    employee_query = db.query(Employee).filter(Employee.is_active.is_(True))

    if employee_id is not None:
        employee_query = employee_query.filter(Employee.id == employee_id)

    employees = employee_query.order_by(Employee.id).all()

    if employee_id is not None and not employees:
        raise HTTPException(
            status_code=404,
            detail="Active employee not found",
        )

    report_employees = []

    for employee in employees:
        records = (
            db.query(Attendance)
            .filter(
                Attendance.employee_id == employee.id,
                Attendance.attendance_date >= period_start,
                Attendance.attendance_date <= period_end,
            )
            .order_by(Attendance.attendance_date)
            .all()
        )

        records_by_date = {record.attendance_date: record for record in records}

        daily_records = []
        total_hours = 0.0
        attended_dates = set()

        current_date = period_start

        while current_date <= period_end:
            record = records_by_date.get(current_date)

            if record is None:
                daily_records.append(
                    {
                        "date": current_date.isoformat(),
                        "entry_time": "Not attended office",
                        "exit_time": "Not attended office",
                        "hours_worked": 0.0,
                        "attendance_status": "NOT_ATTENDED",
                    }
                )
            else:
                hours_worked = 0.0

                if record.check_in is not None and record.check_out is not None:
                    seconds = (record.check_out - record.check_in).total_seconds()

                    if seconds > 0:
                        hours_worked = seconds / 3600
                        total_hours += hours_worked
                        attended_dates.add(current_date)

                daily_records.append(
                    {
                        "date": current_date.isoformat(),
                        "entry_time": (
                            format_attendance_time(record.check_in)
                            if record.check_in
                            else "Not attended office"
                        ),
                        "exit_time": (
                            format_attendance_time(record.check_out)
                            if record.check_out
                            else "Not attended office"
                        ),
                        "hours_worked": round(hours_worked, 2),
                        "attendance_status": (
                            record.status
                            if record.check_in is not None
                            else "NOT_ATTENDED"
                        ),
                    }
                )

            current_date += timedelta(days=1)

        total_hours = round(total_hours, 2)
        days_attended = len(attended_dates)

        average_hours_per_day = (
            round(total_hours / days_attended, 2) if days_attended else 0.0
        )

        # Calculate policy compliance only for a full calendar week.
        weekly_compliance = None

        if period == "weekly":
            weekly_compliance = calculate_weekly_compliance(
                attendance_records=records,
                period_start=period_start,
                period_end=period_end,
            )

        report_employees.append(
            {
                "employee_id": employee.id,
                "employee_code": employee.employee_code,
                "employee_name": employee.full_name,
                "email": employee.email,
                "period_start": period_start.isoformat(),
                "period_end": period_end.isoformat(),
                "days_attended": days_attended,
                "total_hours": total_hours,
                "average_hours_per_day": average_hours_per_day,
                "policy_status": (
                    weekly_compliance["policy_status"]
                    if weekly_compliance
                    else "NOT_EVALUATED"
                ),
                "daily_records": daily_records,
            }
        )

    return {
        "report_type": period,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "total_employees": len(report_employees),
        "employees": report_employees,
    }


@router.post("/attendance/email")
def email_attendance_report(
    employee_id: int = Query(..., gt=0),
    period: str = Query(
        ...,
        description="daily, weekly, monthly, yearly, or custom",
    ),
    report_date: date | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
    db: Session = Depends(get_db),
):
    # Generate the report for this employee.
    report = unified_attendance_report(
        period=period,
        report_date=report_date,
        start_date=start_date,
        end_date=end_date,
        employee_id=employee_id,
        db=db,
    )

    employee_report = report["employees"][0]

    # Send the report to the employee's registered email address.
    try:
        sent = send_attendance_report(
            employee_name=employee_report["employee_name"],
            employee_email=employee_report["email"],
            report=report,
        )
    except Exception:  # noqa: BLE001 — convert email failures to HTTP 502
        raise HTTPException(
            status_code=502,
            detail="Failed to send attendance report email",
        ) from None

    if not sent:
        raise HTTPException(
            status_code=502,
            detail="Attendance report email was not sent",
        )

    return {
        "message": "Attendance report emailed successfully",
        "employee_id": employee_report["employee_id"],
        "employee_name": employee_report["employee_name"],
        "recipient": employee_report["email"],
        "period_start": employee_report["period_start"],
        "period_end": employee_report["period_end"],
    }
