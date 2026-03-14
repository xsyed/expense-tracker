from __future__ import annotations

import contextlib
import datetime
import json
from decimal import Decimal, InvalidOperation
from typing import cast

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from .merchant_utils import normalize_merchant
from .models import Account, Category, ExpenseMonth, MerchantRule, Transaction, UserGridPreference
from .views_months import _month_summary


@login_required
@require_POST
def transaction_update_view(request: HttpRequest, month_id: int, tx_id: int) -> JsonResponse:  # noqa: C901, PLR0911, PLR0912
    month = get_object_or_404(ExpenseMonth, id=month_id, user=request.user)
    transaction = get_object_or_404(Transaction, id=tx_id, expense_month=month)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"success": False, "error": "Invalid request body."}, status=400)

    field = body.get("field")
    value = body.get("value")

    if field == "date":
        try:
            transaction.date = datetime.date.fromisoformat(str(value))
        except (ValueError, TypeError):
            return JsonResponse(
                {"success": False, "error": "Invalid date. Use YYYY-MM-DD format.", "field": "date"},
                status=400,
            )

    elif field == "description":
        if not value or not str(value).strip():
            return JsonResponse(
                {"success": False, "error": "Description cannot be empty.", "field": "description"},
                status=400,
            )
        if len(str(value)) > 500:  # noqa: PLR2004
            return JsonResponse(
                {"success": False, "error": "Description must be 500 characters or fewer.", "field": "description"},
                status=400,
            )
        transaction.description = str(value).strip()

    elif field == "amount":
        try:
            dec = Decimal(str(value)).quantize(Decimal("0.01"))
            if dec <= 0:
                raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            return JsonResponse(
                {"success": False, "error": "Amount must be a positive number.", "field": "amount"},
                status=400,
            )
        transaction.amount = dec

    elif field == "account_id":
        if not value:
            transaction.account = None
        else:
            try:
                transaction.account = Account.objects.get(id=value, user=request.user)
            except Account.DoesNotExist:
                return JsonResponse(
                    {"success": False, "error": "Invalid account.", "field": "account_id"},
                    status=400,
                )

    elif field == "transaction_type":
        if value not in ("income", "expense", "unassigned"):
            return JsonResponse(
                {"success": False, "error": "Invalid transaction type.", "field": "transaction_type"},
                status=400,
            )
        transaction.transaction_type = value

    elif field == "category_id":
        if not value:
            transaction.category = None
        else:
            try:
                category = Category.objects.get(id=value, user=request.user)
            except Category.DoesNotExist:
                return JsonResponse(
                    {"success": False, "error": "Invalid category.", "field": "category_id"},
                    status=400,
                )
            transaction.category = category
            transaction.transaction_type = category.category_type
            normalized = normalize_merchant(transaction.description)
            MerchantRule.objects.update_or_create(
                user=request.user,
                normalized_name=normalized,
                defaults={"category_id": value},
            )
        transaction.auto_categorized = False

    else:
        return JsonResponse({"success": False, "error": f"Unknown field: {field}."}, status=400)

    transaction.save()
    tx_data = {
        "id": transaction.id,
        "date": str(transaction.date),
        "description": transaction.description,
        "amount": float(transaction.amount),
        "account_id": str(transaction.account_id) if transaction.account_id else "",
        "account_name": transaction.account.name if transaction.account else "",
        "transaction_type": transaction.transaction_type,
        "category_id": str(transaction.category_id) if transaction.category_id else "",
        "category_name": transaction.category.name if transaction.category else "",
        "auto_categorized": transaction.auto_categorized,
    }
    return JsonResponse({"success": True, "transaction": tx_data, "summary": _month_summary(month)})


def _parse_create_fields(
    body: dict[str, object],
) -> tuple[dict[str, str], datetime.date | None, str, Decimal | None]:
    errors: dict[str, str] = {}

    parsed_date: datetime.date | None = None
    date_val = body.get("date")
    try:
        _d = datetime.date.fromisoformat(str(date_val)) if date_val else None
        if _d is None:
            errors["date"] = "Date is required."
        else:
            parsed_date = _d
    except (ValueError, TypeError):
        errors["date"] = "Invalid date. Use YYYY-MM-DD format."

    desc_val = body.get("description", "")
    description = str(desc_val).strip() if desc_val else ""
    if not description:
        errors["description"] = "Description cannot be empty."
    elif len(description) > 500:  # noqa: PLR2004
        errors["description"] = "Description must be 500 characters or fewer."

    parsed_amount: Decimal | None = None
    amount_val = body.get("amount")
    try:
        _a = Decimal(str(amount_val)).quantize(Decimal("0.01"))
        if _a <= 0:
            raise ValueError
        parsed_amount = _a
    except (InvalidOperation, ValueError, TypeError):
        errors["amount"] = "Amount must be a positive number."

    return errors, parsed_date, description, parsed_amount


@login_required
@require_POST
def transaction_create_view(request: HttpRequest, month_id: int) -> JsonResponse:
    month = get_object_or_404(ExpenseMonth, id=month_id, user=request.user)
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"success": False, "error": "Invalid request body."}, status=400)

    errors, parsed_date, description, parsed_amount = _parse_create_fields(body)
    if errors:
        return JsonResponse({"success": False, "errors": errors}, status=400)

    date = cast(datetime.date, parsed_date)
    amount = cast(Decimal, parsed_amount)

    account: Account | None = None
    account_id_val = body.get("account_id")
    if account_id_val:
        with contextlib.suppress(Account.DoesNotExist, ValueError, TypeError):
            account = Account.objects.get(id=account_id_val, user=request.user)

    tx_type = str(body.get("transaction_type", "unassigned"))
    if tx_type not in ("income", "expense", "unassigned"):
        tx_type = "unassigned"

    category: Category | None = None
    category_id_val = body.get("category_id")
    if category_id_val:
        with contextlib.suppress(Category.DoesNotExist, ValueError, TypeError):
            category = Category.objects.get(id=category_id_val, user=request.user)

    transaction = Transaction.objects.create(
        expense_month=month,
        date=date,
        description=description,
        amount=amount,
        account=account,
        transaction_type=tx_type,
        category=category,
        source_file="",
    )
    tx_data = {
        "id": transaction.id,
        "date": str(transaction.date),
        "description": transaction.description,
        "amount": float(transaction.amount),
        "account_id": str(transaction.account_id) if transaction.account_id else "",
        "account_name": transaction.account.name if transaction.account else "",
        "transaction_type": transaction.transaction_type,
        "category_id": str(transaction.category_id) if transaction.category_id else "",
        "category_name": transaction.category.name if transaction.category else "",
        "auto_categorized": transaction.auto_categorized,
    }
    return JsonResponse({"success": True, "transaction": tx_data, "summary": _month_summary(month)})


@login_required
@require_POST
def transaction_delete_view(request: HttpRequest, month_id: int, tx_id: int) -> JsonResponse:
    month = get_object_or_404(ExpenseMonth, id=month_id, user=request.user)
    transaction = get_object_or_404(Transaction, id=tx_id, expense_month=month)
    transaction.delete()
    return JsonResponse({"success": True, "summary": _month_summary(month)})


@login_required
@require_POST
def update_grid_preferences_view(request: HttpRequest) -> JsonResponse:
    grid_columns = {"date", "description", "amount", "account_name", "transaction_type", "category_name"}
    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({"success": False, "error": "Invalid request body."}, status=400)

    column_visibility = body.get("column_visibility")
    if not isinstance(column_visibility, dict):
        return JsonResponse({"success": False, "error": "column_visibility must be an object."}, status=400)

    if not set(column_visibility.keys()).issubset(grid_columns):
        return JsonResponse({"success": False, "error": "Unknown column name(s) in column_visibility."}, status=400)
    if not all(isinstance(v, bool) for v in column_visibility.values()):
        return JsonResponse({"success": False, "error": "column_visibility values must be booleans."}, status=400)

    defaults = {col: True for col in grid_columns}
    defaults["account_name"] = False
    defaults["transaction_type"] = False
    pref, _ = UserGridPreference.objects.get_or_create(
        user=request.user,
        defaults={"column_visibility": defaults},
    )
    pref.column_visibility = {**defaults, **column_visibility}
    pref.save()
    return JsonResponse({"success": True})


@login_required
@require_POST
def transaction_bulk_delete_view(request: HttpRequest, month_id: int) -> JsonResponse:
    month = get_object_or_404(ExpenseMonth, id=month_id, user=request.user)
    try:
        body = json.loads(request.body)
        ids = body.get("ids", [])
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({"success": False, "error": "Invalid request body."}, status=400)
    if not isinstance(ids, list) or not ids:
        return JsonResponse({"success": False, "error": "No transaction IDs provided."}, status=400)
    deleted_count, _ = Transaction.objects.filter(id__in=ids, expense_month=month).delete()
    return JsonResponse({"success": True, "deleted_count": deleted_count, "summary": _month_summary(month)})
