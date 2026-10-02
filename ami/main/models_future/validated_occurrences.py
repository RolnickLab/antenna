"""Move what people decided about occurrences between Antenna databases.

Two kinds of human judgement attach to an occurrence: a reviewer confirmed that its
detections are one complete individual (``grouping_verified_at``), and people identified
it as a taxon (``Identification``). Both are lost when a project is re-imported or
re-processed, because every id changes. This module writes them to a portable bundle keyed
by natural keys only (``detection_matching.DetectionKey``, taxon name and GBIF key, user
email), and replays a bundle onto another database.

Replaying a confirmed occurrence means finding its detections again, moving them into one
occurrence with the same track-edit operations the review interface uses (``tracks``), and
recording the confirmation under the original reviewer and time. An occurrence whose
detections cannot all be found is reported as partial and is never confirmed: a reviewer
confirmed a complete set, not whatever subset survived.

Identifications are re-created under the original user and timestamp on the occurrence
that now holds the identified detections. Users and taxa are never created here; a missing
one is reported and its rows are skipped.

The bundle is versioned so a later schema (reviews as rows of their own) can read today's
files. Nothing in it names a database id except as an opaque ``ref`` used to resolve
"agreed with" links inside the same bundle.
"""

from __future__ import annotations

import dataclasses
import datetime
import logging
from collections import Counter
from collections.abc import Iterable

from django.apps import apps
from django.db import transaction
from django.db.models import Prefetch

from ami.main.models import (
    Classification,
    Detection,
    Identification,
    Occurrence,
    Project,
    SourceImage,
    Taxon,
    User,
    update_occurrence_determination,
)
from ami.main.models_future.detection_matching import (
    DEFAULT_IOU_THRESHOLD,
    MATCH_NO_CANDIDATE,
    DetectionKey,
    DetectionMatch,
    match_detections,
)
from ami.main.models_future.tracks import TrackEditError, add_detections, detach_detection, verify_grouping

logger = logging.getLogger(__name__)

BUNDLE_FORMAT = "antenna-validated-occurrences"
BUNDLE_VERSION = 1
GROUPING_ASPECT = "grouping"


# -- Bundle schema ------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class TaxonKey:
    name: str
    rank: str
    gbif_taxon_key: int | None = None

    @classmethod
    def for_taxon(cls, taxon: Taxon | None) -> TaxonKey | None:
        if taxon is None:
            return None
        return cls(name=taxon.name, rank=taxon.rank, gbif_taxon_key=taxon.gbif_taxon_key)

    @classmethod
    def from_dict(cls, data: dict | None) -> TaxonKey | None:
        if not data:
            return None
        return cls(name=data["name"], rank=data["rank"], gbif_taxon_key=data.get("gbif_taxon_key"))


@dataclasses.dataclass
class GroupingConfirmation:
    user_email: str | None
    verified_at: str

    @classmethod
    def from_dict(cls, data: dict | None) -> GroupingConfirmation | None:
        if not data:
            return None
        return cls(user_email=data.get("user_email"), verified_at=data["verified_at"])


@dataclasses.dataclass
class IdentificationRecord:
    ref: str
    created_at: str
    user_email: str | None
    taxon: TaxonKey | None
    withdrawn: bool = False
    comment: str = ""
    agreed_with_identification_ref: str | None = None
    # The prediction agreed with, by taxon and algorithm name: its row will not exist on the target.
    agreed_with_prediction_taxon: TaxonKey | None = None
    agreed_with_prediction_algorithm: str | None = None

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> IdentificationRecord:
        return cls(
            ref=str(data["ref"]),
            created_at=data["created_at"],
            user_email=data.get("user_email"),
            taxon=TaxonKey.from_dict(data.get("taxon")),
            withdrawn=bool(data.get("withdrawn", False)),
            comment=data.get("comment") or "",
            agreed_with_identification_ref=data.get("agreed_with_identification_ref"),
            agreed_with_prediction_taxon=TaxonKey.from_dict(data.get("agreed_with_prediction_taxon")),
            agreed_with_prediction_algorithm=data.get("agreed_with_prediction_algorithm"),
        )


@dataclasses.dataclass
class OccurrenceRecord:
    """One occurrence worth carrying: confirmed as a grouping, identified, or both."""

    ref: str
    detections: list[DetectionKey]
    confirmation: GroupingConfirmation | None = None
    determination: TaxonKey | None = None
    identifications: list[IdentificationRecord] = dataclasses.field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "ref": self.ref,
            "detections": [key.as_dict() for key in self.detections],
            "confirmation": dataclasses.asdict(self.confirmation) if self.confirmation else None,
            "determination": dataclasses.asdict(self.determination) if self.determination else None,
            "identifications": [identification.as_dict() for identification in self.identifications],
        }

    @classmethod
    def from_dict(cls, data: dict) -> OccurrenceRecord:
        return cls(
            ref=str(data["ref"]),
            detections=[DetectionKey.from_dict(key) for key in data["detections"]],
            confirmation=GroupingConfirmation.from_dict(data.get("confirmation")),
            determination=TaxonKey.from_dict(data.get("determination")),
            identifications=[IdentificationRecord.from_dict(row) for row in data.get("identifications", [])],
        )


@dataclasses.dataclass
class Bundle:
    occurrences: list[OccurrenceRecord]
    project_name: str | None = None
    exported_at: str = dataclasses.field(default_factory=lambda: datetime.datetime.now().isoformat())
    source: str | None = None
    version: int = BUNDLE_VERSION

    def as_dict(self) -> dict:
        return {
            "format": BUNDLE_FORMAT,
            "version": self.version,
            "exported_at": self.exported_at,
            "project_name": self.project_name,
            "source": self.source,
            "occurrences": [record.as_dict() for record in self.occurrences],
        }

    @classmethod
    def from_dict(cls, data: dict) -> Bundle:
        if data.get("format") != BUNDLE_FORMAT:
            raise ValueError(f"Not a {BUNDLE_FORMAT} bundle (format={data.get('format')!r}).")
        if int(data.get("version", 0)) > BUNDLE_VERSION:
            raise ValueError(f"Bundle version {data['version']} is newer than this code understands.")
        return cls(
            occurrences=[OccurrenceRecord.from_dict(row) for row in data["occurrences"]],
            project_name=data.get("project_name"),
            exported_at=data.get("exported_at") or "",
            source=data.get("source"),
            version=int(data.get("version", BUNDLE_VERSION)),
        )


# -- Export -------------------------------------------------------------------------------


def _iso(value: datetime.datetime | None) -> str | None:
    return value.isoformat() if value else None


def build_bundle(project: Project) -> Bundle:
    """Every occurrence in ``project`` that a person confirmed or identified, with its detection keys."""
    detections = Detection.objects.valid().select_related("source_image__deployment", "detection_algorithm")
    identifications = Identification.objects.select_related(
        "user", "taxon", "agreed_with_prediction__taxon", "agreed_with_prediction__algorithm"
    ).order_by("created_at", "pk")
    occurrences = (
        Occurrence.objects.filter(project=project)
        .filter(grouping_verified_at__isnull=False)
        .union(Occurrence.objects.filter(project=project, identifications__isnull=False))
        .values_list("pk", flat=True)
    )
    occurrences = (
        Occurrence.objects.filter(pk__in=list(occurrences))
        .select_related("determination", "grouping_verified_by")
        .prefetch_related(
            Prefetch("detections", queryset=detections.order_by("source_image__timestamp", "source_image_id", "pk")),
            Prefetch("identifications", queryset=identifications),
        )
        .order_by("pk")
    )

    records = []
    for occurrence in occurrences:
        keys = [DetectionKey.for_detection(d) for d in occurrence.detections.all() if d.bbox]
        if not keys:
            logger.warning(f"Occurrence {occurrence.pk} has no detection with a box and was left out of the bundle.")
            continue
        confirmation = None
        if occurrence.grouping_verified_at is not None:
            reviewer = occurrence.grouping_verified_by
            confirmation = GroupingConfirmation(
                user_email=reviewer.email if reviewer else None,
                verified_at=occurrence.grouping_verified_at.isoformat(),
            )
        records.append(
            OccurrenceRecord(
                ref=str(occurrence.pk),
                detections=keys,
                confirmation=confirmation,
                determination=TaxonKey.for_taxon(occurrence.determination),
                identifications=[
                    IdentificationRecord(
                        ref=str(identification.pk),
                        created_at=identification.created_at.isoformat(),
                        user_email=identification.user.email if identification.user else None,
                        taxon=TaxonKey.for_taxon(identification.taxon),
                        withdrawn=identification.withdrawn,
                        comment=identification.comment or "",
                        agreed_with_identification_ref=(
                            str(identification.agreed_with_identification_id)
                            if identification.agreed_with_identification_id
                            else None
                        ),
                        agreed_with_prediction_taxon=(
                            TaxonKey.for_taxon(identification.agreed_with_prediction.taxon)
                            if identification.agreed_with_prediction_id
                            else None
                        ),
                        agreed_with_prediction_algorithm=(
                            identification.agreed_with_prediction.algorithm.name
                            if identification.agreed_with_prediction_id
                            and identification.agreed_with_prediction.algorithm_id
                            else None
                        ),
                    )
                    for identification in occurrence.identifications.all()
                ],
            )
        )
    return Bundle(occurrences=records, project_name=project.name, source=f"project:{project.pk}")


# -- Resolving users and taxa -------------------------------------------------------------


class _Lookups:
    """Users by email and taxa by GBIF key or name and rank, each fetched once per import."""

    def __init__(self, bundle: Bundle):
        emails: set[str] = set()
        taxa: set[TaxonKey] = set()
        for record in bundle.occurrences:
            if record.confirmation and record.confirmation.user_email:
                emails.add(record.confirmation.user_email.lower())
            for identification in record.identifications:
                if identification.user_email:
                    emails.add(identification.user_email.lower())
                if identification.taxon:
                    taxa.add(identification.taxon)
                if identification.agreed_with_prediction_taxon:
                    taxa.add(identification.agreed_with_prediction_taxon)
            if record.determination:
                taxa.add(record.determination)

        self.users = {user.email.lower(): user for user in User.objects.filter(email__in=emails)} if emails else {}
        self._by_gbif: dict[int, Taxon] = {}
        self._by_name: dict[tuple[str, str], Taxon] = {}
        gbif_keys = {key.gbif_taxon_key for key in taxa if key.gbif_taxon_key}
        names = {key.name for key in taxa}
        if taxa:
            for taxon in Taxon.objects.filter(gbif_taxon_key__in=gbif_keys):
                self._by_gbif.setdefault(taxon.gbif_taxon_key, taxon)
            for taxon in Taxon.objects.filter(name__in=names):
                self._by_name.setdefault((taxon.name.lower(), taxon.rank), taxon)
        self.missing_users: set[str] = set()
        self.missing_taxa: set[TaxonKey] = set()

    def user(self, email: str | None) -> User | None:
        if not email:
            return None
        user = self.users.get(email.lower())
        if user is None:
            self.missing_users.add(email)
        return user

    def taxon(self, key: TaxonKey | None) -> Taxon | None:
        if key is None:
            return None
        taxon = self._by_gbif.get(key.gbif_taxon_key) if key.gbif_taxon_key else None
        taxon = taxon or self._by_name.get((key.name.lower(), key.rank))
        if taxon is None:
            self.missing_taxa.add(key)
        return taxon


# -- Import -------------------------------------------------------------------------------

# Outcome of one occurrence record. ``applied`` and ``unchanged`` are the two good ends.
OUTCOME_APPLIED = "applied"  # detections regrouped and/or confirmation written
OUTCOME_UNCHANGED = "unchanged"  # the target already matched the record (idempotent re-run)
OUTCOME_PARTIAL = "partial"  # some detections were not found; grouping left alone, not confirmed
OUTCOME_ERROR = "error"  # a track edit refused (sessions differ, two boxes on one capture, ...)


@dataclasses.dataclass
class ImportOptions:
    execute: bool = False
    iou_threshold: float = DEFAULT_IOU_THRESHOLD
    # Recreate a box the reviewer drew by hand when its capture exists but no detector found it.
    create_missing_detections: bool = False


@dataclasses.dataclass
class OccurrenceOutcome:
    ref: str
    outcome: str
    matches: list[DetectionMatch]
    target_occurrence_id: int | None = None
    # How the matched detections were spread over occurrences before the import touched them.
    occurrences_before: int = 0
    detached: int = 0
    added: int = 0
    created: int = 0
    confirmed: bool = False
    identifications_applied: int = 0
    identifications_skipped: int = 0
    determination_matches: bool | None = None
    error: str | None = None

    @property
    def match_counts(self) -> Counter:
        return Counter(match.status for match in self.matches)

    def as_dict(self) -> dict:
        data = dataclasses.asdict(self)
        data["matches"] = [match.as_dict() for match in self.matches]
        return data


@dataclasses.dataclass
class ImportReport:
    options: ImportOptions
    outcomes: list[OccurrenceOutcome] = dataclasses.field(default_factory=list)
    missing_users: list[str] = dataclasses.field(default_factory=list)
    missing_taxa: list[dict] = dataclasses.field(default_factory=list)

    def detection_counts(self) -> Counter:
        counts: Counter = Counter()
        for outcome in self.outcomes:
            counts.update(outcome.match_counts)
        return counts

    def outcome_counts(self) -> Counter:
        return Counter(outcome.outcome for outcome in self.outcomes)

    def summary(self) -> dict:
        detections = self.detection_counts()
        return {
            "mode": "execute" if self.options.execute else "dry-run",
            "iou_threshold": self.options.iou_threshold,
            "occurrences": dict(self.outcome_counts()),
            "occurrences_total": len(self.outcomes),
            "detections": dict(detections),
            "detections_total": sum(detections.values()),
            "confirmed": sum(1 for o in self.outcomes if o.confirmed),
            "detections_created": sum(o.created for o in self.outcomes),
            "identifications_applied": sum(o.identifications_applied for o in self.outcomes),
            "identifications_skipped": sum(o.identifications_skipped for o in self.outcomes),
            "determination_mismatches": sum(1 for o in self.outcomes if o.determination_matches is False),
            "missing_users": self.missing_users,
            "missing_taxa": self.missing_taxa,
        }

    def as_dict(self) -> dict:
        return {"summary": self.summary(), "occurrences": [outcome.as_dict() for outcome in self.outcomes]}


def _parse_datetime(value: str) -> datetime.datetime:
    # Stored times are naive local time (USE_TZ is off); drop any offset an exporter added.
    return datetime.datetime.fromisoformat(value).replace(tzinfo=None)


def confirm_grouping_as_of(occurrence: Occurrence, user: User, verified_at: datetime.datetime) -> None:
    """Record a grouping confirmation made by ``user`` at ``verified_at`` on another database.

    The one place the import writes a confirmation, through the same function the review
    interface uses, so whatever ``verify_grouping`` records (today the cached fields, later a
    review row as well) is recorded here too, under the original time.
    """
    verify_grouping(occurrence, user, timestamp=verified_at)


def review_model():
    """The ``ValidationReview`` model, or None on a branch that does not have it yet."""
    try:
        return apps.get_model("main", "ValidationReview")
    except LookupError:
        return None


def grouping_reviews_supported() -> bool:
    """Whether this branch records grouping confirmations as reviews.

    The review table arrives before the tracking code that adds its ``grouping`` aspect, so
    the table alone does not mean confirmations are kept there.
    """
    model = review_model()
    if model is None:
        return False
    choices = model._meta.get_field("aspect").choices or []
    return GROUPING_ASPECT in {value for value, _label in choices}


def _has_current_grouping_review(occurrence: Occurrence, user: User, verified_at: datetime.datetime) -> bool | None:
    """Whether a standing grouping review by ``user`` at ``verified_at`` exists; None where grouping reviews do not."""
    if not grouping_reviews_supported():
        return None
    return (
        review_model()
        .objects.filter(
            occurrence=occurrence,
            aspect=GROUPING_ASPECT,
            user=user,
            timestamp=verified_at,
            is_current=True,
            withdrawn=False,
        )
        .exists()
    )


def _is_confirmed_as(occurrence: Occurrence, user: User | None, verified_at: datetime.datetime | None) -> bool:
    """Whether the occurrence already carries this confirmation in full.

    The cached ``grouping_verified_at/by`` must match, and where the schema keeps reviews as
    rows of their own a standing grouping review by that person at that time must exist too.
    A cache that matches without its review (an occurrence confirmed before reviews existed)
    is not "confirmed as", so the import re-confirms it through ``verify_grouping`` and the
    review gets written.
    """
    if user is None or verified_at is None:
        return False
    if occurrence.grouping_verified_at != verified_at or occurrence.grouping_verified_by_id != user.pk:
        return False
    has_review = _has_current_grouping_review(occurrence, user, verified_at)
    return has_review is None or has_review


def _holder_counts(detection_ids: Iterable[int]) -> Counter:
    """How many of ``detection_ids`` each occurrence holds right now; ``None`` for unattached ones."""
    return Counter(
        Detection.objects.filter(pk__in=list(detection_ids)).order_by().values_list("occurrence_id", flat=True)
    )


def _majority_holder(holders: Counter) -> int | None:
    attached = {pk: n for pk, n in holders.items() if pk is not None}
    return max(attached, key=lambda pk: (attached[pk], -pk)) if attached else None


def _target_occurrence(project: Project, matches: list[DetectionMatch], holders: Counter) -> Occurrence:
    """The occurrence to rebuild the record on: the one already holding most of its detections.

    Ties go to the lowest id. When no matched detection is attached to any occurrence (a
    detector-only project), a new occurrence is created in the session of the first capture.
    """
    best = _majority_holder(holders)
    if best is not None:
        return Occurrence.objects.get(pk=best)
    first = next(match for match in matches if match.found)
    capture = SourceImage.objects.select_related("deployment").get(pk=first.capture_id)
    return Occurrence.objects.create(project=project, deployment=capture.deployment, event_id=capture.event_id)


def _create_missing_detections(record: OccurrenceRecord, matches: list[DetectionMatch]) -> int:
    """Recreate boxes a reviewer added by hand: their capture exists but no detector drew them."""
    created = 0
    for match in matches:
        if match.status != MATCH_NO_CANDIDATE or match.capture_id is None:
            continue
        capture = SourceImage.objects.get(pk=match.capture_id)
        detection = Detection.objects.create(
            source_image=capture, bbox=list(match.key.bbox), timestamp=capture.timestamp
        )
        match.detection_id = detection.pk
        match.status = "created"
        match.iou = 1.0
        created += 1
    return created


def _regroup(target: Occurrence, matched_ids: set[int], outcome: OccurrenceOutcome) -> None:
    """Make ``target`` hold exactly ``matched_ids`` using the track-edit operations.

    Detections the target holds that are not in the record leave first, one by one, each
    into an occurrence of its own; then the record's detections still elsewhere move in.
    Every step keeps the chain, statistics and session counts the way the review interface does.
    """
    current = set(Detection.objects.valid().filter(occurrence=target).values_list("pk", flat=True))
    for pk in sorted(current - matched_ids):
        detach_detection(target, Detection.objects.get(pk=pk))
        outcome.detached += 1
    incoming = matched_ids - current
    if incoming:
        add_detections(target, Detection.objects.filter(pk__in=incoming).select_related("source_image"))
        outcome.added += len(incoming)


def _apply_identifications(
    target: Occurrence,
    record: OccurrenceRecord,
    lookups: _Lookups,
    outcome: OccurrenceOutcome,
    created_by_ref: dict[str, Identification],
) -> None:
    """Re-create the record's identifications on ``target`` under their original user and time.

    Oldest first, so ``Identification.save`` withdraws earlier ones by the same user in the
    order it did originally; the exported ``withdrawn`` flag is then written as the final
    word. An identification that already exists with the same user, taxon and time is skipped.
    """
    for row in sorted(record.identifications, key=lambda r: r.created_at):
        user = lookups.user(row.user_email)
        taxon = lookups.taxon(row.taxon)
        if (row.user_email and user is None) or (row.taxon and taxon is None):
            outcome.identifications_skipped += 1
            continue
        created_at = _parse_datetime(row.created_at)
        existing = Identification.objects.filter(
            occurrence=target, user=user, taxon=taxon, created_at=created_at
        ).first()
        if existing is not None:
            created_by_ref[row.ref] = existing
            outcome.identifications_skipped += 1
            continue
        agreed_prediction = None
        agreed_taxon = lookups.taxon(row.agreed_with_prediction_taxon) if row.agreed_with_prediction_taxon else None
        if agreed_taxon is not None:
            predictions = Classification.objects.filter(detection__occurrence=target, taxon=agreed_taxon)
            if row.agreed_with_prediction_algorithm:
                predictions = predictions.filter(algorithm__name=row.agreed_with_prediction_algorithm)
            agreed_prediction = predictions.order_by("-score").first()
        identification = Identification(
            occurrence=target,
            user=user,
            taxon=taxon,
            withdrawn=row.withdrawn,
            comment=row.comment,
            agreed_with_prediction=agreed_prediction,
        )
        identification.save()
        # auto_now_add ignores a value given at creation; the original time is the record of who said what when.
        Identification.objects.filter(pk=identification.pk).update(
            created_at=created_at, updated_at=created_at, withdrawn=row.withdrawn
        )
        created_by_ref[row.ref] = identification
        outcome.identifications_applied += 1


def _link_agreements(bundle: Bundle, created_by_ref: dict[str, Identification]) -> None:
    for record in bundle.occurrences:
        for row in record.identifications:
            if row.agreed_with_identification_ref and row.ref in created_by_ref:
                agreed = created_by_ref.get(row.agreed_with_identification_ref)
                if agreed is not None:
                    Identification.objects.filter(pk=created_by_ref[row.ref].pk).update(
                        agreed_with_identification=agreed
                    )


def _pending_identifications(target_pk: int | None, record: OccurrenceRecord, lookups: _Lookups) -> int:
    """How many of the record's identifications are not yet on the target occurrence."""
    pending = 0
    for row in record.identifications:
        user = lookups.user(row.user_email)
        taxon = lookups.taxon(row.taxon)
        if (row.user_email and user is None) or (row.taxon and taxon is None):
            continue
        exists = (
            target_pk is not None
            and Identification.objects.filter(
                occurrence_id=target_pk, user=user, taxon=taxon, created_at=_parse_datetime(row.created_at)
            ).exists()
        )
        pending += 0 if exists else 1
    return pending


def _apply_record(
    project: Project,
    record: OccurrenceRecord,
    lookups: _Lookups,
    options: ImportOptions,
    created_by_ref: dict[str, Identification],
) -> OccurrenceOutcome:
    """Replay one record: regroup and confirm when it carries a confirmation, then re-attach its identifications.

    Only a confirmed record has its grouping rebuilt. An identified-but-unconfirmed
    occurrence keeps whatever grouping the target has; its identifications land on the
    occurrence holding most of its detections, and the report says over how many
    occurrences they were spread.
    """
    matches = match_detections(project, record.detections, options.iou_threshold)
    outcome = OccurrenceOutcome(ref=record.ref, outcome=OUTCOME_PARTIAL, matches=matches)

    if options.execute and options.create_missing_detections:
        outcome.created = _create_missing_detections(record, matches)
    complete = all(match.found for match in matches)
    if not options.execute and options.create_missing_detections:
        # A dry run counts the boxes an execute run would recreate as found.
        complete = all(m.found or (m.status == MATCH_NO_CANDIDATE and m.capture_id) for m in matches)
    matched_ids = {match.detection_id for match in matches if match.found}
    if not matched_ids:
        return outcome
    holders = _holder_counts(matched_ids)
    outcome.occurrences_before = len(holders)
    reviewer = lookups.user(record.confirmation.user_email) if record.confirmation else None
    verified_at = _parse_datetime(record.confirmation.verified_at) if record.confirmation else None
    rebuild = complete and record.confirmation is not None

    if not options.execute:
        # Report what an execute run would do without touching a row.
        target_pk = _majority_holder(holders)
        outcome.target_occurrence_id = target_pk
        pending = _pending_identifications(target_pk, record, lookups)
        if rebuild:
            grouped = (
                target_pk is not None
                and len(holders) == 1
                and Detection.objects.valid().filter(occurrence_id=target_pk).count() == len(matched_ids)
            )
            confirmed = grouped and _is_confirmed_as(Occurrence.objects.get(pk=target_pk), reviewer, verified_at)
            outcome.confirmed = bool(reviewer) and not confirmed
            changed = outcome.confirmed or not grouped
        else:
            changed = False
        if complete:
            outcome.outcome = OUTCOME_APPLIED if (changed or pending) else OUTCOME_UNCHANGED
        return outcome

    try:
        with transaction.atomic():
            target = _target_occurrence(project, matches, holders)
            outcome.target_occurrence_id = target.pk
            changed = False
            if rebuild:
                _regroup(target, matched_ids, outcome)
                changed = bool(outcome.detached or outcome.added or outcome.created or len(holders) != 1)
                if reviewer is None:
                    logger.warning(f"Record {record.ref}: reviewer {record.confirmation.user_email} not found.")
                elif changed or not _is_confirmed_as(target, reviewer, verified_at):
                    confirm_grouping_as_of(target, reviewer, verified_at)
                    outcome.confirmed = True
                    changed = True
            # A partial record is never confirmed, but what people said about it still applies to
            # the occurrence that holds most of its detections.
            _apply_identifications(target, record, lookups, outcome, created_by_ref)
            if outcome.identifications_applied:
                target.refresh_from_db()
                update_occurrence_determination(target)
                changed = True
            if complete:
                outcome.outcome = OUTCOME_APPLIED if changed else OUTCOME_UNCHANGED
            if record.determination:
                target.refresh_from_db()
                wanted = lookups.taxon(record.determination)
                outcome.determination_matches = wanted is not None and target.determination_id == wanted.pk
    except TrackEditError as err:
        outcome.outcome = OUTCOME_ERROR
        outcome.error = str(err)
    return outcome


def import_bundle(project: Project, bundle: Bundle, options: ImportOptions | None = None) -> ImportReport:
    """Replay ``bundle`` onto ``project``; a dry run (the default) only reports what would happen.

    Each record is applied in its own transaction, so a refused edit on one occurrence
    leaves the others in place. Re-running on an already replayed project changes nothing
    and reports every record as unchanged.
    """
    options = options or ImportOptions()
    lookups = _Lookups(bundle)
    report = ImportReport(options=options)
    created_by_ref: dict[str, Identification] = {}
    for record in bundle.occurrences:
        report.outcomes.append(_apply_record(project, record, lookups, options, created_by_ref))
    if options.execute:
        _link_agreements(bundle, created_by_ref)
    report.missing_users = sorted(lookups.missing_users)
    report.missing_taxa = [dataclasses.asdict(key) for key in sorted(lookups.missing_taxa, key=lambda k: k.name)]
    return report


def occurrence_detection_keys(occurrence: Occurrence) -> list[DetectionKey]:
    """The keys of an occurrence's detections in capture order; for verifying a replay."""
    detections = (
        Detection.objects.valid()
        .filter(occurrence=occurrence)
        .select_related("source_image__deployment", "detection_algorithm")
        .order_by("source_image__timestamp", "source_image_id", "pk")
    )
    return [DetectionKey.for_detection(d) for d in detections if d.bbox]
