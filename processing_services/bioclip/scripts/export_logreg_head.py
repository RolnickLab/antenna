"""
Convert a trained sklearn LogisticRegression probe into the two files this service needs:

  1. an npz holding the linear head, as W, b and classes
  2. a label map JSON, keyed by class value, with species_name and inat_taxon_id

Upload both to the Hugging Face repo named by BioCLIP25LogRegClassifier.head_repo_id.
The service downloads them from there with huggingface_hub.hf_hub_download.

This is the same layout the Newfoundland trap classifier demo publishes, so a head
exported here can be dropped in next to the existing one without a second format.

The head is fit on L2-normalised BioCLIP image embeddings, so softmax(x @ W.T + b)
reproduces sklearn's multinomial predict_proba exactly. This script verifies that
numerically before writing anything.

Example:

    python scripts/export_logreg_head.py \
        --classifier probe.joblib \
        --labels species_labels.csv \
        --model-name hf-hub:imageomics/bioclip-2.5-vith14 \
        --out-head logreg_head.npz \
        --out-labels label_map.json

--labels is a CSV with a `class` column matching the classifier's own class values
(clf.classes_, e.g. iNat taxon ids) and a `label` column with the name Antenna should
show. An optional `inat_taxon_id` column is passed through; it defaults to the class
value, which is already the iNat taxon id in the existing heads.
"""

import argparse
import csv
import json
from pathlib import Path

import numpy as np


def load_classifier(path: Path):
    if path.suffix == ".joblib":
        import joblib

        return joblib.load(path)

    import pickle

    with open(path, "rb") as f:
        return pickle.load(f)


def load_label_rows(path: Path) -> dict[str, dict]:
    """Map the classifier's class value (as a string) to its category metadata."""
    if path.suffix == ".json":
        rows = json.loads(path.read_text())
    else:
        with open(path, newline="") as f:
            rows = list(csv.DictReader(f))

    label_rows = {}
    for row in rows:
        if "class" not in row or "label" not in row:
            raise ValueError(f"Each row of {path} needs at least a 'class' and a 'label' column, got: {row}")
        label_rows[str(row["class"])] = row
    return label_rows


def verify_softmax_equivalence(clf, embed_dim: int, tolerance: float = 1e-6) -> None:
    """
    sklearn's one-vs-rest mode produces per-class sigmoids that are then renormalised,
    which a single softmax cannot reproduce. Catch that here rather than in production.
    """
    rng = np.random.default_rng(0)
    probe = rng.normal(size=(8, embed_dim))
    probe = probe / np.linalg.norm(probe, axis=1, keepdims=True)

    sklearn_proba = clf.predict_proba(probe)

    scores = probe @ clf.coef_.T + clf.intercept_
    scores = scores - scores.max(axis=1, keepdims=True)
    softmax_proba = np.exp(scores) / np.exp(scores).sum(axis=1, keepdims=True)

    max_difference = float(np.abs(sklearn_proba - softmax_proba).max())
    if max_difference > tolerance:
        raise ValueError(
            f"softmax(x @ W.T + b) differs from predict_proba by {max_difference:.2e}. "
            "The head is probably one-vs-rest, not multinomial. Refit with a multinomial "
            "solver (lbfgs or saga) so a single Linear layer can reproduce it."
        )
    print(f"Verified softmax equivalence with sklearn (max diff {max_difference:.2e})")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--classifier", type=Path, required=True, help="Pickled/joblib LogisticRegression")
    parser.add_argument("--labels", type=Path, required=True, help="CSV or JSON mapping class value -> label")
    parser.add_argument("--model-name", default="hf-hub:imageomics/bioclip-2.5-vith14")
    parser.add_argument("--out-head", type=Path, default=Path("logreg_head.npz"))
    parser.add_argument("--out-labels", type=Path, default=Path("label_map.json"))
    args = parser.parse_args()

    clf = load_classifier(args.classifier)
    num_classes, embed_dim = clf.coef_.shape
    print(f"Loaded classifier with {num_classes} classes over {embed_dim}-dim embeddings")

    if num_classes != len(clf.classes_):
        raise ValueError(
            f"Classifier has {len(clf.classes_)} classes but {num_classes} coefficient rows. "
            "Binary logistic regression is not supported; this service expects a multinomial head."
        )

    verify_softmax_equivalence(clf, embed_dim)

    label_rows = load_label_rows(args.labels)
    missing = [str(c) for c in clf.classes_ if str(c) not in label_rows]
    if missing:
        raise ValueError(f"{len(missing)} classes have no label, e.g. {missing[:5]}")

    # The label map is keyed by class value, so the service can walk `classes` in head
    # row order and look each one up.
    label_map = {}
    for class_value in clf.classes_:
        row = label_rows[str(class_value)]
        label_map[str(class_value)] = {
            "species_name": row["label"],
            "inat_taxon_id": int(row.get("inat_taxon_id") or class_value),
        }

    args.out_head.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        args.out_head,
        W=clf.coef_.astype("float32"),
        b=clf.intercept_.astype("float32"),
        classes=clf.classes_,
    )
    print(f"Wrote head to {args.out_head} (W {clf.coef_.shape}, {num_classes} classes)")

    args.out_labels.parent.mkdir(parents=True, exist_ok=True)
    args.out_labels.write_text(json.dumps(label_map, indent=2))
    print(f"Wrote {len(label_map)} labels to {args.out_labels}")


if __name__ == "__main__":
    main()
