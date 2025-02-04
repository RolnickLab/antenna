from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db.models.signals import post_migrate
from django.dispatch import receiver
from guardian.shortcuts import assign_perm

from ami.main.models import Project
from ami.users.roles import Role


@receiver(post_migrate)
def create_roles(sender, **kwargs):
    """Creates predefined roles with specific permissions when the app starts."""

    project_ct = ContentType.objects.get_for_model(Project)

    # Get all Role subclasses dynamically
    for project in Project.objects.all():
        for role_class in Role.__subclasses__():
            role_name = f"{project.pk}_{project.name}_{role_class.__name__}"
            permissions = role_class.permissions

            group, _ = Group.objects.get_or_create(name=role_name)

            for perm_codename in permissions:
                permission, _ = Permission.objects.get_or_create(
                    codename=perm_codename,
                    content_type=project_ct,
                    defaults={"name": f"Can {perm_codename.replace('_', ' ')}"},
                )
                group.permissions.add(permission)
                assign_perm(perm_codename, group, project)
