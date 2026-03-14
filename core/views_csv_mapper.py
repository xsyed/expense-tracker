from __future__ import annotations

import contextlib
import csv
import io
from datetime import date
from decimal import Decimal
from typing import IO, Any, TypedDict

from defusedcsv import csv as defusedcsv  # type: ignore[import-untyped]
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import render

from .csv_parser import CSVParser
from .merchant_utils import load_merchant_rules, match_merchant
from .models import Account, ExpenseMonth, Transaction

_parser = CSVParser()


class CsvMapping(TypedDict, total=False):
    date_col: str
    desc_col: str
    amount_cols: list[str]
    account_col: str


class MonthSummary(TypedDict):
    label: str
    pk: int
    count: int
    is_new: bool


class ImportResult(TypedDict):
    total_imported: int
    skipped_errors: int
    skipped_future: int
    months: list[MonthSummary]


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


def _build_mapping(post: Any, prefix: str = "") -> CsvMapping:
    mapping: CsvMapping = {
        "date_col": post.get(f"{prefix}map_date", ""),
        "desc_col": post.get(f"{prefix}map_description", ""),
        "amount_cols": [v for v in post.getlist(f"{prefix}map_amount") if v],
    }
    account_col_name: str = post.get(f"{prefix}map_account_col", "")
    if account_col_name:
        mapping["account_col"] = account_col_name
    return mapping


def _resolve_account(post: Any, user: Any, prefix: str = "") -> Account | None:
    account_id_str: str = post.get(f"{prefix}account_id", "")
    if not account_id_str:
        return None
    try:
        return Account.objects.get(pk=int(account_id_str), user=user)
    except (Account.DoesNotExist, ValueError):
        return None


def _import_single_file(rows: list[dict[str, Any]], user: Any, account: Account | None) -> ImportResult:
    today = date.today()
    rules = load_merchant_rules(user.pk)
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
    months: list[MonthSummary] = []

    for (year, month), group_rows in groups.items():
        month_date = date(year, month, 1)
        expense_month, created = ExpenseMonth.objects.get_or_create(
            user=user,
            month=month_date,
            defaults={"label": month_date.strftime("%b %y")},
        )
        transactions_to_create = []
        for row in group_rows:
            match = match_merchant(row["description"], rules)
            cat_id = match[0] if match else None
            tx_type = match[1] if match else "expense"
            transactions_to_create.append(
                Transaction(
                    expense_month=expense_month,
                    date=row["date"],
                    description=row["description"],
                    amount=row["amount"],
                    transaction_type=tx_type,
                    category_id=cat_id,
                    auto_categorized=cat_id is not None,
                    account=account,
                )
            )
        Transaction.objects.bulk_create(transactions_to_create)
        count = len(group_rows)
        total_imported += count
        months.append({"label": expense_month.label, "pk": expense_month.pk, "count": count, "is_new": created})

    return {
        "total_imported": total_imported,
        "skipped_errors": skipped_errors,
        "skipped_future": skipped_future,
        "months": months,
    }


@login_required
def csv_mapper_view(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        accounts = Account.objects.filter(user=request.user).order_by("name")
        accounts_list = [{"pk": a.pk, "name": a.name} for a in accounts]
        return render(request, "csv_mapper/index.html", {"accounts_json": accounts_list})

    csv_file = request.FILES.get("csv_file")
    if not csv_file:
        return JsonResponse({"error": "No file uploaded."}, status=400)

    rows = _apply_mapping(csv_file, _build_mapping(request.POST))
    account = _resolve_account(request.POST, request.user)
    result = _import_single_file(rows, request.user, account)
    return JsonResponse(result)


@login_required
def csv_mapper_bulk_view(request: HttpRequest) -> HttpResponse:
    if request.method != "POST":
        return HttpResponse(status=405)

    try:
        file_count = max(1, min(6, int(request.POST.get("file_count", "0"))))
    except ValueError:
        return JsonResponse({"error": "Invalid file_count."}, status=400)

    results: list[ImportResult | dict[str, str]] = []
    for i in range(file_count):
        csv_file = request.FILES.get(f"file_{i}")
        if not csv_file:
            results.append({"error": f"File {i + 1} not uploaded."})
            continue
        prefix = f"{i}_"
        rows = _apply_mapping(csv_file, _build_mapping(request.POST, prefix))
        account = _resolve_account(request.POST, request.user, prefix)
        results.append(_import_single_file(rows, request.user, account))

    return JsonResponse({"results": results})


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
        "Date,Description,Amount,Type,Account",
        "2026-03-01,Coffee Shop,4.50,expense,Checking",
        "2026-03-02,Grocery Store,82.30,expense,Checking",
        "2026-03-05,Salary,3500.00,income,Savings",
    ]
    content = "\r\n".join(lines) + "\r\n"
    response = HttpResponse(content, content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="sample.csv"'
    return response
