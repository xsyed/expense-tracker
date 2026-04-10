from django.urls import path

from .views_auth import logout_view, signup_view

urlpatterns = [
    path("signup/", signup_view, name="signup"),
    path("logout/", logout_view, name="logout"),
]
