import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()

EMAIL_MODE = os.getenv("EMAIL_MODE", "console").lower()


def send_policy_warning(
    employee_name: str,
    employee_email: str,
    week_start: str,
    week_end: str,
    days_attended: int,
    total_hours: float,
) -> bool:
    subject = "Weekly Office Attendance Policy Warning"

    body = f"""Hello {employee_name},

Our attendance system has reviewed your office attendance
for the week {week_start} to {week_end}.

Your recorded attendance:
- Office days attended: {days_attended}
- Total hours worked: {total_hours}

Company policy requires:
- At least 3 office days per week
- At least 15 office hours per week
- An average of at least 5 hours per attended day

Your attendance did not meet the required policy.

Please contact your manager if you believe this record
is incorrect.

Regards,
HR / Attendance Management System
"""

    if EMAIL_MODE == "console":
        print("\n" + "=" * 60)
        print("DEVELOPMENT EMAIL PREVIEW")
        print("=" * 60)
        print(f"To: {employee_email}")
        print(f"Subject: {subject}")
        print(body)
        print("=" * 60 + "\n")
        return True

    if EMAIL_MODE == "smtp":
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        sender_email = os.getenv("SENDER_EMAIL", smtp_username)

        if not smtp_username or not smtp_password or not sender_email:
            raise RuntimeError(
                "SMTP_USERNAME, SMTP_PASSWORD, and SENDER_EMAIL "
                "must be configured in .env"
            )

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = sender_email
        message["To"] = employee_email
        message.set_content(body)

        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(message)

        return True

    raise RuntimeError(f"Unsupported EMAIL_MODE: {EMAIL_MODE}")


def send_attendance_report(
    employee_name: str,
    employee_email: str,
    report: dict,
) -> bool:
    """Email an employee their complete attendance report."""

    employee_report = report["employees"][0]

    subject = (
        f"Your Attendance Report: "
        f"{employee_report['period_start']} to "
        f"{employee_report['period_end']}"
    )

    daily_lines = []

    for record in employee_report["daily_records"]:
        daily_lines.append(
            f"Date: {record['date']}\n"
            f"Check-in: {record['entry_time']}\n"
            f"Check-out: {record['exit_time']}\n"
            f"Hours worked: {record['hours_worked']}\n"
            f"Status: {record['attendance_status']}\n"
        )

    daily_details = "\n".join(daily_lines)

    body = f"""Hello {employee_name},

Here is your attendance report.

Employee ID: {employee_report["employee_id"]}
Employee Code: {employee_report["employee_code"]}
Report Type: {report["report_type"]}
Period: {employee_report["period_start"]} to {employee_report["period_end"]}

ATTENDANCE SUMMARY
------------------
Office days attended: {employee_report["days_attended"]}
Total hours worked: {employee_report["total_hours"]}
Average hours per attended day: {employee_report["average_hours_per_day"]}
Policy status: {employee_report["policy_status"]}

DAILY ATTENDANCE DETAILS
-----------------------
{daily_details}

Regards,
HR / Attendance Management System
"""

    if EMAIL_MODE == "console":
        print("\n" + "=" * 60)
        print("ATTENDANCE REPORT EMAIL PREVIEW")
        print("=" * 60)
        print(f"To: {employee_email}")
        print(f"Subject: {subject}")
        print(body)
        print("=" * 60 + "\n")
        return True

    if EMAIL_MODE == "smtp":
        smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
        smtp_port = int(os.getenv("SMTP_PORT", "587"))
        smtp_username = os.getenv("SMTP_USERNAME")
        smtp_password = os.getenv("SMTP_PASSWORD")
        sender_email = os.getenv("SENDER_EMAIL", smtp_username)

        if not smtp_username or not smtp_password or not sender_email:
            raise RuntimeError(
                "SMTP_USERNAME, SMTP_PASSWORD, and SENDER_EMAIL "
                "must be configured in .env"
            )

        message = EmailMessage()
        message["Subject"] = subject
        message["From"] = sender_email
        message["To"] = employee_email
        message.set_content(body)

        with smtplib.SMTP(smtp_host, smtp_port, timeout=20) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(message)

        return True

    raise RuntimeError(f"Unsupported EMAIL_MODE: {EMAIL_MODE}")
