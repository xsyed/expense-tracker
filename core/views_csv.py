from __future__ import annotations

import calendar
from datetime import date
from typing import Any

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect

from .csv_parser import CSVParser
from .merchant_utils import load_merchant_rules, match_merchant
from .models import CSVUpload, ExpenseMonth, Transaction


def _build_transactions(
    rows: list[dict[str, Any]],
    expense_month: ExpenseMonth,
    filename: str,
    rules: dict[str, tuple[int, str]],
) -> list[Transaction]:
    result = []
    for row in rows:
        match = match_merchant(row["description"], rules)
        cat_id = match[0] if match else None
        tx_type = match[1] if match else "expense"
        result.append(
            Transaction(
                expense_month=expense_month,
                date=row["date"],
                description=row["description"],
                amount=row["amount"],
                source_file=row.get("source_file", filename),
                transaction_type=tx_type,
                category_id=cat_id,
                auto_categorized=cat_id is not None,
            )
        )
    return result


@login_required
def csv_upload_view(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != "POST":
        return redirect("month_detail", pk=pk)

    expense_month = get_object_or_404(ExpenseMonth, pk=pk, user=request.user)
    files = request.FILES.getlist("csv_file")

    if not files:
        messages.error(request, "No files were uploaded.")
        return redirect("month_detail", pk=pk)

    total_imported = 0
    rules = load_merchant_rules(request.user.pk)
    start_date: date = expense_month.month
    last_day = calendar.monthrange(start_date.year, start_date.month)[1]
    end_date = date(start_date.year, start_date.month, last_day)

    for f in files:
        if not f.name or not f.name.lower().endswith(".csv"):
            messages.error(request, f'"{f.name}" is not a CSV file. Skipped.')
            continue

        filename = f.name
        rows, errors = CSVParser().parse(f, filename)

        if not rows and errors:
            messages.error(request, f'"{filename}": {errors[0]}')
            continue

        valid_rows = [row for row in rows if start_date <= row["date"] <= end_date]
        excluded_rows = [row for row in rows if row not in valid_rows]

        if valid_rows:
            Transaction.objects.bulk_create(_build_transactions(valid_rows, expense_month, filename, rules))
            CSVUpload.objects.create(
                expense_month=expense_month,
                filename=filename,
                row_count=len(valid_rows),
            )
            total_imported += len(valid_rows)

        if excluded_rows:
            excluded_dates = ", ".join(row["date"].isoformat() for row in excluded_rows)
            msg = (
                f'"{filename}": {len(excluded_rows)} transaction(s) not imported'
                f" — date outside {expense_month.label}: {excluded_dates}"
            )
            messages.warning(request, msg)

        if errors:
            messages.warning(
                request,
                f'"{filename}": {len(errors)} row(s) had errors and were skipped.',
            )

    if total_imported > 0:
        messages.success(request, f"Successfully imported {total_imported} transaction(s).")

    return redirect("month_detail", pk=pk)
