from datetime import date

from app.routers.reports import get_report_dates


def test_daily_report_dates():
    start_date, end_date = get_report_dates(
        period="daily",
        report_date=date(2026, 10, 10),
        start_date=None,
        end_date=None,
    )

    assert start_date == date(2026, 10, 10)
    assert end_date == date(2026, 10, 10)


def test_weekly_report_dates():
    start_date, end_date = get_report_dates(
        period="weekly",
        report_date=date(2026, 10, 10),
        start_date=None,
        end_date=None,
    )

    assert start_date == date(2026, 10, 5)
    assert end_date == date(2026, 10, 11)
