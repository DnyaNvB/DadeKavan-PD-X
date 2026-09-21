from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(
            name="Profile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("photo", models.ImageField(blank=True, null=True, upload_to="profiles/")),
                (
                    "user_level",
                    models.CharField(
                        choices=[("viewer", "Viewer"), ("analyst", "Analyst"), ("admin", "Admin")],
                        db_column="userLevel",
                        default="viewer",
                        max_length=20,
                        verbose_name="user level",
                    ),
                ),
                (
                    "user",
                    models.OneToOneField(
                        db_column="userId",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="profile",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"db_table": "userProfile"},
        )
    ]
