import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("groups", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Settlement",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("group", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="settlements",
                    to="groups.group",
                )),
                ("payer", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="settlements_paid",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("receiver", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="settlements_received",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("created_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="settlements_created",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("note", models.TextField(blank=True, default="")),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "settlements", "ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="settlement",
            index=models.Index(fields=["group", "is_deleted"], name="settlement_group_active_idx"),
        ),
        migrations.AddIndex(
            model_name="settlement",
            index=models.Index(fields=["payer"], name="settlement_payer_idx"),
        ),
        migrations.AddIndex(
            model_name="settlement",
            index=models.Index(fields=["receiver"], name="settlement_receiver_idx"),
        ),
        migrations.AddConstraint(
            model_name="settlement",
            constraint=models.CheckConstraint(
                check=models.Q(amount__gt=0) & models.Q(amount__lte=999999.99),
                name="settlement_amount_positive_and_bounded",
            ),
        ),
        migrations.AddConstraint(
            model_name="settlement",
            constraint=models.CheckConstraint(
                check=~models.Q(payer_id=models.F("receiver_id")),
                name="settlement_payer_ne_receiver",
            ),
        ),
    ]
