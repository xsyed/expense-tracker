# Phase 1 — Foundation & Authentication

## Overview
Establish the project skeleton, configure the database, and implement the full authentication layer. By the end of this phase the app is deployable locally, a user can sign up, log in, and log out, and every protected route correctly redirects unauthenticated visitors to the login screen. Nothing else is built yet — this phase is purely about laying a solid, secure base.

---

## Goals
- Stand up the Django project and database with the correct settings for local deployment.
- Implement a custom User model that uses **email** as the primary identifier instead of a username.
- Deliver fully working sign-up, login, and logout flows with proper form validation and user feedback.
- Provide a consistent, branded base layout (Bootstrap 5) that all future screens will extend.

---

## Scope

### Project Scaffolding
- Django 4.2 LTS project created with a single `core` app.
- SQLite configured as the database.
- Static files directory configured for vendor assets (HTMX, ApexCharts stubs).
- `DEBUG = True`, `SECRET_KEY` loaded from environment or `.env`, `ALLOWED_HOSTS` set for localhost.

### Custom User Model
- Email is the login identifier (`USERNAME_FIELD = 'email'`).
- Password stored securely via Django's default password hashing.
- Model set as `AUTH_USER_MODEL` before any migrations are run.

### Authentication Views & URLs
- **Sign Up** — email + password + confirm password. Validates that email is unique, passwords match, and password meets Django's default validators
- **Login** — email + password. Redirects to Home on success.
- **Logout** — POST-only. Redirects to Login on success.
- All auth routes live under `/auth/`.

### Base Layout
- `base.html` with Bootstrap 5 (CDN or local vendor).
- Top navigation bar: app name/logo on the left, nav links (Home, Categories, Logout) on the right.
- Flash message block (success / error / warning banners).
- Content block extended by all child templates.
- Login and sign-up pages extend a minimal `auth_base.html` (centered card, no nav).

### Route Protection
- All non-auth routes require a logged-in session.
- Unauthenticated requests redirect to `/auth/login/`.
- After login, users are redirected back to the originally requested URL (Django `next` parameter).

---

## Acceptance Criteria

| # | Criterion |
|---|-----------|
| 1 | A new visitor navigating to `/` is redirected to `/auth/login/`. |
| 2 | A visitor can create an account with a valid email and matching passwords; they are immediately logged in and redirected to Home. |
| 3 | Submitting sign-up with a duplicate email shows a clear validation error; no duplicate account is created. |
| 4 | Submitting sign-up with mismatched passwords shows a validation error; no account is created. |
| 5 | A registered user can log in with correct credentials and is redirected to Home. |
| 6 | Logging in with an incorrect password or unknown email shows a generic error ("Invalid email or password") without revealing which field is wrong. |
| 7 | A logged-in user clicking Logout is immediately signed out and redirected to the Login screen. |
| 8 | After logout, navigating back to any protected URL redirects to Login (session is fully cleared). |
| 9 | The Bootstrap 5 navigation bar renders correctly on sign-up, login, and all authenticated screens. |
| 10 | Flash messages (e.g., "Account created successfully") appear on the correct screen and disappear after one page load. |
