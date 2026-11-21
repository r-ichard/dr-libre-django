"""Section 9.3: another clinician's appointment in a room shows only "Occupied"."""

OCCUPIED_LABEL = "Occupied"


def occupancy_label(own_patient_name: str | None) -> str:
    return own_patient_name if own_patient_name is not None else OCCUPIED_LABEL
