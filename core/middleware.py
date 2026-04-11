from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import Resolver404, resolve, reverse
from django_otp import user_has_device

EXEMPT_URL_NAMES = frozenset(
    {
        "two_factor:setup",
        "two_factor:qr",
        "two_factor:login",
        "custom_2fa_setup",
        "signup",
        "logout",
        "health_check",
    }
)

EXEMPT_PATH_PREFIXES = ("/static/", "/admin/login/")


class Require2FASetupMiddleware:
    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if not request.user.is_authenticated:
            return self.get_response(request)

        if user_has_device(request.user):
            return self.get_response(request)

        if request.path.startswith(EXEMPT_PATH_PREFIXES):
            return self.get_response(request)

        try:
            match = resolve(request.path)
        except Resolver404:
            return self.get_response(request)

        url_name = f"{match.namespace}:{match.url_name}" if match.namespace else match.url_name
        if url_name in EXEMPT_URL_NAMES:
            return self.get_response(request)

        return redirect(reverse("two_factor:setup"))
