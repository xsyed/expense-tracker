import datetime
import json
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .csv_parser import CSVParser
from .forms import CategoryForm, CSVUploadForm, ExpenseMonthCreateForm, ExpenseMonthEditForm, LoginForm, SignUpForm
from .models import Category, CSVUpload, ExpenseMonth, Transaction


def _month_summary(month):
    income = month.total_income
    expenses = month.total_expenses
    net = month.net_balance
    return {
        'income': f'{income:.2f}',
        'expense': f'{expenses:.2f}',
        'net': f'{net:.2f}',
        'net_positive': net >= 0,
    }


def signup_view(request):
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


def login_view(request):
    if request.user.is_authenticated:
        return redirect("/")
    next_url = request.GET.get("next", "/")
    if request.method == "POST":
        form = LoginForm(request.POST, request=request)
        if form.is_valid():
            login(request, form.get_user())
            return redirect(next_url)
    else:
        form = LoginForm()
    return render(request, "auth/login.html", {"form": form, "next": next_url})


def logout_view(request):
    if request.method == "POST":
        logout(request)
        messages.success(request, "You have been logged out.")
        return redirect("/auth/login/")
    return redirect("/")


@login_required
def home_view(request):
    expense_months = ExpenseMonth.objects.filter(user=request.user)
    return render(request, "home.html", {"expense_months": expense_months})


@login_required
def month_list_view(request):
    expense_months = ExpenseMonth.objects.filter(user=request.user)
    return render(request, "months/list.html", {"expense_months": expense_months})


@login_required
def month_create_view(request):
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
def month_detail_view(request, pk):
    expense_month = get_object_or_404(ExpenseMonth, pk=pk, user=request.user)
    transactions_data = [
        {
            'id': tx.id,
            'date': str(tx.date),
            'description': tx.description,
            'amount': float(tx.amount),
            'account': tx.account or '',
            'transaction_type': tx.transaction_type,
            'category_id': str(tx.category_id) if tx.category_id else '',
            'category_name': tx.category.name if tx.category else '',
        }
        for tx in expense_month.transactions.select_related('category').all()
    ]
    categories_data = [
        {'id': c.id, 'name': c.name}
        for c in Category.objects.filter(user=request.user)
    ]
    return render(request, "months/detail.html", {
        "expense_month": expense_month,
        "transactions_json": json.dumps(transactions_data),
        "categories_json": json.dumps(categories_data),
    })


@login_required
@require_POST
def transaction_update_view(request, month_id, tx_id):
    month = get_object_or_404(ExpenseMonth, id=month_id, user=request.user)
    transaction = get_object_or_404(Transaction, id=tx_id, expense_month=month)

    try:
        body = json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return JsonResponse({'success': False, 'error': 'Invalid request body.'}, status=400)

    field = body.get('field')
    value = body.get('value')

    if field == 'date':
        try:
            transaction.date = datetime.date.fromisoformat(str(value))
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Invalid date. Use YYYY-MM-DD format.', 'field': 'date'}, status=400)

    elif field == 'description':
        if not value or not str(value).strip():
            return JsonResponse({'success': False, 'error': 'Description cannot be empty.', 'field': 'description'}, status=400)
        if len(str(value)) > 500:
            return JsonResponse({'success': False, 'error': 'Description must be 500 characters or fewer.', 'field': 'description'}, status=400)
        transaction.description = str(value).strip()

    elif field == 'amount':
        try:
            dec = Decimal(str(value)).quantize(Decimal('0.01'))
            if dec <= 0:
                raise ValueError
        except (InvalidOperation, ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Amount must be a positive number.', 'field': 'amount'}, status=400)
        transaction.amount = dec

    elif field == 'account':
        if value and len(str(value)) > 200:
            return JsonResponse({'success': False, 'error': 'Account must be 200 characters or fewer.', 'field': 'account'}, status=400)
        transaction.account = str(value) if value else ''

    elif field == 'transaction_type':
        if value not in ('income', 'expense', 'unassigned'):
            return JsonResponse({'success': False, 'error': 'Invalid transaction type.', 'field': 'transaction_type'}, status=400)
        transaction.transaction_type = value

    elif field == 'category_id':
        if not value:
            transaction.category = None
        else:
            try:
                transaction.category = Category.objects.get(id=value, user=request.user)
            except Category.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Invalid category.', 'field': 'category_id'}, status=400)

    else:
        return JsonResponse({'success': False, 'error': f'Unknown field: {field}.'}, status=400)

    transaction.save()
    tx_data = {
        'id': transaction.id,
        'date': str(transaction.date),
        'description': transaction.description,
        'amount': float(transaction.amount),
        'account': transaction.account or '',
        'transaction_type': transaction.transaction_type,
        'category_id': str(transaction.category_id) if transaction.category_id else '',
        'category_name': transaction.category.name if transaction.category else '',
    }
    return JsonResponse({'success': True, 'transaction': tx_data, 'summary': _month_summary(month)})


@login_required
@require_POST
def transaction_delete_view(request, month_id, tx_id):
    month = get_object_or_404(ExpenseMonth, id=month_id, user=request.user)
    transaction = get_object_or_404(Transaction, id=tx_id, expense_month=month)
    transaction.delete()
    return JsonResponse({'success': True, 'summary': _month_summary(month)})


@login_required
def month_edit_view(request, pk):
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
def month_delete_view(request, pk):
    expense_month = get_object_or_404(ExpenseMonth, pk=pk, user=request.user)
    if request.method == "POST":
        label = expense_month.label
        expense_month.delete()
        messages.success(request, f'Expense month "{label}" and all its data have been deleted.')
        return redirect("home")
    return render(request, "months/delete.html", {"expense_month": expense_month})


@login_required
def csv_upload_view(request, pk):
    if request.method != "POST":
        return redirect("month_detail", pk=pk)

    expense_month = get_object_or_404(ExpenseMonth, pk=pk, user=request.user)
    files = request.FILES.getlist("csv_file")

    if not files:
        messages.error(request, "No files were uploaded.")
        return redirect("month_detail", pk=pk)

    total_imported = 0

    for f in files:
        if not f.name.lower().endswith(".csv"):
            messages.error(request, f'"{f.name}" is not a CSV file. Skipped.')
            continue

        rows, errors = CSVParser().parse(f, f.name)

        if not rows and errors:
            messages.error(request, f'"{f.name}": {errors[0]}')
            continue

        if rows:
            Transaction.objects.bulk_create(
                [
                    Transaction(
                        expense_month=expense_month,
                        date=row["date"],
                        description=row["description"],
                        amount=row["amount"],
                        account=row.get("account", ""),
                        source_file=row.get("source_file", f.name),
                    )
                    for row in rows
                ]
            )
            CSVUpload.objects.create(
                expense_month=expense_month,
                filename=f.name,
                row_count=len(rows),
            )
            total_imported += len(rows)

        if errors:
            messages.warning(
                request,
                f'"{f.name}": {len(errors)} row(s) had errors and were skipped.',
            )

    if total_imported > 0:
        messages.success(request, f"Successfully imported {total_imported} transaction(s).")

    return redirect("month_detail", pk=pk)


@login_required
def category_list_view(request):
    categories = Category.objects.filter(user=request.user)
    if request.method == "POST":
        form = CategoryForm(request.POST, user=request.user)
        if form.is_valid():
            category = form.save(commit=False)
            category.user = request.user
            category.save()
            messages.success(request, f'Category "{category.name}" created.')
            return redirect("category_list")
    else:
        form = CategoryForm(user=request.user)
    return render(request, "categories/list.html", {"categories": categories, "form": form})


@login_required
def category_edit_view(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == "POST":
        form = CategoryForm(request.POST, instance=category, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Category renamed to "{category.name}".')
            return redirect("category_list")
    else:
        form = CategoryForm(instance=category, user=request.user)
    return render(request, "categories/edit.html", {"form": form, "category": category})


@login_required
def category_delete_view(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == "POST":
        name = category.name
        category.delete()
        messages.success(request, f'Category "{name}" deleted.')
        return redirect("category_list")
    return render(request, "categories/delete.html", {"category": category})
