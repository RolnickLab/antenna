# Generated on 2025-09-09 for fixing unlinked Classifications

from django.db import migrations
import logging


logger = logging.getLogger(__name__)


def fix_unlinked_classifications(apps, schema_editor):
    """
    Fix classifications that are missing category_map references but have
    algorithms with category_maps. This typically happens with legacy data
    created before the automatic category_map assignment was implemented.
    """
    Classification = apps.get_model("main", "Classification")

    # Find classifications that need fixing
    unlinked_classifications = Classification.objects.filter(
        category_map__isnull=True, algorithm__category_map__isnull=False
    )

    total_unlinked = unlinked_classifications.count()
    logger.info(f"Found {total_unlinked:,} classifications missing category_map but with algorithm that has one")

    if total_unlinked == 0:
        logger.info("No unlinked classifications found - migration complete")
        return

    # Group by algorithm to do bulk updates more efficiently
    algorithms_with_unlinked = unlinked_classifications.values_list("algorithm_id", flat=True).distinct()

    total_fixed = 0

    for algorithm_id in algorithms_with_unlinked:
        # Get the algorithm's category_map
        algorithm_classifications = unlinked_classifications.filter(algorithm_id=algorithm_id)
        first_classification = algorithm_classifications.first()

        if not first_classification or not first_classification.algorithm:
            continue

        category_map = first_classification.algorithm.category_map
        if not category_map:
            continue

        # Bulk update all classifications for this algorithm
        updated_count = algorithm_classifications.update(category_map=category_map)
        total_fixed += updated_count

        logger.info(
            f"Updated {updated_count:,} classifications for algorithm #{algorithm_id} to use category_map #{category_map.pk}"
        )

    logger.info(f"Migration completed: Fixed {total_fixed:,} unlinked classifications")


def reverse_fix_unlinked_classifications(apps, schema_editor):
    """
    This migration fixes data consistency issues and should not be reversed.
    However, if needed, this would set category_map back to null for classifications
    that were updated by this migration.
    """
    logger.warning("Reversing this migration would create data inconsistency - not recommended")
    # We could implement a reversal if absolutely necessary, but it's not recommended
    # since this migration fixes legitimate data consistency issues


class Migration(migrations.Migration):
    dependencies = [
        ("ml", "0023_merge_duplicate_category_maps"),
        ("main", "0053_alter_classification_algorithm"),  # Ensure Classification model is available
    ]

    operations = [
        migrations.RunPython(
            fix_unlinked_classifications,
            reverse_fix_unlinked_classifications,
        ),
    ]
