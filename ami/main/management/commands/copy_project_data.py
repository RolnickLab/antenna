"""
Copy one project, or a subset of its deployments, from another Antenna database into this one.

The source database is only read. The command opens its own connection to it from the
SOURCE_DATABASE_URL environment variable, in a read-only, repeatable-read transaction, so the
source sees no writes and every table is read from the same snapshot. The rows are streamed with
COPY into temporary staging tables in this (the target) database, given new primary keys, and
inserted in one transaction. Nothing is written to the target unless --execute is passed.

Shared rows are reused when the target already has them: taxa by name, algorithms by key,
pipelines by slug and users by email. Every other row gets a new primary key, and foreign keys are
rewritten to match. A foreign key to a row that is not copied is set to NULL; see SKIPPED_MODELS.

Usage:
    export SOURCE_DATABASE_URL=postgres://readonly_user@source-host:5432/antenna   # password in ~/.pgpass
    # Dry run: row counts and an estimate of the classification score sizes
    python manage.py copy_project_data --project 20 --exclude-deployments 75,76
    # Copy
    python manage.py copy_project_data --project 20 --exclude-deployments 75,76 --execute
"""

import dataclasses
import logging
import os
import time
import typing

import psycopg
from django.core.exceptions import EmptyResultSet
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, models, transaction
from django.db.models import Q, QuerySet

from ami.main.models import (
    Classification,
    Deployment,
    Detection,
    Device,
    Event,
    Identification,
    Occurrence,
    Project,
    Site,
    SourceImage,
    SourceImageCollection,
    TaxaList,
    Taxon,
    UserProjectMembership,
)
from ami.ml.models import Algorithm, AlgorithmCategoryMap, Pipeline, ProjectPipelineConfig
from ami.users.models import User
from ami.users.roles import Role, create_roles_for_project
from ami.users.signals import suppress_membership_signal

logger = logging.getLogger(__name__)

SOURCE_URL_ENV = "SOURCE_DATABASE_URL"

# Rows of these models are never copied, and foreign keys to them are set to NULL.
# Storage sources hold credentials, and jobs and post-processing results describe runs on the
# source instance. Captures keep their own public URLs, so images still load without the source.
SKIPPED_MODELS = "S3StorageSource, Job, AlgorithmResult, SourceImageUpload, Tag, ProcessingService"

ProjectIncludeTaxa = Project.default_filters_include_taxa.through
ProjectExcludeTaxa = Project.default_filters_exclude_taxa.through
CollectionImages = SourceImageCollection.images.through
PipelineAlgorithms = Pipeline.algorithms.through
TaxaListTaxa = TaxaList.taxa.through
TaxaListProjects = TaxaList.projects.through
TaxonProjects = Taxon.projects.through


@dataclasses.dataclass
class Step:
    """One model to copy: which source rows to read and how to fit them into the target."""

    model: type[models.Model]
    # Returns the source rows to copy. It runs after the earlier steps are staged, so it can
    # select by the ids those steps found (see CopyRun.staged_values).
    select: typing.Callable[["CopyRun"], QuerySet]
    # Reuse an existing target row with the same values in these columns instead of inserting one.
    match_on: tuple[str, ...] = ()
    # Column name to an SQL expression used instead of the source value.
    overrides: dict[str, str] = dataclasses.field(default_factory=dict)
    # A self-referencing column to follow until all referenced rows are staged (taxon parents).
    follow: str | None = None

    @property
    def table(self) -> str:
        return self.model._meta.db_table

    @property
    def staging(self) -> str:
        return f"_copy_{self.table}"

    @property
    def is_link_table(self) -> bool:
        """Auto-created many-to-many tables: a row is only kept when both ends are copied."""
        return bool(self.model._meta.auto_created)

    @property
    def fields(self) -> list[models.Field]:
        return list(self.model._meta.concrete_fields)


def build_steps(with_users: bool) -> list[Step]:
    """The copy plan, in the order the rows are read from the source."""
    steps = [
        Step(Project, lambda r: Project.objects.filter(pk=r.project_id)),
        Step(ProjectIncludeTaxa, lambda r: ProjectIncludeTaxa.objects.filter(project_id=r.project_id)),
        Step(ProjectExcludeTaxa, lambda r: ProjectExcludeTaxa.objects.filter(project_id=r.project_id)),
        Step(Deployment, lambda r: Deployment.objects.filter(pk__in=r.deployment_ids)),
        Step(Device, lambda r: Device.objects.filter(pk__in=r.staged_values(Deployment, "device_id"))),
        Step(Site, lambda r: Site.objects.filter(pk__in=r.staged_values(Deployment, "research_site_id"))),
        Step(Event, lambda r: Event.objects.filter(deployment_id__in=r.deployment_ids)),
        Step(SourceImage, lambda r: SourceImage.objects.filter(deployment_id__in=r.deployment_ids)),
        Step(Occurrence, lambda r: Occurrence.objects.filter(deployment_id__in=r.deployment_ids)),
        Step(Detection, lambda r: Detection.objects.filter(source_image__deployment_id__in=r.deployment_ids)),
        Step(
            Classification,
            lambda r: Classification.objects.filter(detection__source_image__deployment_id__in=r.deployment_ids),
        ),
        Step(Identification, lambda r: Identification.objects.filter(occurrence__deployment_id__in=r.deployment_ids)),
        Step(SourceImageCollection, lambda r: SourceImageCollection.objects.filter(project_id=r.project_id)),
        Step(
            CollectionImages,
            lambda r: CollectionImages.objects.filter(
                sourceimagecollection__project_id=r.project_id, sourceimage__deployment_id__in=r.deployment_ids
            ),
        ),
        Step(
            Pipeline,
            lambda r: Pipeline.objects.filter(
                Q(project_pipeline_configs__project_id=r.project_id)
                | Q(pk__in=r.staged_values(Project, "default_processing_pipeline_id"))
            ).distinct(),
            match_on=("slug",),
        ),
        Step(ProjectPipelineConfig, lambda r: ProjectPipelineConfig.objects.filter(project_id=r.project_id)),
        Step(
            Algorithm,
            lambda r: Algorithm.objects.filter(
                Q(pk__in=r.staged_values(Classification, "algorithm_id"))
                | Q(pk__in=r.staged_values(Detection, "detection_algorithm_id"))
                | Q(pipelines__in=r.staged_values(Pipeline, "id"))
            ).distinct(),
            match_on=("key",),
        ),
        Step(
            PipelineAlgorithms,
            lambda r: PipelineAlgorithms.objects.filter(pipeline_id__in=r.staged_values(Pipeline, "id")),
        ),
        Step(
            AlgorithmCategoryMap,
            lambda r: AlgorithmCategoryMap.objects.filter(
                pk__in=r.staged_values(Classification, "category_map_id")
                + r.staged_values(Algorithm, "category_map_id")
            ),
        ),
        Step(TaxaList, lambda r: TaxaList.objects.filter(projects=r.project_id)),
        Step(TaxaListProjects, lambda r: TaxaListProjects.objects.filter(project_id=r.project_id)),
        Step(TaxaListTaxa, lambda r: TaxaListTaxa.objects.filter(taxalist_id__in=r.staged_values(TaxaList, "id"))),
        Step(Taxon, lambda r: r.referenced_taxa(), match_on=("name",), follow="parent_id"),
        Step(TaxonProjects, lambda r: TaxonProjects.objects.filter(project_id=r.project_id)),
    ]
    if with_users:
        steps += [
            Step(UserProjectMembership, lambda r: UserProjectMembership.objects.filter(project_id=r.project_id)),
            Step(
                User,
                lambda r: User.objects.filter(
                    pk__in=r.staged_values(UserProjectMembership, "user_id")
                    + r.staged_values(Project, "owner_id")
                    + r.staged_values(Identification, "user_id")
                ),
                match_on=("email",),
                # Copied accounts cannot log in and have no admin rights on the target.
                overrides={"password": "'!'", "is_staff": "false", "is_superuser": "false"},
            ),
        ]
    return steps


class CopyRun:
    """State shared by the steps of one copy: the two connections and the selection."""

    def __init__(self, source: psycopg.Connection, project_id: int, deployment_ids: list[int], steps: list[Step]):
        self.source = source
        self.project_id = project_id
        self.deployment_ids = deployment_ids
        self.steps = steps
        self.by_model = {step.model: step for step in steps}
        self.staged_tables: set[type[models.Model]] = set()

    def source_sql(self, qs: QuerySet, columns: list[str]) -> str | None:
        """Compile a queryset to a literal SQL statement for the source connection, or None if it is empty."""
        try:
            sql, params = qs.order_by().values_list(*columns).query.sql_with_params()
        except EmptyResultSet:
            return None
        return psycopg.ClientCursor(self.source).mogrify(sql, params)

    def staged_column(self, model: type[models.Model], column: str, where: str = "TRUE") -> list:
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT DISTINCT "{column}" FROM "{self.by_model[model].staging}" WHERE {where}')
            return [row[0] for row in cursor.fetchall()]

    def staged_values(self, model: type[models.Model], column: str) -> list:
        """Distinct non-null values of one column among the rows already staged for a model."""
        if model not in self.staged_tables:
            return []
        return self.staged_column(model, column, f'"{column}" IS NOT NULL')

    def referenced_taxa(self) -> QuerySet:
        """Taxa the copied rows point to, and every taxon named in a copied category map.

        Class masking finds the taxon for each category map label by name, so the label taxa are
        copied too. Their ancestors are added by following ``parent_id`` (see Step.follow).
        """
        ids = set()
        for model, column in [
            (Classification, "taxon_id"),
            (Occurrence, "determination_id"),
            (Identification, "taxon_id"),
            (TaxaListTaxa, "taxon_id"),
            (ProjectIncludeTaxa, "taxon_id"),
            (ProjectExcludeTaxa, "taxon_id"),
        ]:
            ids.update(self.staged_values(model, column))
        labels = set()
        if AlgorithmCategoryMap in self.staged_tables:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT DISTINCT item->>'label' FROM "
                    f'"{self.by_model[AlgorithmCategoryMap].staging}", jsonb_array_elements(data) AS item'
                )
                labels = {row[0] for row in cursor.fetchall() if row[0]}
        return Taxon.objects.filter(Q(pk__in=ids) | Q(name__in=labels))

    def source_roles(self) -> list[tuple[str, int]]:
        """(role name, source user id) for every role a user holds on the source project.

        Roles are permission groups named "<project id>_<project name>_<role class>".
        """
        group_table = User.groups.through._meta.db_table
        with self.source.cursor() as cursor:
            cursor.execute(
                f'SELECT g.name, ug.user_id FROM auth_group g JOIN "{group_table}" ug ON ug.group_id = g.id '
                "WHERE g.name LIKE %s",
                [f"{self.project_id}\\_%"],
            )
            return [(name.rsplit("_", 1)[-1], user_id) for name, user_id in cursor.fetchall()]

    def count(self, step: Step) -> int:
        sql = self.source_sql(step.select(self), [step.model._meta.pk.attname])
        if sql is None:
            return 0
        with self.source.cursor() as cursor:
            cursor.execute(f"SELECT count(*) FROM ({sql}) AS selection")
            return cursor.fetchone()[0]

    def stage(self, step: Step) -> tuple[int, int]:
        """Stream the selected source rows into a temporary table in the target. Returns rows, bytes."""
        columns = [f.column for f in step.fields]
        column_list = ", ".join(f'"{c}"' for c in columns)
        with connection.cursor() as cursor:
            cursor.execute(
                f'CREATE TEMP TABLE "{step.staging}" ON COMMIT DROP AS '
                f'SELECT {column_list} FROM "{step.table}" WITH NO DATA'
            )
        self.staged_tables.add(step.model)

        total_bytes = 0
        qs = step.select(self)
        while True:
            total_bytes += self._copy_rows(step, qs, column_list)
            if not step.follow:
                break
            # Stage referenced rows that are not staged yet, until there are none left.
            with connection.cursor() as cursor:
                cursor.execute(
                    f'SELECT DISTINCT s."{step.follow}" FROM "{step.staging}" s '
                    f'WHERE s."{step.follow}" IS NOT NULL AND NOT EXISTS '
                    f'(SELECT 1 FROM "{step.staging}" t WHERE t.id = s."{step.follow}")'
                )
                missing = [row[0] for row in cursor.fetchall()]
            if not missing:
                break
            qs = step.model.objects.filter(pk__in=missing)

        with connection.cursor() as cursor:
            cursor.execute(f'SELECT count(*) FROM "{step.staging}"')
            return cursor.fetchone()[0], total_bytes

    def _copy_rows(self, step: Step, qs: QuerySet, column_list: str) -> int:
        sql = self.source_sql(qs, [f.attname for f in step.fields])
        copied = 0
        if sql is None:
            return copied
        with connection.cursor() as target_cursor, self.source.cursor() as source_cursor:
            raw_target = target_cursor.cursor
            with source_cursor.copy(f"COPY ({sql}) TO STDOUT (FORMAT BINARY)") as copy_out:
                with raw_target.copy(f'COPY "{step.staging}" ({column_list}) FROM STDIN (FORMAT BINARY)') as copy_in:
                    for chunk in copy_out:
                        copy_in.write(chunk)
                        copied += len(chunk)
        return copied

    def assign_ids(self, step: Step) -> int:
        """Give each staged row its target id: an existing matching row, or a new id. Returns matches."""
        table, staging = step.table, step.staging
        pk = step.model._meta.pk.column
        with connection.cursor() as cursor:
            cursor.execute(
                f'ALTER TABLE "{staging}" ADD COLUMN _new_id bigint, '
                "ADD COLUMN _existing boolean NOT NULL DEFAULT false"
            )
            matched = 0
            if step.match_on:
                condition = " AND ".join(f'existing."{c}" = s."{c}"' for c in step.match_on)
                cursor.execute(
                    f'UPDATE "{staging}" s SET _new_id = existing."{pk}", _existing = true '
                    f'FROM "{table}" existing WHERE {condition}'
                )
                matched = cursor.rowcount
            cursor.execute(
                f"UPDATE \"{staging}\" SET _new_id = nextval(pg_get_serial_sequence('\"{table}\"', '{pk}')) "
                "WHERE _new_id IS NULL"
            )
            # Temporary tables are never analyzed automatically. Without statistics the planner
            # treats them as tiny and joins millions of rows with nested loops.
            cursor.execute(f'ANALYZE "{staging}"')
        return matched

    def insert(self, step: Step) -> int:
        """Insert the staged rows that are not reused, with every foreign key rewritten to target ids."""
        selects, joins, required = [], [], []
        for n, field in enumerate(step.fields):
            column = field.column
            if field.primary_key:
                selects.append("s._new_id")
            elif column in step.overrides:
                selects.append(step.overrides[column])
            elif field.is_relation:
                related = self.by_model.get(field.related_model)
                if related is None:
                    selects.append("NULL")
                else:
                    related_pk = related.model._meta.pk.column
                    joins.append(f'LEFT JOIN "{related.staging}" j{n} ON j{n}."{related_pk}" = s."{column}"')
                    selects.append(f"j{n}._new_id")
                    if step.is_link_table:
                        required.append(f"j{n}._new_id IS NOT NULL")
            else:
                selects.append(f's."{column}"')

        columns = ", ".join(f'"{f.column}"' for f in step.fields)
        where = " AND ".join(["NOT s._existing"] + required)
        conflict = " ON CONFLICT DO NOTHING" if step.is_link_table else ""
        with connection.cursor() as cursor:
            cursor.execute(
                f'INSERT INTO "{step.table}" ({columns}) SELECT {", ".join(selects)} '
                f'FROM "{step.staging}" s {" ".join(joins)} WHERE {where}{conflict}'
            )
            return cursor.rowcount


def check_plan(steps: list[Step]) -> None:
    """Fail before reading anything if a required foreign key points to a model the plan skips."""
    planned = {step.model for step in steps}
    problems = []
    for step in steps:
        for field in step.fields:
            if field.is_relation and field.related_model not in planned and not field.null:
                problems.append(f"{step.model.__name__}.{field.name} -> {field.related_model.__name__}")
            if field.is_relation and field.target_field != field.related_model._meta.pk:
                problems.append(f"{step.model.__name__}.{field.name} does not reference a primary key")
    if problems:
        raise CommandError("The copy plan cannot satisfy these required foreign keys: " + "; ".join(problems))


def connect_source(url: str) -> psycopg.Connection:
    """Open the source connection: read only, with one snapshot for every query in the transaction.

    The server rejects any write on this session, so a bug in this command cannot change the source.
    """
    source = psycopg.connect(url, options="-c default_transaction_read_only=on")
    source.read_only = True
    source.isolation_level = psycopg.IsolationLevel.REPEATABLE_READ
    return source


def parse_ids(value: str | None, option: str) -> list[int]:
    if not value:
        return []
    try:
        return sorted({int(part) for part in value.split(",") if part.strip()})
    except ValueError:
        raise CommandError(f"{option} must be a comma-separated list of integer ids, got {value!r}")


def check_source_columns(source: psycopg.Connection, steps: list[Step]) -> None:
    """Fail if the source schema lacks a column this code expects, which means the migrations differ."""
    with source.cursor() as cursor:
        cursor.execute(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = current_schema()"
        )
        present = set(cursor.fetchall())
    missing = [f"{s.table}.{f.column}" for s in steps for f in s.fields if (s.table, f.column) not in present]
    if missing:
        raise CommandError(
            "The source database is missing columns this code expects. Migrate both databases to the same "
            "migration state first. Missing: " + ", ".join(missing)
        )


class Command(BaseCommand):
    help = "Copy a project, or some of its deployments, from another Antenna database (read only) into this one."

    def add_arguments(self, parser):
        parser.add_argument("--project", type=int, required=True, help="Project id in the source database")
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--deployments", type=str, help="Comma-separated deployment ids to copy (default: all)")
        group.add_argument("--exclude-deployments", type=str, help="Comma-separated deployment ids to leave out")
        parser.add_argument(
            "--with-users",
            action="store_true",
            help="Also copy the project members, owner and identifiers, as accounts that cannot log in",
        )
        parser.add_argument("--execute", action="store_true", help="Copy the data. Without it, only report counts")

    def handle(self, *args, **options):
        url = os.environ.get(SOURCE_URL_ENV)
        if not url:
            raise CommandError(f"Set {SOURCE_URL_ENV} to the source database URL (keep the password in ~/.pgpass).")

        steps = build_steps(with_users=options["with_users"])
        check_plan(steps)

        source = connect_source(url)
        try:
            check_source_columns(source, steps)
            run = CopyRun(source, options["project"], self.select_deployments(source, options), steps)
            if options["execute"]:
                self.copy(run)
            else:
                self.report(run)
        finally:
            source.rollback()
            source.close()

    def select_deployments(self, source: psycopg.Connection, options) -> list[int]:
        project_id = options["project"]
        with source.cursor() as cursor:
            cursor.execute(
                f'SELECT name FROM "{Project._meta.db_table}" WHERE id = %s', [project_id]  # nosec: table name only
            )
            row = cursor.fetchone()
            if not row:
                raise CommandError(f"Project {project_id} does not exist in the source database.")
            cursor.execute(
                f'SELECT id, name FROM "{Deployment._meta.db_table}" WHERE project_id = %s ORDER BY id', [project_id]
            )
            available = dict(cursor.fetchall())
        self.stdout.write(f"Source project {project_id}: {row[0]} ({len(available)} deployments)")

        wanted = parse_ids(options.get("deployments"), "--deployments")
        excluded = parse_ids(options.get("exclude_deployments"), "--exclude-deployments")
        unknown = sorted(set(wanted + excluded) - set(available))
        if unknown:
            raise CommandError(f"Deployments {unknown} are not in source project {project_id}.")
        chosen = [d for d in (wanted or available) if d not in excluded]
        if not chosen:
            raise CommandError("No deployments selected.")
        for dep_id, name in available.items():
            self.stdout.write(f"  [{'x' if dep_id in chosen else ' '}] {dep_id}: {name}")
        return chosen

    def report(self, run: CopyRun) -> None:
        """Dry run: count the directly selected rows and estimate the classification score sizes."""
        direct = [Project, Deployment, Event, SourceImage, Occurrence, Detection, Classification, Identification]
        direct += [SourceImageCollection, CollectionImages, ProjectPipelineConfig, TaxaList]
        self.stdout.write("\nRows that would be copied (taxa, algorithms, category maps, pipelines and users are")
        self.stdout.write("found from these during the copy, and reused when the target already has them):")
        for model in direct:
            self.stdout.write(f"  {model._meta.label:<40} {run.count(run.by_model[model]):>12,}")

        sample = run.source_sql(run.by_model[Classification].select(run), ["logits", "scores"])
        with run.source.cursor() as cursor:
            cursor.execute(
                "SELECT count(*), count(logits), avg(pg_column_size(logits)), avg(pg_column_size(scores)), "
                f"avg(cardinality(scores)) FROM ({sample} LIMIT 1000) AS sample"
            )
            n, with_logits, logits_bytes, scores_bytes, length = cursor.fetchone()
        if n:
            self.stdout.write(
                f"\nClassification sample of {n}: {with_logits} with logits, "
                f"about {length or 0:.0f} values per array, "
                f"{(logits_bytes or 0) / 1024:.1f} KiB logits + {(scores_bytes or 0) / 1024:.1f} KiB scores per row "
                "as stored (TOAST may compress them)."
            )
        self.stdout.write(self.style.WARNING("\nDry run. Nothing was copied. Add --execute to copy."))

    def assign_roles(self, run: CopyRun, project: Project, source_roles: list[tuple[str, int]]) -> None:
        """Create the project's permission groups, which a raw insert skips, and give copied users their roles."""
        create_roles_for_project(project)
        if not source_roles:
            return
        with connection.cursor() as cursor:
            cursor.execute(f'SELECT id, _new_id FROM "{run.by_model[User].staging}"')
            user_ids = dict(cursor.fetchall())
        roles = {role.__name__: role for role in Role.__subclasses__()}
        users = User.objects.in_bulk(user_ids.values())
        with suppress_membership_signal():
            for role_name, source_user_id in source_roles:
                if role_name in roles and source_user_id in user_ids:
                    roles[role_name].assign_user(users[user_ids[source_user_id]], project)
        self.stdout.write(f"Assigned {len(source_roles)} project roles to copied users.")

    def copy(self, run: CopyRun) -> None:
        with transaction.atomic():
            self.stdout.write("\nReading from the source:")
            for step in run.steps:
                started = time.monotonic()
                rows, size = run.stage(step)
                self.stdout.write(
                    f"  {step.model._meta.label:<40} {rows:>12,} rows {size / 2**20:>10,.1f} MiB "
                    f"{time.monotonic() - started:>7.1f}s"
                )
            source_roles = run.source_roles() if User in run.by_model else []
            # The source snapshot is no longer needed; end it so it does not hold back vacuum.
            run.source.rollback()

            matched = {step.model: run.assign_ids(step) for step in run.steps}
            self.stdout.write("\nWriting to this database (inserted, reused):")
            for step in run.steps:
                inserted = run.insert(step)
                self.stdout.write(f"  {step.model._meta.label:<40} {inserted:>12,} {matched[step.model]:>8,}")

            new_taxa = Taxon.objects.filter(pk__in=run.staged_column(Taxon, "_new_id", "NOT _existing"))
            for taxon in new_taxa.select_related("parent"):
                # parents_json holds the ids of ancestors, which changed with the copy.
                taxon.update_parents(save=False)
                taxon.save(update_fields=["parents_json"])

            project = Project.objects.get(pk=run.staged_column(Project, "_new_id")[0])
            self.assign_roles(run, project, source_roles)
        self.stdout.write(self.style.SUCCESS(f"\nCopied into project {project.pk}: {project.name}"))
        self.stdout.write(
            f"Not copied, and set to NULL where referenced: {SKIPPED_MODELS}. "
            "Capture-set sampling settings (kwargs) still refer to source ids."
        )
