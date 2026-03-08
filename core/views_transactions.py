from __future__ import annotations

import datetime
import json
from decimal import Decimal, InvalidOperation

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST

from .models import Category, ExpenseMonth, Transaction, UserGridPreference
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

    elif field == "account":
        if value and len(str(value)) > 200:  # noqa: PLR2004
            return JsonResponse(
                {"success": False, "error": "Account must be 200 characters or fewer.", "field": "account"},
                status=400,
            )
        transaction.account = str(value) if value else ""

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
                transaction.category = Category.objects.get(id=value, user=request.user)
            except Category.DoesNotExist:
                return JsonResponse(
                    {"success": False, "error": "Invalid category.", "field": "category_id"},
                    status=400,
                )

    else:
        return JsonResponse({"success": False, "error": f"Unknown field: {field}."}, status=400)

    transaction.save()
    tx_data = {
        "id": transaction.id,
        "date": str(transaction.date),
        "description": transaction.description,
        "amount": float(transaction.amount),
        "account": transaction.account or "",
        "transaction_type": transaction.transaction_type,
        "category_id": str(transaction.category_id) if transaction.category_id else "",
        "category_name": transaction.category.name if transaction.category else "",
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
    grid_columns = {"date", "description", "amount", "account", "transaction_type", "category_name"}
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
    defaults["account"] = False
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
