"""
Retrain the classifier head from labels people verified in Antenna.

The backbone is frozen, so a head is just a linear layer over stored embeddings. Antenna
already holds those embeddings, so nothing here touches an image: pull rows, fit a head,
score it against the one in service, and keep the new one only if it wins.
"""

import dataclasses
import datetime
import json
import logging
import pathlib
import tempfile
import typing

import numpy as np
import requests
import torch

logger = logging.getLogger(__name__)

# A new head must beat the incumbent STRICTLY, by more than this margin. A tie must not
# promote: swapping heads is not free (it invalidates comparisons against past results), so
# an equal score is not a reason to change.
DEFAULT_MIN_IMPROVEMENT = 0.0

# Below this many held-out rows the comparison is noise, not evidence. The run still
# reports its numbers, but says plainly that they cannot support a decision.
MIN_MEANINGFUL_TEST_ROWS = 30

# The head shapes this service can fit. Only "linear" for now: the serving path loads a
# single Linear layer, so anything else would train fine and then fail to load. An MLP-1
# head scores far better on rare species and is worth adding, but it needs the loader too.
SUPPORTED_HEAD_TYPES = ("linear",)


class NotEnoughData(Exception):
    """Raised when the verified data cannot support both training and evaluation."""


class UnsupportedHeadType(Exception):
    """Raised when asked for a head shape this service cannot fit or serve."""


@dataclasses.dataclass
class TrainingRow:
    detection_id: int
    label: str
    split: str
    features: np.ndarray


def fetch_dataset(url: str, timeout: int = 300, session: requests.Session | None = None) -> tuple[list[TrainingRow], dict]:
    """
    Download the training set Antenna prepared and unpack it.

    An npz of float16 vectors rather than JSON rows: the values are stored as two bytes in
    Postgres, so float16 loses nothing, and it is roughly ten times smaller and far faster
    to parse than the equivalent JSON.
    """
    session = session or requests.Session()
    response = session.get(url, timeout=timeout, stream=True)
    response.raise_for_status()

    with tempfile.NamedTemporaryFile(suffix=".npz") as handle:
        for chunk in response.iter_content(chunk_size=1 << 20):
            handle.write(chunk)
        handle.flush()
        archive = np.load(handle.name, allow_pickle=True)

        metadata = json.loads(str(archive["metadata"]))
        classes = [str(c) for c in archive["classes"]]
        features = archive["features"]
        labels = archive["labels"]
        detection_ids = archive["detection_ids"]
        splits = archive["split"]

    rows = [
        TrainingRow(
            detection_id=int(detection_id),
            label=classes[int(label)],
            split=str(split),
            features=vector,
        )
        for detection_id, label, split, vector in zip(detection_ids, labels, splits, features)
    ]
    logger.info(f"Loaded {len(rows)} training rows over {len(classes)} species from {url}")
    return rows, metadata


def _matrices(rows: list[TrainingRow], labels: list[str]) -> tuple[np.ndarray, np.ndarray]:
    index = {name: i for i, name in enumerate(labels)}
    x = np.asarray([r.features for r in rows], dtype=np.float32)
    y = np.asarray([index[r.label] for r in rows], dtype=np.int64)
    return x, y


def warm_start(
    head: torch.nn.Linear,
    labels: list[str],
    incumbent: dict[str, typing.Any] | None,
) -> int:
    """
    Copy the current head's weights for any species they have in common.

    Without this a retrain starts from noise, so every species with no new verified crops
    comes out worse than before. Seeding from the incumbent makes a retrain additive: a
    species nobody verified this time keeps exactly what it already knew.

    Returns how many classes were seeded.
    """
    if not incumbent:
        return 0
    index = {name: i for i, name in enumerate(incumbent["labels"])}
    weights = incumbent["weights"]
    bias = incumbent["bias"]

    seeded = 0
    with torch.no_grad():
        for i, name in enumerate(labels):
            source = index.get(name)
            if source is None:
                continue
            head.weight[i] = torch.from_numpy(np.asarray(weights[source], dtype=np.float32))
            head.bias[i] = float(bias[source])
            seeded += 1
    logger.info(f"Warm-started {seeded} of {len(labels)} classes from the current head")
    return seeded


def restore_untrained_classes(
    weights: np.ndarray,
    bias: np.ndarray,
    labels: list[str],
    trained_counts: dict[str, int],
    incumbent: dict[str, typing.Any] | None,
) -> int:
    """
    Put back the current head's weights for species that had no training rows.

    Warm-starting alone is not enough: cross-entropy still pushes those classes around as
    negatives over hundreds of epochs, so they drift away from what they knew. Copying them
    back afterwards is what actually makes a retrain additive.

    Returns how many classes were restored.
    """
    if not incumbent:
        return 0
    index = {name: i for i, name in enumerate(incumbent["labels"])}
    restored = 0
    for i, name in enumerate(labels):
        if trained_counts.get(name):
            continue
        source = index.get(name)
        if source is None:
            continue
        weights[i] = np.asarray(incumbent["weights"][source], dtype=weights.dtype)
        bias[i] = incumbent["bias"][source]
        restored += 1
    if restored:
        logger.info(f"Restored {restored} class(es) that had no verified crops this run")
    return restored


def train_linear_head(
    x: np.ndarray,
    y: np.ndarray,
    num_classes: int,
    epochs: int = 300,
    learning_rate: float = 0.01,
    weight_decay: float = 1e-4,
    device: str = "cpu",
    labels: list[str] | None = None,
    incumbent: dict[str, typing.Any] | None = None,
) -> torch.nn.Linear:
    """
    Fit a single linear layer over frozen embeddings.

    Deliberately the same shape as the head already in service (a Linear over L2-normalised
    BioCLIP features), so a retrained head is a drop-in replacement rather than a different
    kind of model that would need its own serving path.
    """
    head = torch.nn.Linear(x.shape[1], num_classes).to(device)
    if labels:
        warm_start(head, labels, incumbent)
    optimizer = torch.optim.AdamW(head.parameters(), lr=learning_rate, weight_decay=weight_decay)
    loss_fn = torch.nn.CrossEntropyLoss()

    inputs = torch.from_numpy(x).to(device)
    targets = torch.from_numpy(y).to(device)

    head.train()
    for epoch in range(epochs):
        optimizer.zero_grad()
        loss = loss_fn(head(inputs), targets)
        loss.backward()
        optimizer.step()
        if epoch % 50 == 0:
            logger.debug(f"epoch {epoch} loss {loss.item():.4f}")
    head.eval()
    return head


def evaluate(
    weights: np.ndarray,
    bias: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
) -> dict[str, float]:
    """Top-1 and macro recall. Macro matters because trap data is heavily long-tailed."""
    logits = x @ weights.T + bias
    predicted = logits.argmax(axis=1)
    correct = predicted == y

    per_class = []
    for cls in np.unique(y):
        mask = y == cls
        per_class.append(float(correct[mask].mean()))

    return {
        "top1": float(correct.mean()),
        "macro_recall": float(np.mean(per_class)) if per_class else 0.0,
        "n": int(len(y)),
        "classes": int(len(np.unique(y))),
    }


def score_incumbent(
    incumbent_weights: np.ndarray,
    incumbent_bias: np.ndarray,
    incumbent_labels: list[str],
    rows: list[TrainingRow],
) -> dict[str, float] | None:
    """
    Score the head currently in service on the same held-out rows.

    Only rows whose species the incumbent can actually predict are counted. Scoring it on
    species it was never trained to output would understate it and make any new head look
    better than it is.
    """
    index = {name: i for i, name in enumerate(incumbent_labels)}
    usable = [r for r in rows if r.label in index]
    if not usable:
        return None
    x = np.asarray([r.features for r in usable], dtype=np.float32)
    y = np.asarray([index[r.label] for r in usable], dtype=np.int64)
    result = evaluate(incumbent_weights, incumbent_bias, x, y)
    result["skipped_unknown_species"] = len(rows) - len(usable)
    return result


def retrain(
    rows: list[TrainingRow],
    incumbent: dict[str, typing.Any] | None = None,
    min_per_species: int = 2,
    min_improvement: float = DEFAULT_MIN_IMPROVEMENT,
    device: str = "cpu",
    declared_classes: list[str] | None = None,
    epochs: int = 300,
    learning_rate: float = 0.01,
    weight_decay: float = 1e-4,
    head_type: str = "linear",
) -> dict[str, typing.Any]:
    """
    Fit a new head and decide whether it deserves to replace the current one.

    Returns the metrics, the decision, and the new head's weights. It does not write
    anything: publishing is a separate, deliberate step.
    """
    if head_type not in SUPPORTED_HEAD_TYPES:
        # Refused rather than ignored: silently fitting a different shape than the caller
        # asked for would produce a head nobody could explain.
        raise UnsupportedHeadType(
            f"This service cannot fit a '{head_type}' head. Supported: {', '.join(SUPPORTED_HEAD_TYPES)}."
        )
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.label] = counts.get(row.label, 0) + 1

    if declared_classes:
        # Antenna decided the species list, usually from a project's taxa list. Honour it:
        # a species with no verified crops this run still needs a column, or the head would
        # quietly stop predicting it. Its weights come from the current head instead.
        labels = sorted(declared_classes)
    else:
        labels = sorted(name for name, n in counts.items() if n >= min_per_species)
    if not labels:
        raise NotEnoughData(
            f"No species has at least {min_per_species} verified crops. "
            f"Verify more occurrences before retraining. Counts: {counts}"
        )

    label_set = set(labels)
    kept = [r for r in rows if r.label in label_set]
    train_rows = [r for r in kept if r.split == "train"]
    test_rows = [r for r in kept if r.split == "test"]
    if not train_rows:
        raise NotEnoughData("The train split is empty.")
    if not test_rows:
        raise NotEnoughData(
            "The test split is empty, so a new head cannot be compared against the current one. "
            "Verify more occurrences."
        )

    x_train, y_train = _matrices(train_rows, labels)
    x_test, y_test = _matrices(test_rows, labels)

    head = train_linear_head(
        x_train,
        y_train,
        num_classes=len(labels),
        device=device,
        labels=labels,
        incumbent=incumbent,
        epochs=epochs,
        learning_rate=learning_rate,
        weight_decay=weight_decay,
    )
    weights = head.weight.detach().cpu().numpy()
    bias = head.bias.detach().cpu().numpy()

    trained_counts: dict[str, int] = {}
    for row in train_rows:
        trained_counts[row.label] = trained_counts.get(row.label, 0) + 1
    restored = restore_untrained_classes(weights, bias, labels, trained_counts, incumbent)

    candidate = evaluate(weights, bias, x_test, y_test)
    incumbent_metrics = None
    if incumbent:
        incumbent_metrics = score_incumbent(
            incumbent["weights"], incumbent["bias"], incumbent["labels"], test_rows
        )

    if incumbent_metrics is None:
        promote = False
        reason = "No incumbent head was scored, so the new head is not promoted automatically."
    elif candidate["top1"] > incumbent_metrics["top1"] + min_improvement:
        promote = True
        reason = (
            f"New head top-1 {candidate['top1']:.3f} beats current {incumbent_metrics['top1']:.3f} "
            f"by more than {min_improvement:.3f}."
        )
    else:
        promote = False
        reason = (
            f"New head top-1 {candidate['top1']:.3f} does not beat current "
            f"{incumbent_metrics['top1']:.3f} by more than {min_improvement:.3f}."
        )

    warnings: list[str] = []
    if len(test_rows) < MIN_MEANINGFUL_TEST_ROWS:
        warnings.append(
            f"Only {len(test_rows)} held-out row(s). Anything under {MIN_MEANINGFUL_TEST_ROWS} is too "
            "few to tell two heads apart, so treat this result as a smoke test, not evidence."
        )
    if incumbent_metrics and incumbent_metrics.get("skipped_unknown_species"):
        warnings.append(
            f"{incumbent_metrics['skipped_unknown_species']} held-out row(s) name species the current "
            "head cannot predict, so they were left out of its score. The two heads were not scored on "
            "identical rows."
        )
    if len(labels) < 5:
        warnings.append(
            f"The new head covers only {len(labels)} species. The head in service covers far more, so "
            "promoting this one would narrow what the pipeline can predict."
        )

    return {
        "labels": labels,
        "weights": weights,
        "bias": bias,
        "counts": {name: counts.get(name, 0) for name in labels},
        "dropped_species": sorted(set(counts) - label_set),
        "rows": {"total": len(rows), "kept": len(kept), "train": len(train_rows), "test": len(test_rows)},
        "classes_restored_from_current_head": restored,
        "candidate_metrics": candidate,
        "incumbent_metrics": incumbent_metrics,
        "promote": promote,
        "reason": reason,
        "warnings": warnings,
        "trained_at": datetime.datetime.now().isoformat(),
    }


def save_head(result: dict[str, typing.Any], directory: pathlib.Path, name: str) -> dict[str, str]:
    """
    Write the head in the same format the service already loads (npz + label_map.json).

    Written under its own name rather than overwriting the current head: Antenna keys
    algorithms by key, and a head that is swapped in place makes past classifications
    impossible to attribute.
    """
    directory.mkdir(parents=True, exist_ok=True)
    head_path = directory / f"{name}.npz"
    labels_path = directory / f"{name}.label_map.json"

    np.savez(
        head_path,
        W=result["weights"],
        b=result["bias"],
        # A plain string array, not dtype=object. An object array can only be read back
        # with allow_pickle=True, and the loader that serves these heads does not set it.
        classes=np.array([str(label) for label in result["labels"]]),
    )
    labels_path.write_text(
        json.dumps(
            {
                "labels": result["labels"],
                "counts": result["counts"],
                "metrics": result["candidate_metrics"],
                "trained_at": result["trained_at"],
            },
            indent=2,
        )
    )
    return {"head": str(head_path), "labels": str(labels_path)}
