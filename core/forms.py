import datetime

from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password

from .models import Category, ExpenseMonth

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

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
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

    def save(self):
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

    def __init__(self, *args, request=None, **kwargs):
        self.request = request
        self._user = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get("email", "").lower()
        password = cleaned_data.get("password")
        if email and password:
            self._user = authenticate(self.request, username=email, password=password)
            if self._user is None:
                raise forms.ValidationError("Invalid email or password.")
            if not self._user.is_active:
                raise forms.ValidationError("This account has been disabled.")
        return cleaned_data

    def get_user(self):
        return self._user


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name"]
        widgets = {
            "name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Category name"}
            ),
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_name(self):
        name = self.cleaned_data["name"].strip()
        qs = Category.objects.filter(user=self.user, name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("You already have a category with this name.")
        return name


MONTH_CHOICES = [
    (1, "January"), (2, "February"), (3, "March"), (4, "April"),
    (5, "May"), (6, "June"), (7, "July"), (8, "August"),
    (9, "September"), (10, "October"), (11, "November"), (12, "December"),
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

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        today = datetime.date.today()
        year_choices = [(y, y) for y in range(today.year - 3, today.year + 3)]
        super().__init__(*args, **kwargs)
        self.fields["year"].choices = year_choices
        # Default selects to current month/year
        if not args and not kwargs.get("data"):
            self.fields["month"].initial = today.month
            self.fields["year"].initial = today.year

    def clean(self):
        cleaned_data = super().clean()
        month = cleaned_data.get("month")
        year = cleaned_data.get("year")
        if month and year:
            try:
                month_date = datetime.date(int(year), int(month), 1)
            except ValueError:
                raise forms.ValidationError("Invalid month/year combination.")
            cleaned_data["month_date"] = month_date
            if ExpenseMonth.objects.filter(user=self.user, month=month_date).exists():
                raise forms.ValidationError(
                    "You already have an expense month for this calendar month."
                )
        return cleaned_data

    def save(self):
        return ExpenseMonth.objects.create(
            user=self.user,
            label=self.cleaned_data["label"],
            month=self.cleaned_data["month_date"],
        )


class ExpenseMonthEditForm(forms.ModelForm):
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

    def clean_csv_file(self):
        files = self.files.getlist("csv_file")
        if not files:
            raise forms.ValidationError("Please select at least one CSV file.")
        for f in files:
            if not f.name.lower().endswith(".csv"):
                raise forms.ValidationError(
                    f'"{f.name}" is not a CSV file. Only .csv files are allowed.'
                )
        return files
