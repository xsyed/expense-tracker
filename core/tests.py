"""
Phase 1 acceptance criteria tests.
Covers all 10 AC items from phases/phase-1-foundation-auth.md
"""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase

from core.models import DEFAULT_CATEGORIES
from core.recurring_utils import detect_recurring

User = get_user_model()


class AuthRedirectTests(TestCase):
    """AC 1: Unauthenticated user on / redirects to /auth/login/"""

    def test_root_redirects_unauthenticated_to_login(self):
        response = self.client.get("/")
        self.assertRedirects(response, "/auth/login/?next=/", fetch_redirect_response=False)


class SignUpTests(TestCase):
    """AC 2-4: Sign-up flow"""

    def test_valid_signup_creates_user_and_logs_in(self):
        """AC 2"""
        response = self.client.post(
            "/auth/signup/",
            {
                "email": "test@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertTrue(User.objects.filter(email="test@example.com").exists())
        # user is now logged in — home returns 200
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)

    def test_duplicate_email_shows_error(self):
        """AC 3"""
        User.objects.create_user(email="existing@example.com", password="StrongPass123!")
        response = self.client.post(
            "/auth/signup/",
            {
                "email": "existing@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "already exists")
        self.assertEqual(User.objects.filter(email="existing@example.com").count(), 1)

    def test_mismatched_passwords_shows_error(self):
        """AC 4"""
        response = self.client.post(
            "/auth/signup/",
            {
                "email": "new@example.com",
                "password1": "StrongPass123!",
                "password2": "WrongPass456!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "do not match")
        self.assertFalse(User.objects.filter(email="new@example.com").exists())


class LoginTests(TestCase):
    """AC 5-6: Login flow"""

    def setUp(self):
        self.user = User.objects.create_user(email="user@example.com", password="CorrectPass123!")

    def test_valid_login_redirects_to_home(self):
        """AC 5"""
        response = self.client.post(
            "/auth/login/",
            {
                "email": "user@example.com",
                "password": "CorrectPass123!",
            },
        )
        self.assertRedirects(response, "/", fetch_redirect_response=False)

    def test_login_does_not_duplicate_default_categories(self):
        response = self.client.post(
            "/auth/login/",
            {
                "email": "user@example.com",
                "password": "CorrectPass123!",
            },
        )

        self.assertRedirects(response, "/", fetch_redirect_response=False)
        self.assertEqual(self.user.categories.count(), len(DEFAULT_CATEGORIES))

    def test_wrong_password_shows_generic_error(self):
        """AC 6"""
        response = self.client.post(
            "/auth/login/",
            {
                "email": "user@example.com",
                "password": "WrongPassword!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password")

    def test_unknown_email_shows_generic_error(self):
        """AC 6 — unknown email must not reveal which field is wrong"""
        response = self.client.post(
            "/auth/login/",
            {
                "email": "nobody@example.com",
                "password": "SomePass123!",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password")


class LogoutTests(TestCase):
    """AC 7-8: Logout flow"""

    def setUp(self):
        self.user = User.objects.create_user(email="user@example.com", password="Pass123!")
        self.client.login(username="user@example.com", password="Pass123!")

    def test_post_logout_redirects_to_login(self):
        """AC 7"""
        response = self.client.post("/auth/logout/")
        self.assertRedirects(response, "/auth/login/", fetch_redirect_response=False)

    def test_after_logout_protected_url_redirects_to_login(self):
        """AC 8"""
        self.client.post("/auth/logout/")
        response = self.client.get("/")
        self.assertRedirects(response, "/auth/login/?next=/", fetch_redirect_response=False)


class TemplateRenderTests(TestCase):
    """AC 9-10: Navbar and flash messages"""

    def test_signup_page_has_bootstrap(self):
        """AC 9 — signup renders auth card with Bootstrap"""
        response = self.client.get("/auth/signup/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bootstrap")

    def test_login_page_has_bootstrap(self):
        """AC 9 — login renders with Bootstrap"""
        response = self.client.get("/auth/login/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "bootstrap")

    def test_home_page_contains_navbar_after_login(self):
        """AC 9 — navbar with Home / Categories / Logout after login"""
        User.objects.create_user(email="u@x.com", password="Pass!1234")
        self.client.login(username="u@x.com", password="Pass!1234")
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Expense Tracker")
        self.assertContains(response, "Categories")
        self.assertContains(response, "Logout")

    def test_flash_message_shown_after_signup(self):
        """AC 10 — success flash shown after account creation"""
        response = self.client.post(
            "/auth/signup/",
            {
                "email": "flash@example.com",
                "password1": "StrongPass123!",
                "password2": "StrongPass123!",
            },
            follow=True,
        )
        self.assertContains(response, "Account created successfully")

    def test_flash_message_shown_after_logout(self):
        """AC 10 — flash shown after logout"""
        User.objects.create_user(email="u2@x.com", password="Pass!1234")
        self.client.login(username="u2@x.com", password="Pass!1234")
        response = self.client.post("/auth/logout/", follow=True)
        self.assertContains(response, "logged out")


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

    def test_daily_dropped(self) -> None:
        dates = [_BASE_DATE + datetime.timedelta(days=i) for i in range(7)]
        results = detect_recurring(_txns("Coffee Shop", "5.00", dates))
        self.assertEqual(results, [])

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
        # 4 steady payments at $50 + 1 outlier at $200; outlier filtered, monthly still detected
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
