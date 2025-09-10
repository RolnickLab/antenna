# Generated on 2025-09-09 for merging duplicate AlgorithmCategoryMaps

from django.db import migrations
from django.db.models import Count
import logging
import json


logger = logging.getLogger(__name__)


def merge_duplicate_category_maps(apps, schema_editor):
    """
    Find duplicate AlgorithmCategoryMaps based on their `data` field,
    compare them (description, version, associated Algorithms, associated Classifications),
    choose a keeper, then reassign Classifications and Algorithms to use the keeper.
    Then delete the duplicates.
    """
    AlgorithmCategoryMap = apps.get_model("ml", "AlgorithmCategoryMap")
    Algorithm = apps.get_model("ml", "Algorithm")
    Classification = apps.get_model("main", "Classification")

    # Group category maps by their data content (JSON field)
    # We'll use a dictionary to group by serialized data
    data_groups = {}

    for category_map in AlgorithmCategoryMap.objects.all():
        # Normalize the data for comparison by converting to a sorted JSON string
        normalized_data = json.dumps(category_map.data, sort_keys=True)

        if normalized_data not in data_groups:
            data_groups[normalized_data] = []
        data_groups[normalized_data].append(category_map)

    # Process each group that has duplicates
    duplicates_found = 0
    maps_merged = 0

    for normalized_data, category_maps in data_groups.items():
        if len(category_maps) <= 1:
            continue  # Skip groups with only one category map

        duplicates_found += len(category_maps) - 1
        logger.info(f"Found {len(category_maps)} duplicate category maps with data hash")

        # Choose the keeper - prioritize by:
        # 1. Has description
        # 2. Has version
        # 3. Most associated algorithms
        # 4. Most associated classifications
        # 5. Earliest created (as tie-breaker)

        def score_category_map(cm):
            score = 0

            # Has description
            if cm.description:
                score += 1000

            # Has version
            if cm.version:
                score += 500

            # Count associated algorithms
            algorithm_count = Algorithm.objects.filter(category_map=cm).count()
            score += algorithm_count * 100

            # Count associated classifications
            classification_count = Classification.objects.filter(category_map=cm).count()
            score += classification_count * 10

            # Prefer older records (negative timestamp for sorting)
            score -= cm.created_at.timestamp() / 1000000  # Small adjustment for tie-breaking

            return score

        # Sort by score (highest first) and pick the keeper
        sorted_maps = sorted(category_maps, key=score_category_map, reverse=True)
        keeper = sorted_maps[0]
        duplicates = sorted_maps[1:]

        logger.info(f"Keeping category map #{keeper.pk}, merging {len(duplicates)} duplicates")

        # Merge data from duplicates to keeper
        for duplicate in duplicates:
            # Update algorithms pointing to the duplicate
            algorithms_updated = Algorithm.objects.filter(category_map=duplicate).update(category_map=keeper)
            logger.info(f"Updated {algorithms_updated} algorithms from category map #{duplicate.pk} to #{keeper.pk}")

            # Update classifications pointing to the duplicate
            classifications_updated = Classification.objects.filter(category_map=duplicate).update(category_map=keeper)
            logger.info(
                f"Updated {classifications_updated} classifications from category map #{duplicate.pk} to #{keeper.pk}"
            )

            # If duplicate has better description or version, update keeper
            if not keeper.description and duplicate.description:
                keeper.description = duplicate.description
                logger.info(f"Updated keeper description from duplicate #{duplicate.pk}")

            if not keeper.version and duplicate.version:
                keeper.version = duplicate.version
                logger.info(f"Updated keeper version from duplicate #{duplicate.pk}")

            if not keeper.uri and duplicate.uri:
                keeper.uri = duplicate.uri
                logger.info(f"Updated keeper URI from duplicate #{duplicate.pk}")

        # Save keeper with any merged data
        keeper.save()

        # Delete the duplicates
        for duplicate in duplicates:
            logger.info(f"Deleting duplicate category map #{duplicate.pk}")
            duplicate.delete()

        maps_merged += len(duplicates)

    logger.info(
        f"Migration completed: {duplicates_found} duplicates found, {maps_merged} category maps merged and deleted"
    )


def reverse_merge_duplicate_category_maps(apps, schema_editor):
    """
    This migration cannot be easily reversed since we deleted duplicate data.
    The reverse operation would require restoring the deleted category maps
    and reassigning relationships, which is not feasible without backup data.
    """
    raise NotImplementedError(
        "This migration cannot be reversed as it permanently deletes duplicate "
        "AlgorithmCategoryMap instances. If you need to reverse this, restore from a backup."
    )


class Migration(migrations.Migration):
    dependencies = [
        ("ml", "0022_alter_pipeline_default_config"),
        ("main", "0053_alter_classification_algorithm"),  # Ensure Classification model is available
    ]

    operations = [
        migrations.RunPython(
            merge_duplicate_category_maps,
            reverse_merge_duplicate_category_maps,
        ),
    ]
