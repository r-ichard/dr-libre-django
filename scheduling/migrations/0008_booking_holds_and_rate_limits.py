import django.db.models.deletion
import django.db.models.functions.text
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models

import scheduling.identifiers


class Migration(migrations.Migration):

    dependencies = [
        ('scheduling', '0007_notification_email_pending'),
    ]

    operations = [
        # Nothing created these rows before task 12, and a hold without a record of accepted terms or
        # a code without its hold must not be invented, so the few development rows go.
        migrations.RunSQL(
            "DELETE FROM scheduling_verificationcode; DELETE FROM scheduling_bookinghold;",
            migrations.RunSQL.noop,
        ),
        migrations.AddField(
            model_name='bookinghold',
            name='terms_accepted_at',
            field=models.DateTimeField(default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AddConstraint(
            model_name='bookinghold',
            constraint=models.UniqueConstraint(fields=('visitor_email',), name='bookinghold_visitor_email_unique', violation_error_message='visitor_email has a hold'),
        ),
        migrations.AddField(
            model_name='user',
            name='terms_accepted_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='verificationcode',
            name='hold',
            field=models.OneToOneField(default=None, on_delete=django.db.models.deletion.PROTECT, to='scheduling.bookinghold'),
            preserve_default=False,
        ),
        migrations.CreateModel(
            name='RateLimitHit',
            fields=[
                ('id', models.UUIDField(default=scheduling.identifiers.new_identifier, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('scope', models.CharField(choices=[('hold', 'Hold'), ('code', 'Code')], max_length=20)),
                ('key_hash', models.CharField(max_length=64)),
                ('hit_at', models.DateTimeField()),
                ('created_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name='+', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddIndex(
            model_name='ratelimithit',
            index=models.Index(fields=['scope', 'key_hash', 'hit_at'], name='ratelimithit_key_time'),
        ),
        migrations.AddConstraint(
            model_name='ratelimithit',
            constraint=models.CheckConstraint(condition=models.Q(models.lookups.Exact(django.db.models.functions.text.Length('key_hash'), 64)), name='ratelimithit_key_hash_64_characters', violation_error_message='key_hash must be exactly 64 characters'),
        ),
        migrations.AddConstraint(
            model_name='ratelimithit',
            constraint=models.CheckConstraint(condition=models.Q(('scope__in', ['hold', 'code'])), name='ratelimithit_scope_listed', violation_error_message='scope must be one of hold, code'),
        ),
    ]
