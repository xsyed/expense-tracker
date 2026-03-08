from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AccountForm
from .models import Account


@login_required
def account_list_view(request: HttpRequest) -> HttpResponse:
    accounts = Account.objects.filter(user=request.user)
    if request.method == "POST":
        form = AccountForm(request.POST, user=request.user)
        if form.is_valid():
            account = form.save(commit=False)
            account.user = request.user
            account.save()
            messages.success(request, f'Account "{account.name}" created.')
            return redirect("account_list")
    else:
        form = AccountForm(user=request.user)
    return render(request, "accounts/list.html", {"accounts": accounts, "form": form})


@login_required
def account_edit_view(request: HttpRequest, pk: int) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, user=request.user)
    if request.method == "POST":
        form = AccountForm(request.POST, instance=account, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Account renamed to "{account.name}".')
            return redirect("account_list")
    else:
        form = AccountForm(instance=account, user=request.user)
    return render(request, "accounts/edit.html", {"form": form, "account": account})


@login_required
def account_delete_view(request: HttpRequest, pk: int) -> HttpResponse:
    account = get_object_or_404(Account, pk=pk, user=request.user)
    if request.method == "POST":
        name = account.name
        account.delete()
        messages.success(request, f'Account "{name}" deleted.')
        return redirect("account_list")
    return render(request, "accounts/delete.html", {"account": account})
