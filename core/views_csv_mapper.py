from __future__ import annotations

import contextlib
import csv
import io
from datetime import date
from decimal import Decimal
from typing import IO, Any, TypedDict

from defusedcsv import csv as defusedcsv  # type: ignore[import-untyped]
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from .csv_parser import CSVParser
from .models import Account, ExpenseMonth, Transaction

_parser = CSVParser()


class CsvMapping(TypedDict, total=False):
    date_col: str
    desc_col: str
    amount_cols: list[str]
    account_col: str


def _apply_mapping(file: IO[bytes], mapping: CsvMapping) -> list[dict[str, Any]]:
    raw: bytes = file.read()
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = raw.decode("latin-1", errors="replace")

    rows: list[dict[str, Any]] = []
    account_col = mapping.get("account_col")
    amount_cols: list[str] = mapping.get("amount_cols") or []

    for row in csv.DictReader(io.StringIO(text)):
        date_str = (row.get(mapping.get("date_col", "")) or "").strip()
        desc_str = (row.get(mapping.get("desc_col", "")) or "").strip()
        account_str: str | None = (row.get(account_col) or "").strip() if account_col else None

        parsed_date = _parser._parse_date(date_str)
        parsed_amount: Decimal | None = None

        filled = [(col, val) for col in amount_cols if (val := (row.get(col) or "").strip())]
        if len(filled) == 1:
            with contextlib.suppress(ValueError, TypeError):
                parsed_amount = abs(Decimal(str(_parser._parse_amount(filled[0][1]))))
        # len == 0 (none filled) or len > 1 (conflict) → parsed_amount stays None → parse_error

        entry: dict[str, Any] = {
            "date": parsed_date,
            "description": desc_str,
            "amount": parsed_amount,
            "account_from_col": account_str,
        }
        if parsed_date is None or parsed_amount is None:
            entry["parse_error"] = True
        rows.append(entry)

    return rows


def _build_mapping(post: Any) -> CsvMapping:
    mapping: CsvMapping = {
        "date_col": post.get("map_date", ""),
        "desc_col": post.get("map_description", ""),
        "amount_cols": [v for v in post.getlist("map_amount") if v],
    }
    account_col_name: str = post.get("map_account_col", "")
    if account_col_name:
        mapping["account_col"] = account_col_name
    return mapping


def _resolve_account(post: Any, user: Any) -> Account | None:
    account_id_str: str = post.get("account_id", "")
    if not account_id_str:
        return None
    try:
        return Account.objects.get(pk=int(account_id_str), user=user)
    except (Account.DoesNotExist, ValueError):
        return None


@login_required
def csv_mapper_view(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        accounts = Account.objects.filter(user=request.user).order_by("name")
        return render(request, "csv_mapper/index.html", {"accounts": accounts})

    csv_file = request.FILES.get("csv_file")
    if not csv_file:
        accounts = Account.objects.filter(user=request.user).order_by("name")
        return render(request, "csv_mapper/index.html", {"accounts": accounts})

    rows = _apply_mapping(csv_file, _build_mapping(request.POST))
    today = date.today()
    account = _resolve_account(request.POST, request.user)

    skipped_errors = 0
    skipped_future = 0
    groups: dict[tuple[int, int], list[dict[str, Any]]] = {}

    for row in rows:
        if row.get("parse_error"):
            skipped_errors += 1
            continue
        if row["date"] > today:
            skipped_future += 1
            continue
        key = (row["date"].year, row["date"].month)
        groups.setdefault(key, []).append(row)

    total_imported = 0
    months_summary: list[dict[str, Any]] = []

    for (year, month), group_rows in groups.items():
        month_date = date(year, month, 1)
        expense_month, created = ExpenseMonth.objects.get_or_create(
            user=request.user,
            month=month_date,
            defaults={"label": month_date.strftime("%b %y")},
        )
        Transaction.objects.bulk_create(
            [
                Transaction(
                    expense_month=expense_month,
                    date=row["date"],
                    description=row["description"],
                    amount=row["amount"],
                    transaction_type="expense",
                    category=None,
                    account=account,
                )
                for row in group_rows
            ]
        )
        count = len(group_rows)
        total_imported += count
        months_summary.append({"month": expense_month, "count": count, "is_new": created})

    return render(
        request,
        "csv_mapper/result.html",
        {
            "total_imported": total_imported,
            "skipped_future": skipped_future,
            "skipped_errors": skipped_errors,
            "months_summary": months_summary,
        },
    )


@login_required
def csv_mapper_download_view(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)

    csv_file = request.FILES.get("csv_file")
    if not csv_file:
        return HttpResponse("No file uploaded.", status=400)

    rows = _apply_mapping(csv_file, _build_mapping(request.POST))
    today = date.today()
    account = _resolve_account(request.POST, request.user)
    include_account = account is not None

    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="mapped_transactions.csv"'

    writer = defusedcsv.writer(response)
    headers = ["Date", "Description", "Amount"]
    if include_account:
        headers.append("Account")
    writer.writerow(headers)

    for row in rows:
        if row.get("parse_error") or row["date"] > today:
            continue
        row_data = [row["date"].isoformat(), row["description"], str(row["amount"])]
        if include_account:
            row_data.append(account.name)  # type: ignore[union-attr]
        writer.writerow(row_data)

    return response


@login_required
def csv_mapper_sample_view(request: HttpRequest) -> HttpResponse:
    lines = [
        "Date,Description,Amount",
        "2026-03-01,Coffee Shop,4.50",
        "2026-03-02,Grocery Store,82.30",
        "2026-03-05,Phone Bill,45.00",
    ]
    content = "\r\n".join(lines) + "\r\n"
    response = HttpResponse(content, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="sample.csv"'
    return response
