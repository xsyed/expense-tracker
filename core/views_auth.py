from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from two_factor.views import SetupView

from .forms import SignUpForm
from .models import ExpenseMonth


class CustomSetupView(SetupView):  # type: ignore[misc]
    success_url = "home"


class CustomDisableView(View):
    def get(self, request: HttpRequest) -> HttpResponse:
        messages.error(request, "Two-factor authentication is required and cannot be disabled.")
        return redirect(reverse("two_factor:profile"))

    def post(self, request: HttpRequest) -> HttpResponse:
        messages.error(request, "Two-factor authentication is required and cannot be disabled.")
        return redirect(reverse("two_factor:profile"))


def signup_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("/")
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created! Please set up two-factor authentication.")
            return redirect(reverse("two_factor:setup"))
    else:
        form = SignUpForm()
    return render(request, "auth/signup.html", {"form": form})


def logout_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        logout(request)
        messages.success(request, "You have been logged out.")
        return redirect(reverse("two_factor:login"))
    return redirect("/")


@login_required
def home_view(request: HttpRequest) -> HttpResponse:
    expense_months = ExpenseMonth.objects.filter(user=request.user).order_by("-month")
    return render(request, "home.html", {"expense_months": expense_months})
