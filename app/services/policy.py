
from datetime import date

from app.models import Attendance


MINIMUM_DAYS_PER_WEEK = 3
MINIMUM_HOURS_PER_WEEK = 15
MINIMUM_AVERAGE_HOURS_PER_DAY = 5


def calculate_weekly_compliance(
    attendance_records: list[Attendance],
    period_start: date,
    period_end: date,
) -> dict:
    """
    Calculate weekly attendance policy compliance.

    Policy requirements:
    1. Attend the office at least 3 days per week.
    2. Complete at least 15 hours per week.
    3. Average at least 5 hours per attended day.

    Only completed check-in/check-out sessions count
    toward attended days and working hours.

    An unfinished week remains PENDING if the employee
    has not yet met all requirements.
    """

    total_hours = 0.0
    attended_dates = set()
    incomplete_dates = []

    for record in attendance_records:
        if not (period_start <= record.attendance_date <= period_end):
            continue

        # Incomplete sessions do not count toward
        # completed attendance days or working hours.
        if record.check_in is None or record.check_out is None:
            incomplete_dates.append(
                record.attendance_date.isoformat()
            )
            continue

        # Calculate the duration without rounding.
        duration_seconds = (
            record.check_out - record.check_in
        ).total_seconds()

        # Ignore zero-duration or invalid sessions.
        if duration_seconds <= 0:
            continue

        total_hours += duration_seconds / 3600
        attended_dates.add(record.attendance_date)

    days_attended = len(attended_dates)

    # Calculate the average using unrounded total hours.
    average_hours_per_day = (
        total_hours / days_attended
        if days_attended > 0
        else 0.0
    )

    # Evaluate policy requirements before rounding.
    days_requirement_met = (
        days_attended >= MINIMUM_DAYS_PER_WEEK
    )

    hours_requirement_met = (
        total_hours >= MINIMUM_HOURS_PER_WEEK
    )

    average_requirement_met = (
        average_hours_per_day
        >= MINIMUM_AVERAGE_HOURS_PER_DAY
    )

    compliant = (
        days_requirement_met
        and hours_requirement_met
        and average_requirement_met
    )

    # Do not declare a violation while the reporting
    # period is still in progress.
    if compliant:
        policy_status = "COMPLIANT"
    elif period_end > date.today():
        policy_status = "PENDING"
    else:
        policy_status = "NON_COMPLIANT"

    return {
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "days_attended": days_attended,
        "total_hours": round(total_hours, 2),
        "average_hours_per_day": round(
            average_hours_per_day, 2
        ),
        "minimum_days_required": MINIMUM_DAYS_PER_WEEK,
        "minimum_hours_required": MINIMUM_HOURS_PER_WEEK,
        "minimum_average_hours_per_day": (
            MINIMUM_AVERAGE_HOURS_PER_DAY
        ),
        "days_requirement_met": days_requirement_met,
        "hours_requirement_met": hours_requirement_met,
        "average_requirement_met": average_requirement_met,
        "compliant": compliant,
        "policy_status": policy_status,
        "incomplete_attendance_dates": incomplete_dates,
    }
