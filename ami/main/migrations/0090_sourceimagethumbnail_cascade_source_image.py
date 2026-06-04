"""Cascade SourceImageThumbnail.source_image and reap orphan rows.

Thumbnails are pure derivatives of (source_image, label). The previous
``on_delete=SET_NULL, null=True`` left rows + storage blobs orphaned whenever
their parent SourceImage was deleted, with no other reaper. CASCADE the FK so
the parent's deletion takes the row with it, and rely on the pre_delete signal
in ``ami.main.signals`` to clean the storage blob.

The migration is two-step to handle databases that already have orphan rows:

1. Delete any rows with ``source_image_id IS NULL`` (and their storage blobs
   via the model's pre_delete signal — which runs in the data migration because
   we use the live model class via ``apps.get_model`` and the signal is
   connected at import time).
2. Schema migration: AlterField to CASCADE + NOT NULL.
"""

from django.db import migrations, models


def delete_orphan_thumbnails(apps, schema_editor):
    SourceImageThumbnail = apps.get_model("main", "SourceImageThumbnail")
    # ``delete()`` on a queryset fires pre_delete per row; the signal handler in
    # ami.main.signals will clean each row's storage blob best-effort.
    orphans = SourceImageThumbnail.objects.filter(source_image__isnull=True)
    orphans.delete()


def noop_reverse(apps, schema_editor):
    # We can't recover deleted rows; reverse is intentionally a no-op so the
    # schema reverse below can still run if you're rolling back the FK change.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("main", "0089_sourceimagethumbnail_and_more"),
    ]

    operations = [
        migrations.RunPython(delete_orphan_thumbnails, reverse_code=noop_reverse),
        migrations.AlterField(
            model_name="sourceimagethumbnail",
            name="source_image",
            field=models.ForeignKey(
                on_delete=models.deletion.CASCADE,
                related_name="thumbnails",
                to="main.sourceimage",
            ),
        ),
    ]
