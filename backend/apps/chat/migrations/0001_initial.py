import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ("expenses", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Message",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("expense", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="messages",
                    to="expenses.expense",
                )),
                ("sender", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="sent_messages",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("content", models.TextField(max_length=1000)),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "messages", "ordering": ["created_at"]},
        ),
        migrations.AddIndex(
            model_name="message",
            index=models.Index(fields=["expense", "created_at"], name="message_expense_time_idx"),
        ),
    ]
