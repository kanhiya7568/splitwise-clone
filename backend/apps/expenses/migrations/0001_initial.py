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
            name="Expense",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("group", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="expenses",
                    to="groups.group",
                )),
                ("paid_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="expenses_paid",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("created_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="expenses_created",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("description", models.CharField(max_length=255)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("category", models.CharField(
                    choices=[
                        ("food","Food & Drink"), ("transport","Transport"),
                        ("accommodation","Accommodation"), ("entertainment","Entertainment"),
                        ("utilities","Utilities"), ("shopping","Shopping"),
                        ("health","Health"), ("travel","Travel"),
                        ("general","General"), ("other","Other"),
                    ],
                    default="general",
                    max_length=20,
                )),
                ("expense_date", models.DateField()),
                ("split_type", models.CharField(
                    choices=[
                        ("equal","Equal"), ("unequal","Unequal"),
                        ("percentage","Percentage"), ("shares","Shares"),
                    ],
                    default="equal",
                    max_length=20,
                )),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "expenses", "ordering": ["-expense_date", "-created_at"]},
        ),
        migrations.CreateModel(
            name="ExpenseSplit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("expense", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="splits",
                    to="expenses.expense",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="expense_splits",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("amount", models.DecimalField(decimal_places=2, max_digits=10)),
                ("percentage", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("shares", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "expense_splits"},
        ),
        # ── Indexes ───────────────────────────────────────────────────────────
        migrations.AddIndex(
            model_name="expense",
            index=models.Index(fields=["group", "is_deleted", "-expense_date"], name="expense_group_active_date_idx"),
        ),
        migrations.AddIndex(
            model_name="expense",
            index=models.Index(fields=["paid_by"], name="expense_paid_by_idx"),
        ),
        migrations.AddIndex(
            model_name="expense",
            index=models.Index(fields=["group", "category"], name="expense_group_category_idx"),
        ),
        migrations.AddIndex(
            model_name="expensesplit",
            index=models.Index(fields=["expense"], name="split_expense_idx"),
        ),
        migrations.AddIndex(
            model_name="expensesplit",
            index=models.Index(fields=["user"], name="split_user_idx"),
        ),
        # ── Constraints ───────────────────────────────────────────────────────
        migrations.AddConstraint(
            model_name="expense",
            constraint=models.CheckConstraint(
                check=models.Q(amount__gt=0) & models.Q(amount__lte=999999.99),
                name="expense_amount_positive_and_bounded",
            ),
        ),
        migrations.AddConstraint(
            model_name="expensesplit",
            constraint=models.UniqueConstraint(
                fields=["expense", "user"],
                name="unique_split_per_expense_user",
            ),
        ),
        migrations.AddConstraint(
            model_name="expensesplit",
            constraint=models.CheckConstraint(
                check=models.Q(amount__gte=0),
                name="split_amount_non_negative",
            ),
        ),
    ]
