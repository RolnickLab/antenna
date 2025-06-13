import random

import numpy as np
from django.core.management.base import BaseCommand

from ami.main.models import Classification


class Command(BaseCommand):
    help = "Sample classifications by score quartiles and identify occurrences for human verification"

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, help="Project ID to process")
        parser.add_argument("--sample-size", type=int, default=1000, help="Initial random sample size")
        parser.add_argument("--bin-sample-size", type=int, default=50, help="Sample size from each quartile bin")
        parser.add_argument("--dry-run", action="store_true", help="Don't make any changes")

    def handle(self, *args, **options):
        project_id = options["project"]
        sample_size = options["sample_size"]
        bin_sample_size = options["bin_sample_size"]
        dry_run = options["dry_run"]

        # Get all classifications for the project
        classifications_qs = Classification.objects.select_related("detection__occurrence").filter(
            detection__source_image__project_id=project_id, score__isnull=False, detection__occurrence__isnull=False
        )

        total_classifications = classifications_qs.count()
        self.stdout.write(f"Found {total_classifications} classifications with scores and occurrences")

        if total_classifications == 0:
            self.stdout.write("No classifications found. Exiting.")
            return

        # Randomly sample detections
        sample_size = min(sample_size, total_classifications)
        self.stdout.write(f"Randomly sampling {sample_size} classifications...")

        # Get random sample
        sampled_classifications = list(classifications_qs.order_by("?")[:sample_size])

        # Extract scores for quartile calculation (filter out None values)
        scores = [c.score for c in sampled_classifications if c.score is not None]

        if not scores:
            self.stdout.write("No valid scores found. Exiting.")
            return

        # Calculate quartiles
        q1 = np.percentile(scores, 25)
        q2 = np.percentile(scores, 50)  # median
        q3 = np.percentile(scores, 75)

        self.stdout.write(f"Score quartiles: Q1={q1:.3f}, Q2={q2:.3f}, Q3={q3:.3f}")

        # Separate into bins
        bins: dict[str, list[Classification]] = {
            "Q1 (0-25%)": [],
            "Q2 (25-50%)": [],
            "Q3 (50-75%)": [],
            "Q4 (75-100%)": [],
        }

        for classification in sampled_classifications:
            score = classification.score
            if score is not None:
                if score <= q1:
                    bins["Q1 (0-25%)"].append(classification)
                elif score <= q2:
                    bins["Q2 (25-50%)"].append(classification)
                elif score <= q3:
                    bins["Q3 (50-75%)"].append(classification)
                else:
                    bins["Q4 (75-100%)"].append(classification)

        # Print bin statistics
        self.stdout.write("\nBin statistics:")
        for bin_name, bin_classifications in bins.items():
            self.stdout.write(f"  {bin_name}: {len(bin_classifications)} classifications")

        # Sample from each bin
        sampled_occurrences = set()

        self.stdout.write(f"\nSampling up to {bin_sample_size} classifications from each bin...")

        for bin_name, bin_classifications in bins.items():
            if not bin_classifications:
                self.stdout.write(f"  {bin_name}: No classifications to sample")
                continue

            # Sample from this bin
            bin_sample = random.sample(bin_classifications, min(bin_sample_size, len(bin_classifications)))

            # Extract occurrences
            bin_occurrences = {c.detection.occurrence for c in bin_sample if c.detection and c.detection.occurrence}
            sampled_occurrences.update(bin_occurrences)

            self.stdout.write(
                f"  {bin_name}: Sampled {len(bin_sample)} classifications -> {len(bin_occurrences)} occurrences"
            )

        # Print summary
        self.stdout.write("\n=== SUMMARY ===")
        self.stdout.write(f"Total unique occurrences for human verification: {len(sampled_occurrences)}")

        if sampled_occurrences:
            # Group by determination for summary
            determination_counts = {}
            score_ranges = {"min": float("inf"), "max": float("-inf")}

            for occurrence in sampled_occurrences:
                determination = occurrence.determination
                determination_name = str(determination) if determination else "Undetermined"
                determination_counts[determination_name] = determination_counts.get(determination_name, 0) + 1

                if occurrence.determination_score:
                    score_ranges["min"] = min(score_ranges["min"], occurrence.determination_score)
                    score_ranges["max"] = max(score_ranges["max"], occurrence.determination_score)

            self.stdout.write("\nOccurrences by determination:")
            for determination, count in sorted(determination_counts.items(), key=lambda x: x[1], reverse=True):
                self.stdout.write(f"  {determination}: {count}")

            if score_ranges["min"] != float("inf"):
                self.stdout.write(
                    f"\nDetermination score range: {score_ranges['min']:.3f} - {score_ranges['max']:.3f}"
                )

            # Sample occurrence details for verification
            sample_occurrences = list(sampled_occurrences)[:10]  # Show first 10 as examples
            self.stdout.write("\nSample occurrences for verification (first 10):")
            for i, occurrence in enumerate(sample_occurrences, 1):
                determination = occurrence.determination or "Undetermined"
                score = f"{occurrence.determination_score:.3f}" if occurrence.determination_score else "N/A"
                deployment = occurrence.deployment.name if occurrence.deployment else "Unknown"
                self.stdout.write(
                    f"  {i}. Occurrence #{occurrence.pk} - {determination} (score: {score}) - {deployment}"
                )

        if not dry_run:
            self.stdout.write(
                f"\n[DRY-RUN MODE] Would process {len(sampled_occurrences)} occurrences for verification"
            )
            # TODO: Add logic here to tag occurrences for verification
        else:
            self.stdout.write(
                f"\n[DRY-RUN MODE] Would process {len(sampled_occurrences)} occurrences for verification"
            )
