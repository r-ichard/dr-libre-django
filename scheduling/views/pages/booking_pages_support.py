"""Shared helpers of the booking page tests."""

from __future__ import annotations

import re
from datetime import UTC, datetime

from django.contrib.auth.hashers import make_password
from django.test import Client

from scheduling.models import User
from scheduling.models.builders import STARTS_AT, Clinic
from scheduling.views.pages.browser_support import browser_client

NOW = datetime(2030, 1, 7, 6, 0, tzinfo=UTC)
PHRASE = "correct horse battery staple"
VISITOR_EMAIL = "vera.page@example.test"
FORM = {
    "full_name": "Vera Visitor",
    "date_of_birth": "1985-03-14",
    "email": VISITOR_EMAIL,
    "phone": "",
    "reason": "Sore knee",
    "terms_accepted": "on",
}


def times_path(clinic: Clinic, query: str = "") -> str:
    return f"/book/{clinic.appointment_type.pk}{query}"


def details_path(clinic: Clinic) -> str:
    starts = STARTS_AT.strftime("%Y-%m-%dT%H:%M:%SZ")
    base = f"/book/{clinic.appointment_type.pk}/details"
    return f"{base}?provider={clinic.clinician.pk}&starts_at={starts}"


def signed_in_patient(user: User) -> Client:
    user.refresh_from_db()
    user.password = make_password(PHRASE)
    user.save()
    client = browser_client()
    client.get("/sign-in")
    response = client.post(
        "/api/v1/auth/login",
        {"email": user.email, "password": PHRASE},
        content_type="application/json",
    )
    assert response.status_code == 200  # noqa: S101 - a failed sign-in is a broken test setup
    return client


def no_inline_code(html: str) -> bool:
    return not re.search(r"<script(?![^>]*\bsrc=)", html) and "style=" not in html
