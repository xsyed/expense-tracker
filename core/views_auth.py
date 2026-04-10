from __future__ import annotations

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import LoginForm, SignUpForm
from .models import ExpenseMonth


def signup_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("/")
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Account created successfully. Welcome!")
            return redirect("/")
    else:
        form = SignUpForm()
    return render(request, "auth/signup.html", {"form": form})


def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect("/")
    raw_next = request.GET.get("next", "/")
    next_url = raw_next if url_has_allowed_host_and_scheme(raw_next, allowed_hosts={request.get_host()}) else "/"
    if request.method == "POST":
        form = LoginForm(request.POST, request=request)
        if form.is_valid():
            login(request, form.get_user())
            return redirect(next_url)
    else:
        form = LoginForm()
    return render(request, "auth/login.html", {"form": form, "next": next_url})


def logout_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        logout(request)
        messages.success(request, "You have been logged out.")
        return redirect("/auth/login/")
    return redirect("/")


@login_required
def home_view(request: HttpRequest) -> HttpResponse:
    expense_months = ExpenseMonth.objects.filter(user=request.user).order_by("-month")
    return render(request, "home.html", {"expense_months": expense_months})
