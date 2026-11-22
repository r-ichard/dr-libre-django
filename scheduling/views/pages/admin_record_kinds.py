"""Section 10: what each of the five admin records shows and asks for. The pages read this table;
none of them names a record."""

from dataclasses import dataclass

TEXT = "text"
NUMBER = "number"
TEXTAREA = "textarea"
SELECT = "select"
CHECKBOX = "checkbox"
PASSWORD = "password"  # noqa: S105 - a widget name, not a secret
CONSOLE_PATH = "/admin-console"


@dataclass(frozen=True)
class FormField:
    name: str
    label: str
    widget: str = TEXT
    hint: str = ""


@dataclass(frozen=True)
class KindView:
    kind: str
    path_name: str
    singular: str
    plural: str
    fields: tuple[FormField, ...]
    columns: tuple[tuple[str, str], ...]
    new_text: str
    title_accessor: str = "name"
    identifier_accessor: str = "code"
    identifier_label: str = "Code"
    search_label: str = "Search by name or code"
    has_deactivate: bool = False
    has_calendar: bool = False

    @property
    def base_path(self) -> str:
        return f"{CONSOLE_PATH}/{self.path_name}"


NAME = FormField("name", "Name")
CODE = FormField("code", "Code")
ACTIVE = FormField("is_active", "Active", CHECKBOX)
DESCRIPTION = FormField("description", "Description", TEXTAREA)
ACTIVE_COLUMN = ("Status", "is_active")

KIND_VIEWS = {
    view.kind: view
    for view in (
        KindView(
            "hospital", "hospitals", "hospital", "hospitals",
            (
                NAME, CODE, DESCRIPTION,
                FormField("street_address", "Street address"),
                FormField("postal_code", "Postal code"),
                FormField("city", "City"),
                FormField("country", "Country"),
                FormField("phone", "Phone"),
                FormField("time_zone", "Time zone", SELECT),
                FormField("latitude", "Latitude", hint="Optional. For example 48.8566."),
                FormField("longitude", "Longitude", hint="Optional. For example 2.3522."),
                ACTIVE,
            ),
            (("City", "city"), ACTIVE_COLUMN),
            "New hospital",
        ),
        KindView(
            "specialty", "specialties", "specialty", "specialties",
            (NAME, CODE, ACTIVE),
            (ACTIVE_COLUMN,),
            "New specialty",
        ),
        KindView(
            "department", "departments", "department", "departments",
            (NAME, CODE, FormField("hospital", "Hospital", SELECT), DESCRIPTION),
            (("Hospital", "hospital.name"),),
            "New department",
        ),
        KindView(
            "room", "rooms", "room", "rooms",
            (
                NAME, CODE, FormField("department", "Department", SELECT),
                FormField("floor", "Floor"),
                FormField("capacity", "Capacity", NUMBER),
                FormField("equipment", "Equipment", TEXTAREA, "One item on each line."),
                ACTIVE,
            ),
            (("Department", "department.name"), ACTIVE_COLUMN),
            "New room",
        ),
        KindView(
            "appointment_type", "appointment-types", "appointment type", "appointment types",
            (
                NAME, CODE, FormField("department", "Department", SELECT),
                FormField("duration_minutes", "Duration in minutes", NUMBER),
                FormField("buffer_minutes", "Buffer in minutes", NUMBER),
                FormField("colour", "Colour", hint="Shown on the calendar. For example #1a2b3c."),
                FormField("needs_room", "Needs a room", CHECKBOX),
                FormField("is_bookable_online", "Bookable online", CHECKBOX),
                ACTIVE,
            ),
            (("Department", "department.name"), ("Minutes", "duration_minutes"), ACTIVE_COLUMN),
            "New appointment type",
        ),
        KindView(
            "user", "users", "user", "users",
            (
                FormField("full_name", "Name"),
                FormField("email", "Email"),
                FormField("role", "Role", SELECT),
                FormField(
                    "password", "Temporary password", PASSWORD,
                    "10 to 72 characters. Tell the person to change it after the first sign-in.",
                ),
                ACTIVE,
            ),
            (("Role", "role"), ACTIVE_COLUMN),
            "New user",
            "full_name", "email", "Email", "Search by name or email", has_deactivate=True,
        ),
        KindView(
            "clinician", "clinicians", "clinician", "clinicians",
            (
                FormField("user", "Clinician user", SELECT),
                FormField("department", "Department", SELECT),
                FormField("specialty", "Specialty", SELECT),
                FormField("title", "Title"),
                FormField("bio", "Bio", TEXTAREA, "Optional."),
                FormField("default_room", "Default room", SELECT, "Optional."),
                FormField("round_robin_weight", "Round-robin weight", NUMBER, "Whole number, 1+."),
            ),
            (
                ("Department", "department.name"),
                ("Specialty", "specialty.name"),
                ("Status", "user.is_active"),
                ("Weekly availability", "extra"),
            ),
            "Attach a clinician profile",
            "user.full_name", "title", "Title", "Search by name, email or title",
            has_calendar=True,
        ),
    )
}  # fmt: skip
