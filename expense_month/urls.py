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

from core.views_accounts import account_delete_view, account_edit_view, account_list_view
from core.views_auth import home_view
from core.views_budgets import budget_setup_view
from core.views_categories import category_delete_view, category_edit_view, category_list_view
from core.views_charts import (
    chart_category_breakdown_view,
    chart_month_over_month_view,
    chart_monthly_totals_view,
    chart_top_categories_view,
)
from core.views_csv import csv_upload_view
from core.views_csv_mapper import (
    csv_mapper_bulk_view,
    csv_mapper_download_view,
    csv_mapper_sample_view,
    csv_mapper_view,
)
from core.views_insights import budget_data_view, insights_view
from core.views_months import month_create_view, month_delete_view, month_detail_view, month_edit_view, month_list_view
from core.views_transactions import (
    transaction_bulk_delete_view,
    transaction_delete_view,
    transaction_update_view,
    update_grid_preferences_view,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("core.urls")),
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
    path("api/insights/budget-data/", budget_data_view, name="budget_data"),
    path("insights/", insights_view, name="insights"),
]
