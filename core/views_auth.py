from __future__ import annotations

from axes.helpers import get_client_ip_address
from axes.models import AccessAttempt
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.forms.utils import ErrorDict
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from two_factor.views import LoginView, SetupView

from .forms import SignUpForm
from .models import ExpenseMonth
from .turnstile import verify_turnstile


class CustomSetupView(SetupView):  # type: ignore[misc]
    success_url = "home"


class CustomDisableView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        messages.error(request, "Two-factor authentication is required and cannot be disabled.")
        return redirect(reverse("two_factor:profile"))

    def post(self, request: HttpRequest) -> HttpResponse:
        messages.error(request, "Two-factor authentication is required and cannot be disabled.")
        return redirect(reverse("two_factor:profile"))


class CustomLoginView(LoginView):  # type: ignore[misc]
    def _should_show_captcha(self) -> bool:
        ip = get_client_ip_address(self.request)
        if not ip:
            return False
        return bool(
            AccessAttempt.objects.filter(
                ip_address=ip,
                failures_since_start__gte=settings.CAPTCHA_FAILURE_THRESHOLD,
            ).exists()
        )

    def get_context_data(self, form: object, **kwargs: object) -> dict[str, object]:
        context: dict[str, object] = super().get_context_data(form, **kwargs)
        if self.steps.current == self.AUTH_STEP and self._should_show_captcha():
            context["show_captcha"] = True
            context["turnstile_site_key"] = settings.TURNSTILE_SITE_KEY
        return context

    def post(self, *args: object, **kwargs: object) -> HttpResponse:
        is_auth_submission = (
            self.steps.current == self.AUTH_STEP
            and "wizard_goto_step" not in self.request.POST
            and "challenge_device" not in self.request.POST
        )
        if is_auth_submission and self._should_show_captcha():
            token = self.request.POST.get("cf-turnstile-response", "")
            ip = get_client_ip_address(self.request) or ""
            if not verify_turnstile(token, ip):
                form = self.get_form(data=self.request.POST, files=self.request.FILES)
                form._errors = ErrorDict()
                form.add_error(None, "CAPTCHA verification failed. Please try again.")
                response: HttpResponse = self.render(form)
                return response
        response = super().post(*args, **kwargs)
        return response


def signup_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("home")
    context: dict[str, object] = {"turnstile_site_key": settings.TURNSTILE_SITE_KEY}
    if request.method == "POST":
        token = request.POST.get("cf-turnstile-response", "")
        ip = get_client_ip_address(request) or ""
        if not verify_turnstile(token, ip):
            form = SignUpForm(request.POST)
            form.add_error(None, "CAPTCHA verification failed. Please try again.")
            return render(request, "auth/signup.html", {**context, "form": form})
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user, backend="django.contrib.auth.backends.ModelBackend")
            messages.success(request, "Account created! Please set up two-factor authentication.")
            return redirect(reverse("two_factor:setup"))
    else:
        form = SignUpForm()
    return render(request, "auth/signup.html", {**context, "form": form})


def logout_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        logout(request)
        messages.success(request, "You have been logged out.")
        return redirect(reverse("two_factor:login"))
    return redirect("home")


@login_required
def home_view(request: HttpRequest) -> HttpResponse:
    expense_months = ExpenseMonth.objects.filter(user=request.user).order_by("-month")
    return render(request, "home.html", {"expense_months": expense_months})


def health_check_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("ok", status=200)
