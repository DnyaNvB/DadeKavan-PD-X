from django.contrib.auth.models import User
from django.db import models


class Profile(models.Model):
    class UserLevel(models.TextChoices):
        VIEWER = "viewer", "Viewer"
        ANALYST = "analyst", "Analyst"
        ADMIN = "admin", "Admin"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="profile",
        db_column="userId",
    )
    photo = models.ImageField(upload_to="profiles/", blank=True, null=True)
    user_level = models.CharField(
        "user level",
        max_length=20,
        choices=UserLevel.choices,
        default=UserLevel.VIEWER,
        db_column="userLevel",
    )

    class Meta:
        db_table = "userProfile"

    def __str__(self) -> str:
        return f"Profile({self.user.username})"
