import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Group",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=255)),
                ("description", models.TextField(blank=True, default="")),
                ("created_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="created_groups",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("is_deleted", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "groups", "ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="GroupMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("group", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="memberships",
                    to="groups.group",
                )),
                ("user", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="group_memberships",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("role", models.CharField(
                    choices=[("admin", "Admin"), ("member", "Member")],
                    default="member",
                    max_length=20,
                )),
                ("is_active", models.BooleanField(default=True)),
                ("joined_at", models.DateTimeField(auto_now_add=True)),
                ("left_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={"db_table": "group_memberships", "ordering": ["joined_at"]},
        ),
        migrations.CreateModel(
            name="GroupInvitation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False)),
                ("group", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="invitations",
                    to="groups.group",
                )),
                ("email", models.EmailField(db_index=True)),
                ("invited_by", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="sent_invitations",
                    to=settings.AUTH_USER_MODEL,
                )),
                ("status", models.CharField(
                    choices=[
                        ("pending", "Pending"), ("accepted", "Accepted"),
                        ("declined", "Declined"), ("expired", "Expired"),
                    ],
                    db_index=True,
                    default="pending",
                    max_length=20,
                )),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("expires_at", models.DateTimeField()),
            ],
            options={"db_table": "group_invitations", "ordering": ["-created_at"]},
        ),
        # ── Indexes ──────────────────────────────────────────────────────────
        migrations.AddIndex(
            model_name="group",
            index=models.Index(fields=["created_by", "is_deleted"], name="group_creator_deleted_idx"),
        ),
        migrations.AddIndex(
            model_name="groupmembership",
            index=models.Index(fields=["group", "is_active"], name="membership_group_active_idx"),
        ),
        migrations.AddIndex(
            model_name="groupmembership",
            index=models.Index(fields=["user", "is_active"], name="membership_user_active_idx"),
        ),
        migrations.AddIndex(
            model_name="groupinvitation",
            index=models.Index(fields=["group", "status"], name="invitation_group_status_idx"),
        ),
        # ── Constraints ───────────────────────────────────────────────────────
        migrations.AddConstraint(
            model_name="groupmembership",
            constraint=models.UniqueConstraint(
                fields=["group", "user"],
                name="unique_group_user_membership",
            ),
        ),
        migrations.AddConstraint(
            model_name="groupinvitation",
            constraint=models.UniqueConstraint(
                fields=["group", "email"],
                condition=models.Q(status="pending"),
                name="unique_pending_invitation_per_group_email",
            ),
        ),
    ]
