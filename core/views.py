from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .csv_parser import CSVParser
from .forms import CategoryForm, CSVUploadForm, ExpenseMonthCreateForm, ExpenseMonthEditForm, LoginForm, SignUpForm
from .models import Category, CSVUpload, ExpenseMonth, Transaction


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
    return render(request, "months/detail.html", {"expense_month": expense_month})


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
