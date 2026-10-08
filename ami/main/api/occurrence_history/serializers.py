"""Serializers for an occurrence's history: identifications, predictions and algorithm results as one list."""

from drf_spectacular.utils import PolymorphicProxySerializer, extend_schema_field
from rest_framework import serializers

from ami.jobs.job_config import JobConfigFieldSerializer
from ami.main.api.serializers import TaxonParentSerializer


class HistoryUserSerializer(serializers.Serializer):
    """A person in an occurrence's history: name and picture only, never an email address."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    image = serializers.ImageField(allow_null=True)


class HistoryAlgorithmSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    key = serializers.CharField()


class HistoryTaxonSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    rank = serializers.CharField()
    parents = TaxonParentSerializer(many=True, read_only=True, source="parents_json")


class HistoryJobSerializer(serializers.Serializer):
    """A job in the history. ``config`` is filled per entry by ``HistoryEntryBaseSerializer``."""

    id = serializers.IntegerField()
    name = serializers.CharField()
    config = JobConfigFieldSerializer(
        many=True, read_only=True, help_text="The job's config, in the order its task's config schema declares it."
    )


class ReplacedClassificationSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    taxon = HistoryTaxonSerializer(allow_null=True)
    score = serializers.FloatField(allow_null=True)


class CreatedClassificationSerializer(serializers.Serializer):
    """A classification a run created, and the one it replaced (null when none, or when it was deleted)."""

    id = serializers.IntegerField(source="classification.id")
    taxon = HistoryTaxonSerializer(source="classification.taxon", allow_null=True)
    score = serializers.FloatField(source="classification.score", allow_null=True)
    terminal = serializers.BooleanField(source="classification.terminal")
    detection_id = serializers.IntegerField(source="classification.detection_id")
    replaced = ReplacedClassificationSerializer(allow_null=True)


class HistoryEntryBaseSerializer(serializers.Serializer):
    """The fields every entry of an occurrence's history has."""

    id = serializers.IntegerField(help_text="Primary key of the row in the table ``type`` names.")
    timestamp = serializers.DateTimeField()
    user = HistoryUserSerializer(allow_null=True)
    algorithm = HistoryAlgorithmSerializer(allow_null=True)
    job = serializers.SerializerMethodField()
    taxon = HistoryTaxonSerializer(allow_null=True, help_text="The identified or predicted taxon.")
    score = serializers.FloatField(allow_null=True, help_text="A prediction's score; null for other entries.")

    @extend_schema_field(HistoryJobSerializer(allow_null=True))
    def get_job(self, entry) -> dict | None:
        if entry.job is None:
            return None
        return {
            **HistoryJobSerializer(entry.job).data,
            "config": JobConfigFieldSerializer(entry.job_config, many=True).data,
        }


class IdentificationDetailsSerializer(serializers.Serializer):
    comment = serializers.CharField(allow_blank=True)
    withdrawn = serializers.BooleanField()


class PredictionDetailsSerializer(serializers.Serializer):
    terminal = serializers.BooleanField()


class IdentificationEntrySerializer(HistoryEntryBaseSerializer):
    type = serializers.ChoiceField(choices=["identification"])
    details = IdentificationDetailsSerializer()


class PredictionEntrySerializer(HistoryEntryBaseSerializer):
    type = serializers.ChoiceField(choices=["prediction"])
    details = PredictionDetailsSerializer()


class AlgorithmResultEntrySerializer(HistoryEntryBaseSerializer):
    """What a post-processing run decided about the occurrence, with the classifications it created."""

    type = serializers.ChoiceField(choices=["algorithm_result"])
    kind = serializers.CharField()
    value = serializers.FloatField(
        allow_null=True, help_text="The kind's headline figure, for sorting and filtering; not a confidence."
    )
    data = serializers.JSONField(help_text="The kind's figures, validated against its data model.")
    determination_before = HistoryTaxonSerializer(allow_null=True)
    determination_after = HistoryTaxonSerializer(allow_null=True)
    classifications = CreatedClassificationSerializer(
        many=True, help_text="The classifications the run created, best score first."
    )


HISTORY_ENTRY_SERIALIZERS = {
    "identification": IdentificationEntrySerializer,
    "prediction": PredictionEntrySerializer,
    "algorithm_result": AlgorithmResultEntrySerializer,
}

# The history endpoint's response: a plain oneOf with a literal ``type`` field. A result's ``data`` is
# published as JSON; the server validates it against its kind's model, and the UI types it by kind.
# Publishing one typed component per kind waits for a client generated from the schema (#1482).
OCCURRENCE_HISTORY_ENTRY_SCHEMA = PolymorphicProxySerializer(
    component_name="OccurrenceHistoryEntry",
    serializers=list(HISTORY_ENTRY_SERIALIZERS.values()),
    resource_type_field_name=None,
    many=True,
)


def serialize_history(entries, context) -> list[dict]:
    return [HISTORY_ENTRY_SERIALIZERS[entry.type](entry, context=context).data for entry in entries]
