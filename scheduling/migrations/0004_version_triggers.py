from django.db import migrations

VERSIONED_TABLES = [
    "scheduling_appointment",
    "scheduling_appointmenttype",
    "scheduling_auditlogentry",
    "scheduling_availabilityrule",
    "scheduling_bookinghold",
    "scheduling_clinicianprofile",
    "scheduling_department",
    "scheduling_hospital",
    "scheduling_notification",
    "scheduling_room",
    "scheduling_specialty",
    "scheduling_timeoff",
    "scheduling_user",
    "scheduling_waitlistentry",
]
SCHEDULE_TABLES = ["scheduling_availabilityrule", "scheduling_timeoff"]

FUNCTIONS = """
CREATE FUNCTION scheduling_enforce_version() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.version <> 1 THEN
        RAISE EXCEPTION 'a new row starts at version 1' USING ERRCODE = 'check_violation';
    END IF;
    IF TG_OP = 'UPDATE' AND NEW.version <> OLD.version + 1 THEN
        RAISE EXCEPTION 'a change must raise the version by exactly one'
            USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION scheduling_touch_clinician_profile() RETURNS trigger AS $$
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        UPDATE scheduling_clinicianprofile
            SET version = version + 1, updated_at = now() WHERE id = OLD.clinician_id;
    END IF;
    IF TG_OP = 'INSERT'
       OR (TG_OP = 'UPDATE' AND NEW.clinician_id IS DISTINCT FROM OLD.clinician_id) THEN
        UPDATE scheduling_clinicianprofile
            SET version = version + 1, updated_at = now() WHERE id = NEW.clinician_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION scheduling_touch_user() RETURNS trigger AS $$
BEGIN
    IF TG_OP IN ('UPDATE', 'DELETE') THEN
        UPDATE scheduling_user
            SET version = version + 1, updated_at = now() WHERE id = OLD.user_id;
    END IF;
    IF TG_OP = 'INSERT'
       OR (TG_OP = 'UPDATE' AND NEW.user_id IS DISTINCT FROM OLD.user_id) THEN
        UPDATE scheduling_user
            SET version = version + 1, updated_at = now() WHERE id = NEW.user_id;
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE scheduling_specialty_revision (
    only_row boolean PRIMARY KEY DEFAULT true CHECK (only_row),
    last_value bigint NOT NULL,
    is_called boolean NOT NULL DEFAULT true
);
INSERT INTO scheduling_specialty_revision (last_value) VALUES (1);

CREATE FUNCTION scheduling_advance_specialty_revision() RETURNS trigger AS $$
BEGIN
    UPDATE scheduling_specialty_revision SET last_value = last_value + 1;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER scheduling_touch_user
    AFTER INSERT OR DELETE ON scheduling_clinicianprofile
    FOR EACH ROW EXECUTE FUNCTION scheduling_touch_user();

CREATE TRIGGER scheduling_touch_user_on_change
    AFTER UPDATE ON scheduling_clinicianprofile
    FOR EACH ROW
    WHEN (OLD.title IS DISTINCT FROM NEW.title OR OLD.user_id IS DISTINCT FROM NEW.user_id)
    EXECUTE FUNCTION scheduling_touch_user();

CREATE TRIGGER scheduling_advance_specialty_revision
    AFTER INSERT OR UPDATE OR DELETE ON scheduling_specialty
    FOR EACH STATEMENT EXECUTE FUNCTION scheduling_advance_specialty_revision();"""

DROP_FUNCTIONS = """
DROP TRIGGER scheduling_advance_specialty_revision ON scheduling_specialty;
DROP TRIGGER scheduling_touch_user_on_change ON scheduling_clinicianprofile;
DROP TRIGGER scheduling_touch_user ON scheduling_clinicianprofile;
DROP FUNCTION scheduling_advance_specialty_revision();
DROP TABLE scheduling_specialty_revision;
DROP FUNCTION scheduling_touch_user();
DROP FUNCTION scheduling_touch_clinician_profile();
DROP FUNCTION scheduling_enforce_version();"""


def _per_table(template: str, tables: list[str]) -> str:
    return "\n".join(template.format(table=table) for table in tables)


CREATE_VERSION_TRIGGER = """
CREATE TRIGGER scheduling_enforce_version
    BEFORE INSERT OR UPDATE ON {table}
    FOR EACH ROW EXECUTE FUNCTION scheduling_enforce_version();"""
CREATE_TOUCH_TRIGGER = """
CREATE TRIGGER scheduling_touch_clinician_profile
    AFTER INSERT OR UPDATE OR DELETE ON {table}
    FOR EACH ROW EXECUTE FUNCTION scheduling_touch_clinician_profile();"""
DROP_VERSION_TRIGGER = "DROP TRIGGER scheduling_enforce_version ON {table};"
DROP_TOUCH_TRIGGER = "DROP TRIGGER scheduling_touch_clinician_profile ON {table};"

# The trigger text must run after the functions exist and, in reverse, before they are dropped.
FORWARD = (
    FUNCTIONS
    + _per_table(CREATE_VERSION_TRIGGER, VERSIONED_TABLES)
    + _per_table(CREATE_TOUCH_TRIGGER, SCHEDULE_TABLES)
)
REVERSE = (
    _per_table(DROP_TOUCH_TRIGGER, SCHEDULE_TABLES)
    + "\n"
    + _per_table(DROP_VERSION_TRIGGER, VERSIONED_TABLES)
    + DROP_FUNCTIONS
)


class Migration(migrations.Migration):
    dependencies = [("scheduling", "0003_versions_and_waitlist_link")]
    operations = [migrations.RunSQL(FORWARD, reverse_sql=REVERSE)]
