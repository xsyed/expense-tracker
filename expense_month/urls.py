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

from core import views as core_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("auth/", include("core.urls")),
    path("", core_views.home_view, name="home"),
    path("categories/", core_views.category_list_view, name="category_list"),
    path("categories/<int:pk>/edit/", core_views.category_edit_view, name="category_edit"),
    path("categories/<int:pk>/delete/", core_views.category_delete_view, name="category_delete"),
    path("months/", core_views.month_list_view, name="month_list"),
    path("months/create/", core_views.month_create_view, name="month_create"),
    path("months/<int:pk>/", core_views.month_detail_view, name="month_detail"),
    path("months/<int:pk>/edit/", core_views.month_edit_view, name="month_edit"),
    path("months/<int:pk>/delete/", core_views.month_delete_view, name="month_delete"),
    path("months/<int:pk>/upload/", core_views.csv_upload_view, name="csv_upload"),
    path("months/<int:month_id>/transactions/<int:tx_id>/update/", core_views.transaction_update_view, name="transaction_update"),
    path("months/<int:month_id>/transactions/<int:tx_id>/delete/", core_views.transaction_delete_view, name="transaction_delete"),
    path("api/charts/monthly-totals/", core_views.chart_monthly_totals_view, name="chart_monthly_totals"),
    path("api/charts/category-breakdown/", core_views.chart_category_breakdown_view, name="chart_category_breakdown"),
    path("api/charts/top-categories/", core_views.chart_top_categories_view, name="chart_top_categories"),
    path("api/charts/month-over-month/", core_views.chart_month_over_month_view, name="chart_mom"),
]
