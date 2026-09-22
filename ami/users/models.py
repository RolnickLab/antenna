from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import CharField, EmailField
from django.urls import reverse
from django.utils.translation import gettext_lazy as _

from ami.users.managers import UserManager


class User(AbstractUser):
    """
    Default custom user model for Automated Monitoring of Insects ML Platform.
    If adding fields that need to be filled at user signup,
    check forms.SignupForm and forms.SocialSignupForms accordingly.
    """

    # First and last name do not cover name patterns around the globe
    name = CharField(_("Name of User"), blank=True, max_length=255)
    first_name = None  # type: ignore
    last_name = None  # type: ignore
    email = EmailField(_("email address"), unique=True)
    username = None  # type: ignore
    image = models.ImageField(upload_to="users", blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def save(self, *args, **kwargs):
        if not self.email:
            raise ValueError("The Email field must be set")
        self.email = UserManager.normalize_email(self.email)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        """Get URL for user's detail view.

        Returns:
            str: URL for user detail.

        """
        # @TODO return frontend URL, not API URL
        return reverse("api:user-detail", kwargs={"id": self.pk})


class RoleSchemaVersion(models.Model):
    """
    Tracks the current role/permission schema version.
    Updated when Role classes or Project.Permissions change.
    """

    version = models.CharField(max_length=100, unique=True)
    description = models.TextField()
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"RoleSchemaVersion {self.version}"

    @classmethod
    def get_current_version(cls):
        """Get the current schema version from code."""
        import hashlib

        from ami.users.roles import Role

        role_data = []
        for role_class in sorted(Role.__subclasses__(), key=lambda r: r.__name__):
            perms = sorted(role_class.permissions)
            role_data.append(f"{role_class.__name__}:{','.join(perms)}")

        schema_str = "|".join(role_data)
        return hashlib.md5(schema_str.encode()).hexdigest()[:16]

    @classmethod
    def needs_update(cls):
        """Check if roles need updating based on schema version."""
        current = cls.get_current_version()
        try:
            latest = cls.objects.first()
            return latest is None or latest.version != current
        except Exception:
            # Table doesn't exist yet (first migration)
            return False

    @classmethod
    def mark_updated(cls, description="Schema updated"):
        """Mark schema as updated to current version."""
        current = cls.get_current_version()
        cls.objects.create(version=current, description=description)
