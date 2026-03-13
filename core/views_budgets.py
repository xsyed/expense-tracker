from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from .forms import CategoryBudgetForm


@login_required
def budget_setup_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = CategoryBudgetForm(request.POST, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Budgets saved.")
            return redirect("budget_setup")
    else:
        form = CategoryBudgetForm(user=request.user)
    return render(request, "budgets/setup.html", {"form": form})
