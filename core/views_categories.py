from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CategoryForm, CategoryGroupForm
from .models import Category, CategoryGroup


@login_required
def category_list_view(request: HttpRequest) -> HttpResponse:
    categories = Category.objects.filter(user=request.user).select_related("category_group")
    expense_categories = categories.filter(category_type="expense")
    income_categories = categories.filter(category_type="income")
    category_groups = CategoryGroup.objects.filter(user=request.user).order_by("name")
    form = CategoryForm(user=request.user)
    group_form = CategoryGroupForm(user=request.user)

    if request.method == "POST":
        action = request.POST.get("action", "create_category")
        if action == "create_group":
            group_form = CategoryGroupForm(request.POST, user=request.user)
            if group_form.is_valid():
                group = group_form.save(commit=False)
                group.user = request.user
                group.save()
                messages.success(request, f'Category group "{group.name}" created.')
                return redirect("category_list")
        elif action == "rename_group":
            group = get_object_or_404(CategoryGroup, pk=request.POST.get("group_id"), user=request.user)
            rename_form = CategoryGroupForm(request.POST, instance=group, user=request.user)
            if rename_form.is_valid():
                rename_form.save()
                messages.success(request, f'Category group renamed to "{group.name}".')
                return redirect("category_list")
            messages.error(request, rename_form.errors.get("name", ["Could not rename category group."])[0])
        elif action == "delete_group":
            group = get_object_or_404(CategoryGroup, pk=request.POST.get("group_id"), user=request.user)
            name = group.name
            group.delete()
            messages.success(request, f'Category group "{name}" deleted.')
            return redirect("category_list")
        else:
            form = CategoryForm(request.POST, user=request.user)
            if form.is_valid():
                category = form.save(commit=False)
                category.user = request.user
                category.save()
                messages.success(request, f'Category "{category.name}" created.')
                return redirect("category_list")

    return render(
        request,
        "categories/list.html",
        {
            "categories": categories,
            "expense_categories": expense_categories,
            "income_categories": income_categories,
            "category_groups": category_groups,
            "form": form,
            "group_form": group_form,
        },
    )


@login_required
def category_edit_view(request: HttpRequest, pk: int) -> HttpResponse:
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
def category_delete_view(request: HttpRequest, pk: int) -> HttpResponse:
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == "POST":
        name = category.name
        category.delete()
        messages.success(request, f'Category "{name}" deleted.')
        return redirect("category_list")
    return render(request, "categories/delete.html", {"category": category})
