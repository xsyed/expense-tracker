from __future__ import annotations

import datetime
from typing import Any, cast

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.http import HttpRequest

from .models import Category, ExpenseMonth
from .models import User as UserModel

User = get_user_model()


class SignUpForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"autofocus": True, "placeholder": "you@example.com"}),
    )
    password1 = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={"placeholder": "Password"}),
    )
    password2 = forms.CharField(
        label="Confirm password",
        widget=forms.PasswordInput(attrs={"placeholder": "Confirm password"}),
    )

    def clean_email(self) -> str:
        email: str = self.cleaned_data["email"]
        email = email.lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self) -> dict[str, Any]:
        cleaned_data: dict[str, Any] = super().clean() or {}
        password1 = cleaned_data.get("password1")
        password2 = cleaned_data.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords do not match.")
        if password1:
            try:
                validate_password(password1)
            except forms.ValidationError as e:
                self.add_error("password1", e)
        return cleaned_data

    def save(self) -> UserModel:
        email = self.cleaned_data["email"]
        password = self.cleaned_data["password1"]
        return User.objects.create_user(email, password)


class LoginForm(forms.Form):
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={"autofocus": True, "placeholder": "you@example.com"}),
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={"placeholder": "Password"}),
    )

    def __init__(self, *args: Any, request: HttpRequest | None = None, **kwargs: Any) -> None:
        self.request = request
        self._user: UserModel | None = None
        super().__init__(*args, **kwargs)

    def clean(self) -> dict[str, Any]:
        cleaned_data: dict[str, Any] = super().clean() or {}
        email: str = cleaned_data.get("email") or ""
        email = email.lower()
        password = cleaned_data.get("password")
        if email and password:
            self._user = authenticate(self.request, username=email, password=password)
            if self._user is None:
                raise forms.ValidationError("Invalid email or password.")
            if not self._user.is_active:
                raise forms.ValidationError("This account has been disabled.")
        return cleaned_data

    def get_user(self) -> UserModel | None:
        return self._user


class CategoryForm(forms.ModelForm[Category]):
    class Meta:
        model = Category
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control", "placeholder": "Category name"}),
        }

    def __init__(self, *args: Any, user: UserModel | None = None, **kwargs: Any) -> None:
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_name(self) -> str:
        name: str = self.cleaned_data["name"]
        name = name.strip()
        qs = Category.objects.filter(user=self.user, name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("You already have a category with this name.")
        return name


MONTH_CHOICES = [
    (1, "January"),
    (2, "February"),
    (3, "March"),
    (4, "April"),
    (5, "May"),
    (6, "June"),
    (7, "July"),
    (8, "August"),
    (9, "September"),
    (10, "October"),
    (11, "November"),
    (12, "December"),
]


class ExpenseMonthCreateForm(forms.Form):
    label = forms.CharField(
        max_length=100,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. February 2026"}),
    )
    month = forms.ChoiceField(
        choices=MONTH_CHOICES,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    year = forms.ChoiceField(
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args: Any, user: UserModel | None = None, **kwargs: Any) -> None:
        self.user = user
        today = datetime.date.today()
        year_choices = [(y, y) for y in range(today.year - 3, today.year + 3)]
        super().__init__(*args, **kwargs)
        cast(forms.ChoiceField, self.fields["year"]).choices = year_choices
        # Default selects to current month/year
        if not args and not kwargs.get("data"):
            self.fields["month"].initial = today.month
            self.fields["year"].initial = today.year

    def clean(self) -> dict[str, Any]:
        cleaned_data: dict[str, Any] = super().clean() or {}
        month = cleaned_data.get("month")
        year = cleaned_data.get("year")
        if month and year:
            try:
                month_date = datetime.date(int(year), int(month), 1)
            except ValueError:
                raise forms.ValidationError("Invalid month/year combination.") from None
            cleaned_data["month_date"] = month_date
            if ExpenseMonth.objects.filter(user=self.user, month=month_date).exists():
                raise forms.ValidationError("You already have an expense month for this calendar month.")
        return cleaned_data

    def save(self) -> ExpenseMonth:
        assert self.user is not None
        return ExpenseMonth.objects.create(
            user=self.user,
            label=self.cleaned_data["label"],
            month=self.cleaned_data["month_date"],
        )


class ExpenseMonthEditForm(forms.ModelForm[ExpenseMonth]):
    class Meta:
        model = ExpenseMonth
        fields = ["label"]
        widgets = {
            "label": forms.TextInput(attrs={"class": "form-control"}),
        }


class _MultipleFileInput(forms.FileInput):
    """FileInput subclass that supports the ``multiple`` HTML attribute."""

    allow_multiple_selected = True


class CSVUploadForm(forms.Form):
    csv_file = forms.FileField(
        widget=_MultipleFileInput(attrs={"accept": ".csv", "class": "form-control"}),
        help_text="Select one or more .csv files to upload.",
    )

    def clean_csv_file(self) -> list[Any]:
        files = self.files.getlist("csv_file")
        if not files:
            raise forms.ValidationError("Please select at least one CSV file.")
        for f in files:
            if not f.name or not f.name.lower().endswith(".csv"):
                raise forms.ValidationError(f'"{f.name}" is not a CSV file. Only .csv files are allowed.')
        return files
