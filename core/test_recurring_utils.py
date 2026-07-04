from __future__ import annotations

import datetime
from decimal import Decimal

from django.test import TestCase

from core.recurring_utils import detect_recurring

_BASE_DATE = datetime.date(2025, 1, 1)


def _txns(desc: str, amount: str, dates: list[datetime.date]) -> list[tuple[str, Decimal, datetime.date]]:
    return [(desc, Decimal(amount), d) for d in dates]


class RecurringDetectionTests(TestCase):
    def test_weekly_detected(self) -> None:
        dates = [_BASE_DATE + datetime.timedelta(weeks=i) for i in range(6)]
        results = detect_recurring(_txns("Netflix Subscription", "15.99", dates))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["frequency"], "weekly")
        self.assertAlmostEqual(float(str(results[0]["annual_estimate"])), 15.99 * 52, places=1)

    def test_monthly_detected(self) -> None:
        dates = [_BASE_DATE.replace(month=m) for m in range(1, 5)]
        results = detect_recurring(_txns("Gym Membership", "50.00", dates))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["frequency"], "monthly")
        self.assertAlmostEqual(float(str(results[0]["annual_estimate"])), 50.0 * 12, places=1)

    def test_quarterly_detected(self) -> None:
        dates = [
            _BASE_DATE,
            _BASE_DATE + datetime.timedelta(days=90),
            _BASE_DATE + datetime.timedelta(days=180),
        ]
        results = detect_recurring(_txns("Insurance Payment", "200.00", dates))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["frequency"], "quarterly")
        self.assertAlmostEqual(float(str(results[0]["annual_estimate"])), 200.0 * 4, places=1)

    def test_daily_detected(self) -> None:
        dates = [_BASE_DATE + datetime.timedelta(days=i) for i in range(7)]
        results = detect_recurring(_txns("Coffee Shop", "5.00", dates))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["frequency"], "daily")

    def test_weekly_stale_when_last_seen_more_than_30_days_ago(self) -> None:
        dates = [_BASE_DATE + datetime.timedelta(weeks=i) for i in range(6)]
        results = detect_recurring(
            _txns("Streaming Service", "15.99", dates),
            as_of=dates[-1] + datetime.timedelta(days=31),
        )
        self.assertEqual(results, [])

    def test_weekly_fresh_when_last_seen_within_30_days(self) -> None:
        dates = [_BASE_DATE + datetime.timedelta(weeks=i) for i in range(6)]
        results = detect_recurring(
            _txns("Streaming Service", "15.99", dates),
            as_of=dates[-1] + datetime.timedelta(days=30),
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["frequency"], "weekly")

    def test_monthly_stale_when_last_seen_more_than_60_days_ago(self) -> None:
        dates = [_BASE_DATE.replace(month=m) for m in range(1, 5)]
        results = detect_recurring(
            _txns("Gym Membership", "50.00", dates),
            as_of=dates[-1] + datetime.timedelta(days=61),
        )
        self.assertEqual(results, [])

    def test_daily_stale_when_last_seen_more_than_14_days_ago(self) -> None:
        dates = [_BASE_DATE + datetime.timedelta(days=i) for i in range(7)]
        results = detect_recurring(
            _txns("Coffee Shop", "5.00", dates),
            as_of=dates[-1] + datetime.timedelta(days=15),
        )
        self.assertEqual(results, [])

    def test_quarterly_freshness_uses_120_day_window(self) -> None:
        dates = [_BASE_DATE + datetime.timedelta(days=90 * i) for i in range(3)]
        fresh_results = detect_recurring(
            _txns("Insurance Payment", "200.00", dates),
            as_of=dates[-1] + datetime.timedelta(days=120),
        )
        stale_results = detect_recurring(
            _txns("Insurance Payment", "200.00", dates),
            as_of=dates[-1] + datetime.timedelta(days=121),
        )
        self.assertEqual(len(fresh_results), 1)
        self.assertEqual(fresh_results[0]["frequency"], "quarterly")
        self.assertEqual(stale_results, [])

    def test_other_freshness_uses_twice_median_gap(self) -> None:
        dates = [_BASE_DATE + datetime.timedelta(days=14 * i) for i in range(5)]
        fresh_results = detect_recurring(
            _txns("Biweekly Service", "100.00", dates),
            as_of=dates[-1] + datetime.timedelta(days=28),
        )
        stale_results = detect_recurring(
            _txns("Biweekly Service", "100.00", dates),
            as_of=dates[-1] + datetime.timedelta(days=29),
        )
        self.assertEqual(len(fresh_results), 1)
        self.assertEqual(fresh_results[0]["frequency"], "other")
        self.assertEqual(stale_results, [])

    def test_biweekly_classified_as_other(self) -> None:
        dates = [_BASE_DATE + datetime.timedelta(days=14 * i) for i in range(5)]
        results = detect_recurring(_txns("Biweekly Service", "100.00", dates))
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["frequency"], "other")

    def test_below_min_occurrences_dropped(self) -> None:
        dates = [_BASE_DATE, _BASE_DATE + datetime.timedelta(days=30)]
        results = detect_recurring(_txns("Magazine Sub", "10.00", dates))
        self.assertEqual(results, [])

    def test_amount_filtering_excludes_outlier(self) -> None:
        dates = [_BASE_DATE + datetime.timedelta(days=30 * i) for i in range(5)]
        txns: list[tuple[str, Decimal, datetime.date]] = [
            ("Store Charge", Decimal("50.00"), dates[0]),
            ("Store Charge", Decimal("50.00"), dates[1]),
            ("Store Charge", Decimal("50.00"), dates[2]),
            ("Store Charge", Decimal("50.00"), dates[3]),
            ("Store Charge", Decimal("200.00"), dates[4]),
        ]
        results = detect_recurring(txns)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["frequency"], "monthly")
