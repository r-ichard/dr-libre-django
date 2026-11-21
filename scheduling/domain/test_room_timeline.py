"""Section 9.3: another clinician's appointment in a room shows only "Occupied"."""


def returns_shows_patient_name_when_own() -> None:
    from scheduling.domain.room_timeline import occupancy_label

    assert occupancy_label("Linus Linkfrei") == "Linus Linkfrei"


def returns_shows_only_occupied_when_name_not_given() -> None:
    from scheduling.domain.room_timeline import occupancy_label

    assert occupancy_label(None) == "Occupied"
