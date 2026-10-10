
from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.session import Base, get_db
from app.main import app
from app.models import Attendance, Department, Employee


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    Base.metadata.create_all(bind=engine)

    TestingSessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
    )

    db = TestingSessionLocal()

    try:
        department = Department(name="Test Department")
        db.add(department)
        db.flush()

        employee = Employee(
            employee_code="TEST001",
            full_name="Test Employee",
            email="attendance-test@example.com",
            is_active=True,
            department_id=department.id,
        )
        db.add(employee)
        db.flush()

        db.add(
            Attendance(
                employee_id=employee.id,
                attendance_date=date(2026, 10, 10),
                check_in=datetime(2026, 10, 10, 9, 0),
                check_out=datetime(2026, 10, 10, 17, 0),
                status="PRESENT",
            )
        )
        db.commit()

        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_email_attendance_report(
    test_db,
    monkeypatch,
):
    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    email_calls = []

    def fake_send_attendance_report(
        employee_name,
        employee_email,
        report,
    ):
        email_calls.append(
            {
                "employee_name": employee_name,
                "employee_email": employee_email,
                "report": report,
            }
        )
        return True

    monkeypatch.setattr(
        "app.routers.reports.send_attendance_report",
        fake_send_attendance_report,
    )

    try:
        # Do not use a TestClient context manager here:
        # that would run the application's normal database
        # startup lifecycle.
        client = TestClient(app)

        response = client.post(
            "/reports/attendance/email",
            params={
                "employee_id": 1,
                "period": "weekly",
                "report_date": "2026-10-10",
            },
        )

        assert response.status_code == 200

        body = response.json()
        assert body["message"] == (
            "Attendance report emailed successfully"
        )
        assert body["employee_id"] == 1
        assert body["recipient"] == (
            "attendance-test@example.com"
        )
        assert body["period_start"] == "2026-10-05"
        assert body["period_end"] == "2026-10-11"

        assert len(email_calls) == 1

        email = email_calls[0]
        assert email["employee_name"] == "Test Employee"
        assert email["employee_email"] == (
            "attendance-test@example.com"
        )

        report_employee = email["report"]["employees"][0]
        assert report_employee["days_attended"] == 1
        assert report_employee["total_hours"] == 8.0

    finally:
        app.dependency_overrides.pop(get_db, None)

def test_email_report_employee_not_found(
    test_db,
    monkeypatch,
):
    def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db

    def unexpected_email_call(*args, **kwargs):
        pytest.fail("Email must not be sent for a missing employee")

    monkeypatch.setattr(
        "app.routers.reports.send_attendance_report",
        unexpected_email_call,
    )

    try:
        client = TestClient(app)

        response = client.post(
            "/reports/attendance/email",
            params={
                "employee_id": 999,
                "period": "weekly",
                "report_date": "2026-10-10",
            },
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Active employee not found"

    finally:
        app.dependency_overrides.pop(get_db, None)
