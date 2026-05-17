from __future__ import annotations

import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .forms import GoalContributionForm, GoalForm
from .goal_progress import debt_goal_progress, savings_goal_progress, spending_goal_progress
from .models import Goal, GoalContribution


@login_required
def goal_list_view(request: HttpRequest) -> HttpResponse:
    goals = Goal.objects.filter(user=request.user).select_related("category")
    today = datetime.date.today()
    current_month = today.replace(day=1)

    goal_data = []
    for goal in goals:
        if goal.goal_type == "savings":
            progress = savings_goal_progress(goal)
        elif goal.goal_type == "debt":
            progress = debt_goal_progress(goal)
        else:
            progress = spending_goal_progress(goal, current_month)

        pct = min(int(progress / goal.target_amount * 100), 100) if goal.target_amount > 0 else 0
        goal_data.append({"goal": goal, "progress": progress, "pct": pct})

    return render(request, "goals/list.html", {"goal_data": goal_data})


@login_required
def goal_create_view(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        form = GoalForm(request.POST, user=request.user)
        if form.is_valid():
            goal = form.save(commit=False)
            goal.user = request.user
            goal.save()
            messages.success(request, f'Goal "{goal.name}" created.')
            return redirect("goal_list")
    else:
        form = GoalForm(user=request.user)
    return render(request, "goals/create.html", {"form": form})


@login_required
def goal_edit_view(request: HttpRequest, pk: int) -> HttpResponse:
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    if request.method == "POST":
        form = GoalForm(request.POST, instance=goal, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, f'Goal "{goal.name}" updated.')
            return redirect("goal_list")
    else:
        form = GoalForm(instance=goal, user=request.user)
    return render(request, "goals/edit.html", {"form": form, "goal": goal})


@login_required
def goal_delete_view(request: HttpRequest, pk: int) -> HttpResponse:
    goal = get_object_or_404(Goal, pk=pk, user=request.user)
    if request.method == "POST":
        name = goal.name
        goal.delete()
        messages.success(request, f'Goal "{name}" deleted.')
        return redirect("goal_list")
    return render(request, "goals/delete.html", {"goal": goal})


@login_required
def goal_contribute_view(request: HttpRequest, pk: int) -> HttpResponse:
    goal = get_object_or_404(Goal, pk=pk, user=request.user, goal_type="savings")
    if request.method == "POST":
        form = GoalContributionForm(request.POST)
        if form.is_valid():
            contribution: GoalContribution = form.save(commit=False)
            contribution.goal = goal
            contribution.save()
            messages.success(request, f"Contribution of ${contribution.amount} logged.")
            return redirect("goal_list")
    else:
        form = GoalContributionForm(initial={"date": datetime.date.today()})
    return render(request, "goals/contribute.html", {"form": form, "goal": goal})
