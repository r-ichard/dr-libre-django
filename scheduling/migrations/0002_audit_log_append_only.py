from django.db import migrations

CREATE = """
CREATE FUNCTION scheduling_refuse_audit_change() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'audit log entries are append-only';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER scheduling_auditlogentry_refuse_row_change
    BEFORE UPDATE OR DELETE ON scheduling_auditlogentry
    FOR EACH ROW EXECUTE FUNCTION scheduling_refuse_audit_change();

CREATE TRIGGER scheduling_auditlogentry_refuse_truncate
    BEFORE TRUNCATE ON scheduling_auditlogentry
    FOR EACH STATEMENT EXECUTE FUNCTION scheduling_refuse_audit_change();
"""

DROP = """
DROP TRIGGER scheduling_auditlogentry_refuse_truncate ON scheduling_auditlogentry;
DROP TRIGGER scheduling_auditlogentry_refuse_row_change ON scheduling_auditlogentry;
DROP FUNCTION scheduling_refuse_audit_change();
"""


class Migration(migrations.Migration):
    dependencies = [("scheduling", "0001_initial")]
    operations = [migrations.RunSQL(CREATE, reverse_sql=DROP)]
