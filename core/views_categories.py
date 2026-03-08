from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import CategoryForm
from .models import Category


@login_required
def category_list_view(request: HttpRequest) -> HttpResponse:
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
