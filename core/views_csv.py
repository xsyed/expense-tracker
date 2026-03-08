from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect

from .csv_parser import CSVParser
from .models import CSVUpload, ExpenseMonth, Transaction


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

    for f in files:
        if not f.name or not f.name.lower().endswith(".csv"):
            messages.error(request, f'"{f.name}" is not a CSV file. Skipped.')
            continue

        filename = f.name
        rows, errors = CSVParser().parse(f, filename)

        if not rows and errors:
            messages.error(request, f'"{filename}": {errors[0]}')
            continue

        if rows:
            Transaction.objects.bulk_create(
                [
                    Transaction(
                        expense_month=expense_month,
                        date=row["date"],
                        description=row["description"],
                        amount=row["amount"],
                        source_file=row.get("source_file", filename),
                        transaction_type="expense",
                    )
                    for row in rows
                ]
            )
            CSVUpload.objects.create(
                expense_month=expense_month,
                filename=filename,
                row_count=len(rows),
            )
            total_imported += len(rows)

        if errors:
            messages.warning(
                request,
                f'"{filename}": {len(errors)} row(s) had errors and were skipped.',
            )

    if total_imported > 0:
        messages.success(request, f"Successfully imported {total_imported} transaction(s).")

    return redirect("month_detail", pk=pk)
