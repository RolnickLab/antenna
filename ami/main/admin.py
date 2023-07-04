from django.contrib import admin

from .models import BlogPost, Deployment, Project, SourceImage


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin[BlogPost]):
    """Admin panel example for ``BlogPost`` model."""


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin[Project]):
    """Admin panel example for ``Project`` model."""


@admin.register(Deployment)
class DeploymentAdmin(admin.ModelAdmin[Deployment]):
    """Admin panel example for ``Deployment`` model."""


@admin.register(SourceImage)
class SourceImageAdmin(admin.ModelAdmin[SourceImage]):
    """Admin panel example for ``SourceImage`` model."""
