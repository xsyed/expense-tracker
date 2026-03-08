from __future__ import annotations

import datetime
import json
import math

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ExpenseMonthCreateForm, ExpenseMonthEditForm
from .models import Category, ExpenseMonth, UserGridPreference


def _month_summary(month: ExpenseMonth) -> dict[str, int | bool]:
    income = month.total_income
    expenses = month.total_expenses
    net = month.net_balance
    return {
        "income": math.floor(income),
        "expense": math.floor(expenses),
        "net": math.floor(net),
        "net_positive": net >= 0,
    }


def _cutoff_date(months: int) -> datetime.date:
    """Return the first day of the month that is `months` before today."""
    today = datetime.date.today()
    year = today.year
    month = today.month - months
    while month <= 0:
        month += 12
        year -= 1
    return datetime.date(year, month, 1)


@login_required
def month_list_view(request: HttpRequest) -> HttpResponse:
    expense_months = ExpenseMonth.objects.filter(user=request.user)
    return render(request, "months/list.html", {"expense_months": expense_months})


@login_required
def month_create_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = ExpenseMonthCreateForm(request.POST, user=request.user)
        if form.is_valid():
            expense_month = form.save()
            messages.success(request, f'Expense month "{expense_month.label}" created.')
            return redirect("month_detail", pk=expense_month.pk)
    else:
        form = ExpenseMonthCreateForm(user=request.user)
    return render(request, "months/create.html", {"form": form})


@login_required
def month_detail_view(request: HttpRequest, pk: int) -> HttpResponse:
    grid_columns = ["date", "description", "amount", "account", "transaction_type", "category_name"]
    expense_month = get_object_or_404(ExpenseMonth, pk=pk, user=request.user)
    transactions_data = [
        {
            "id": tx.id,
            "date": str(tx.date),
            "description": tx.description,
            "amount": float(tx.amount),
            "account": tx.account or "",
            "transaction_type": tx.transaction_type,
            "category_id": str(tx.category_id) if tx.category_id else "",
            "category_name": tx.category.name if tx.category else "",
        }
        for tx in expense_month.transactions.select_related("category").all()
    ]
    categories_data = [{"id": c.id, "name": c.name} for c in Category.objects.filter(user=request.user)]
    defaults = {col: True for col in grid_columns}
    defaults["account"] = False
    defaults["transaction_type"] = False
    pref, _ = UserGridPreference.objects.get_or_create(
        user=request.user,
        defaults={"column_visibility": defaults},
    )
    visibility = {**defaults, **pref.column_visibility}
    return render(
        request,
        "months/detail.html",
        {
            "expense_month": expense_month,
            "transactions_json": json.dumps(transactions_data),
            "categories_json": json.dumps(categories_data),
            "column_visibility_json": json.dumps(visibility),
        },
    )


@login_required
def month_edit_view(request: HttpRequest, pk: int) -> HttpResponse:
    expense_month = get_object_or_404(ExpenseMonth, pk=pk, user=request.user)
    if request.method == "POST":
        form = ExpenseMonthEditForm(request.POST, instance=expense_month)
        if form.is_valid():
            form.save()
            messages.success(request, f'Month renamed to "{expense_month.label}".')
            return redirect("month_detail", pk=expense_month.pk)
    else:
        form = ExpenseMonthEditForm(instance=expense_month)
    return render(request, "months/edit.html", {"form": form, "expense_month": expense_month})


@login_required
def month_delete_view(request: HttpRequest, pk: int) -> HttpResponse:
    expense_month = get_object_or_404(ExpenseMonth, pk=pk, user=request.user)
    if request.method == "POST":
        label = expense_month.label
        expense_month.delete()
        messages.success(request, f'Expense month "{label}" and all its data have been deleted.')
        return redirect("home")
    return render(request, "months/delete.html", {"expense_month": expense_month})
