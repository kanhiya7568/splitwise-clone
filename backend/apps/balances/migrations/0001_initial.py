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
            name="Balance",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("group", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="balances",
                    to="groups.group",
                )),
                ("user1", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="balances_as_user1",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("user2", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="balances_as_user2",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("net_amount", models.DecimalField(decimal_places=2, default="0.00", max_digits=12)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "balances"},
        ),
        migrations.AddIndex(
            model_name="balance",
            index=models.Index(fields=["group", "user1"], name="balance_group_user1_idx"),
        ),
        migrations.AddIndex(
            model_name="balance",
            index=models.Index(fields=["group", "user2"], name="balance_group_user2_idx"),
        ),
        migrations.AddConstraint(
            model_name="balance",
            constraint=models.UniqueConstraint(
                fields=["group", "user1", "user2"],
                name="unique_balance_per_group_user_pair",
            ),
        ),
        migrations.AddConstraint(
            model_name="balance",
            constraint=models.CheckConstraint(
                check=models.Q(user1_id__lt=models.F("user2_id")),
                name="balance_user1_id_lt_user2_id",
            ),
        ),
    ]
