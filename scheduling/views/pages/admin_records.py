"""Section 10: the admin pages of the five records, one flow: list, show, form, delete. Each page
is told its kind by the route; what differs per record lives in `admin_record_kinds`."""

from urllib.parse import urlencode
from uuid import UUID

from django.db.models import Model
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import URLPattern, path

from scheduling.domain.failure import Failure, FailureCode, Result
from scheduling.domain.specialty_icons import FALLBACK_ICON, icon_file_for
from scheduling.domain.vocabulary import Role
from scheduling.models.base import Versioned
from scheduling.use_cases import admin_record_reads
from scheduling.use_cases.admin_record_specs import count_text
from scheduling.use_cases.admin_records import (
    RecordEdit,
    create_record,
    delete_record,
    dependents_of,
    update_record,
)
from scheduling.use_cases.request_context import current_request_context
from scheduling.views.pages.admin_record_forms import (
    form_fields,
    initial_text,
    parse_form,
    typed_text,
)
from scheduling.views.pages.admin_record_kinds import (
    CHECKBOX,
    KIND_VIEWS,
    SELECT,
    KindView,
)
from scheduling.views.pages.booking_links import path_uuid
from scheduling.views.pages.local_time import errors_by_field
from scheduling.views.pages.page_view import PageView, render_page

STALE_TEXT = (
    "Another admin saved this record first. Your changes are not saved. "
    "Saving again replaces theirs."
)
UNREADABLE_VERSION = "This form is out of date or damaged. Open the record again to edit it."


class RecordPage(PageView):
    allowed_roles = frozenset({Role.ADMIN})
    kind = ""

    @property
    def view(self) -> KindView:
        return KIND_VIEWS[self.kind]

    def record_or_404(self) -> Versioned:
        record = admin_record_reads.find_record(self.kind, path_uuid(self, "record_id"))
        if record is None:
            raise Http404
        return record

    def refusal_of(self, request: HttpRequest, failure: Failure) -> HttpResponse:
        if failure.code == FailureCode.NOT_FOUND:
            raise Http404
        return render_page(request, "errors/403.html", status=403, signed_in_user=self.user)


def _page_number(raw: str) -> int:
    return int(raw) if raw.isascii() and raw.isdigit() else 1


def _cell(record: Model, accessor: str) -> str:
    value: object = record
    for part in accessor.split("."):
        value = getattr(value, part)
    if isinstance(value, bool):
        return "Active" if value else "Inactive"
    return str(value)


class RecordListPage(RecordPage):
    template_name = "admin/list.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        query = request.GET.get("q", "").replace("\x00", "").strip()[:100]
        found = admin_record_reads.list_records(
            self.kind, query, _page_number(request.GET.get("page", ""))
        )
        view = self.view
        rows = [
            {
                "name": _cell(record, "name"),
                "href": f"{view.base_path}/{record.pk}",
                "code": _cell(record, "code"),
                "cells": [_cell(record, accessor) for _, accessor in view.columns],
            }
            for record in found.items
        ]
        word = view.singular if found.total == 1 else view.plural
        context = {
            "view": view,
            "rows": rows,
            "query": query,
            "total_text": f"{found.total} {word}",
            "current": view.path_name,
            "page": found.page,
            "page_count": found.page_count,
            "previous_href": self._href(query, found.page - 1) if found.page > 1 else "",
            "next_href": self._href(query, found.page + 1) if found.page < found.page_count else "",
        }
        return self.page(request, context)

    def _href(self, query: str, page: int) -> str:
        parameters = {"q": query, "page": page} if query else {"page": page}
        return f"{self.view.base_path}?{urlencode(parameters)}"


class RecordShowPage(RecordPage):
    template_name = "admin/show.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        record = self.record_or_404()
        view = self.view
        details = [
            (field.label, _detail(record, field.name, field.widget)) for field in view.fields
        ]
        uses = admin_record_reads.dependent_counts(self.kind, record.pk)
        context = {
            "view": view,
            "record": record,
            "details": details,
            "uses": [count_text(count, reason) for reason, count in uses.items() if count],
            "icon": _icon_of(record) if self.kind == "specialty" else None,
            "current": view.path_name,
            "record_path": f"{view.base_path}/{record.pk}",
        }
        return self.page(request, context)


def _detail(record: Model, name: str, widget: str) -> str:
    if widget == SELECT:
        related = getattr(record, name)
        return str(related) if name == "time_zone" else str(related.name)
    value = getattr(record, name)
    if widget == CHECKBOX:
        return "Yes" if value else "No"
    if isinstance(value, list):
        return ", ".join(value) or "None"
    return "None" if value is None or value == "" else str(value)


def _icon_of(record: Model) -> dict[str, object]:
    file = icon_file_for(_cell(record, "code"))
    return {"file": file, "is_fallback": file == FALLBACK_ICON}


class RecordFormPage(RecordPage):
    """New at /new, edit at /<id>/edit; one form."""

    template_name = "admin/form.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        record = self.record_or_404() if "record_id" in self.kwargs else None
        version = record.version if record is not None else None
        return self._form(request, initial_text(self.kind, record), {}, version)

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        typed = typed_text(self.kind, request.POST)
        values, errors = parse_form(self.kind, typed)
        if "record_id" not in self.kwargs:
            if errors:
                return self._form(request, typed, errors, None, 422)
            result = create_record(self.kind, values, self.user)
            return self._answer(request, result, typed, None)
        record_id = path_uuid(self, "record_id")
        version = request.POST.get("version", "")
        if not (version.isascii() and version.isdigit()):
            return self._form(request, typed, {}, None, 422, UNREADABLE_VERSION)
        if errors:
            return self._form(request, typed, errors, int(version), 422)
        result = update_record(RecordEdit(self.kind, record_id, values, int(version)), self.user)
        return self._answer(request, result, typed, int(version))

    def _answer(
        self, request: HttpRequest, result: Result[UUID], typed: dict[str, str], version: int | None
    ) -> HttpResponse:
        if not isinstance(result, Failure):
            return HttpResponseRedirect(f"{self.view.base_path}/{result.value}", status=303)
        if result.code == FailureCode.INVALID_INPUT:
            return self._form(request, typed, errors_by_field(result), version, 422)
        if result.code == FailureCode.CONFLICT:
            return self._form(request, typed, {}, self.record_or_404().version, 409, STALE_TEXT)
        return self.refusal_of(request, result)

    def _form(
        self,
        request: HttpRequest,
        typed: dict[str, str],
        errors: dict[str, str],
        version: int | None,
        status: int = 200,
        problem: str = "",
    ) -> HttpResponse:
        editing = "record_id" in self.kwargs
        view = self.view
        context = {
            "view": view,
            "title": f"Edit {view.singular}" if editing else view.new_text,
            "fields": form_fields(self.kind, typed, errors),
            "summary": [{"target": f"id_{name}", "message": text} for name, text in errors.items()],
            "version": version,
            "problem": problem,
            "is_stale": status == 409,
            "time_zone_note": self._time_zone_note(editing),
            "current": view.path_name,
            "back_path": self._back_path(editing),
        }
        return self.page(request, context, status)

    def _back_path(self, editing: bool) -> str:
        return (
            f"{self.view.base_path}/{self.kwargs['record_id']}" if editing else self.view.base_path
        )

    def _time_zone_note(self, editing: bool) -> str:
        if self.kind != "hospital" or not editing:
            return ""
        now = current_request_context().now
        upcoming = admin_record_reads.upcoming_appointment_count(path_uuid(self, "record_id"), now)
        if upcoming == 0:
            return ""
        counted = f"{upcoming} upcoming appointment{'' if upcoming == 1 else 's'}"
        return (
            f"This hospital has {counted}. Changing the time zone moves nothing that is stored, "
            "but its availability is read in the new zone from then on."
        )


class RecordDeletePage(RecordPage):
    template_name = "admin/delete.html"

    def get(self, request: HttpRequest, **_path: object) -> HttpResponse:
        record = self.record_or_404()
        return self._confirmation(request, record, dependents_of(self.kind, record.pk))

    def post(self, request: HttpRequest, **_path: object) -> HttpResponse:
        assert self.user is not None  # noqa: S101 - allowed_roles guarantees a signed-in user
        record_id: UUID = path_uuid(self, "record_id")
        result = delete_record(self.kind, record_id, self.user)
        if not isinstance(result, Failure):
            return HttpResponseRedirect(self.view.base_path, status=303)
        if result.code != FailureCode.HAS_DEPENDENTS:
            return self.refusal_of(request, result)
        reasons = result.details["dependents"]
        return self._confirmation(
            request, self.record_or_404(), reasons if isinstance(reasons, list) else [], 409
        )

    def _confirmation(
        self, request: HttpRequest, record: Model, reasons: list[str], status: int = 200
    ) -> HttpResponse:
        context = {
            "view": self.view,
            "record": record,
            "reasons": reasons,
            "action": request.path,
            "back_path": f"{self.view.base_path}/{record.pk}",
            "current": self.view.path_name,
        }
        return self.page(request, context, status)


def admin_record_routes() -> list[URLPattern]:
    routes: list[URLPattern] = []
    for kind, view in KIND_VIEWS.items():
        base = f"admin-console/{view.path_name}"
        routes += [
            path(base, RecordListPage.as_view(kind=kind)),
            path(f"{base}/new", RecordFormPage.as_view(kind=kind)),
            path(f"{base}/<uuid:record_id>", RecordShowPage.as_view(kind=kind)),
            path(f"{base}/<uuid:record_id>/edit", RecordFormPage.as_view(kind=kind)),
            path(f"{base}/<uuid:record_id>/delete", RecordDeletePage.as_view(kind=kind)),
        ]
    return routes
