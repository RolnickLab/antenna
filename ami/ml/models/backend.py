from django.db import models


class Backend(models.Model):
    """An ML processing backend"""

    projects = models.ManyToManyField("main.Project", related_name="backends", blank=True)
    endpoint_url = models.CharField(max_length=1024, null=True, blank=True)

    def __str__(self):
        return self.endpoint_url

    class Meta:
        verbose_name = "Backend"
        verbose_name_plural = "Backends"
