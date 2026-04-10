"""
URL configuration for expense_month project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path
from two_factor.admin import AdminSiteOTPRequired
from two_factor.urls import urlpatterns as tf_urls

from core.views_accounts import account_delete_view, account_edit_view, account_list_view
from core.views_accounts_overview import accounts_overview_data_view
from core.views_auth import CustomDisableView, CustomSetupView, home_view, logout_view, signup_view
from core.views_budgets import budget_setup_view
from core.views_categories import category_delete_view, category_edit_view, category_list_view
from core.views_category_trends import category_trends_data_view
from core.views_charts import (
    chart_category_breakdown_view,
    chart_month_over_month_view,
    chart_monthly_totals_view,
    chart_top_categories_view,
)
from core.views_csv import csv_upload_view
from core.views_csv_mapper import (
    csv_mapper_bulk_view,
    csv_mapper_delete_profile,
    csv_mapper_download_view,
    csv_mapper_list_profiles,
    csv_mapper_match_profiles,
    csv_mapper_sample_view,
    csv_mapper_save_profile,
    csv_mapper_view,
)
from core.views_forecasting import forecasting_data_view
from core.views_goals import goal_contribute_view, goal_create_view, goal_delete_view, goal_edit_view, goal_list_view
from core.views_insights import (
    budget_data_view,
    burn_rate_data_view,
    goal_projection_data_view,
    goals_data_view,
    insights_view,
    recurring_data_view,
    spending_trend_data_view,
)
from core.views_months import month_create_view, month_delete_view, month_detail_view, month_edit_view, month_list_view
from core.views_savings_planner import savings_planner_overview_api, savings_planner_view
from core.views_transactions import (
    transaction_bulk_delete_view,
    transaction_create_view,
    transaction_delete_view,
    transaction_update_view,
    update_grid_preferences_view,
)

admin.site.__class__ = AdminSiteOTPRequired

urlpatterns = [
    path("admin/", admin.site.urls),
    path("account/two_factor/setup/", CustomSetupView.as_view(), name="custom_2fa_setup"),
    path("account/two_factor/disable/", CustomDisableView.as_view(), name="custom_2fa_disable"),
    path("", include(tf_urls)),
    path("auth/signup/", signup_view, name="signup"),
    path("auth/logout/", logout_view, name="logout"),
    path("", home_view, name="home"),
    path("categories/", category_list_view, name="category_list"),
    path("categories/<int:pk>/edit/", category_edit_view, name="category_edit"),
    path("categories/<int:pk>/delete/", category_delete_view, name="category_delete"),
    path("accounts/", account_list_view, name="account_list"),
    path("accounts/<int:pk>/edit/", account_edit_view, name="account_edit"),
    path("accounts/<int:pk>/delete/", account_delete_view, name="account_delete"),
    path("budgets/setup/", budget_setup_view, name="budget_setup"),
    path("months/", month_list_view, name="month_list"),
    path("months/create/", month_create_view, name="month_create"),
    path("months/<int:pk>/", month_detail_view, name="month_detail"),
    path("months/<int:pk>/edit/", month_edit_view, name="month_edit"),
    path("months/<int:pk>/delete/", month_delete_view, name="month_delete"),
    path("months/<int:pk>/upload/", csv_upload_view, name="csv_upload"),
    path(
        "months/<int:month_id>/transactions/<int:tx_id>/update/",
        transaction_update_view,
        name="transaction_update",
    ),
    path(
        "months/<int:month_id>/transactions/<int:tx_id>/delete/",
        transaction_delete_view,
        name="transaction_delete",
    ),
    path(
        "months/<int:month_id>/transactions/create/",
        transaction_create_view,
        name="transaction_create",
    ),
    path(
        "months/<int:month_id>/transactions/bulk-delete/",
        transaction_bulk_delete_view,
        name="transaction_bulk_delete",
    ),
    path("api/charts/monthly-totals/", chart_monthly_totals_view, name="chart_monthly_totals"),
    path("api/charts/category-breakdown/", chart_category_breakdown_view, name="chart_category_breakdown"),
    path("preferences/grid/", update_grid_preferences_view, name="grid_preferences_update"),
    path("api/charts/top-categories/", chart_top_categories_view, name="chart_top_categories"),
    path("api/charts/month-over-month/", chart_month_over_month_view, name="chart_mom"),
    path("csv-mapper/", csv_mapper_view, name="csv_mapper"),
    path("csv-mapper/bulk/", csv_mapper_bulk_view, name="csv_mapper_bulk"),
    path("csv-mapper/download/", csv_mapper_download_view, name="csv_mapper_download"),
    path("csv-mapper/sample.csv", csv_mapper_sample_view, name="csv_mapper_sample"),
    path("csv-mapper/profiles/", csv_mapper_list_profiles, name="csv_mapper_list_profiles"),
    path("csv-mapper/profiles/match/", csv_mapper_match_profiles, name="csv_mapper_match_profiles"),
    path("csv-mapper/profiles/save/", csv_mapper_save_profile, name="csv_mapper_save_profile"),
    path("csv-mapper/profiles/<int:pk>/delete/", csv_mapper_delete_profile, name="csv_mapper_delete_profile"),
    path("api/insights/budget-data/", budget_data_view, name="budget_data"),
    path("api/insights/burn-rate/", burn_rate_data_view, name="burn_rate_data"),
    path("api/insights/goals-data/", goals_data_view, name="goals_data"),
    path("api/insights/goals/<int:pk>/projection/", goal_projection_data_view, name="goal_projection_data"),
    path("api/insights/goals/<int:pk>/spending-trend/", spending_trend_data_view, name="spending_trend_data"),
    path("api/insights/recurring-data/", recurring_data_view, name="recurring_data"),
    path("api/insights/category-trends/", category_trends_data_view, name="category_trends_data"),
    path("api/insights/accounts-overview/", accounts_overview_data_view, name="accounts_overview_data"),
    path("api/insights/forecasting/", forecasting_data_view, name="forecasting_data"),
    path("insights/", insights_view, name="insights"),
    path("savings-planner/", savings_planner_view, name="savings_planner"),
    path("api/savings-planner/overview/", savings_planner_overview_api, name="savings_planner_overview_api"),
    path("goals/", goal_list_view, name="goal_list"),
    path("goals/create/", goal_create_view, name="goal_create"),
    path("goals/<int:pk>/edit/", goal_edit_view, name="goal_edit"),
    path("goals/<int:pk>/delete/", goal_delete_view, name="goal_delete"),
    path("goals/<int:pk>/contribute/", goal_contribute_view, name="goal_contribute"),
]
