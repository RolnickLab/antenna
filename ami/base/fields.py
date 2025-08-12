import datetime
import typing

from django.db import models
from rest_framework import serializers


class DateStringField(serializers.CharField):
    """
    Field that validates and stores dates as YYYY-MM-DD strings.
    Needed for storing dates as strings in JSON fields but keep validation.
    """

    def to_internal_value(self, value: str | None) -> str | None:
        if value is None:
            return None

        try:
            # Validate the date format by parsing it
            datetime.datetime.strptime(value, "%Y-%m-%d")
            return value
        except ValueError as e:
            raise serializers.ValidationError("Invalid date format. Use YYYY-MM-DD format.") from e

    @classmethod
    def to_date(cls, value: str | None) -> datetime.date | None:
        """Convert a YYYY-MM-DD string to a Python date object for ORM queries."""
        if value is None:
            return None
        return datetime.datetime.strptime(value, "%Y-%m-%d").date()


def create_nested_writable_fields(
    field_name: str, nested_serializer: type, queryset: models.QuerySet, required: bool = True
) -> tuple[serializers.Field, serializers.Field]:
    """
    Creates a pair of fields for nested read/write pattern.
    Returns (read_field, write_field)
    """
    read_field = nested_serializer(read_only=True)
    write_field = serializers.PrimaryKeyRelatedField(
        queryset=queryset, source=field_name, write_only=True, required=required
    )
    return read_field, write_field


class NestedWritableField(serializers.Field):
    """
    A DRF field that reads as nested objects but writes using ID suffix format.

    This field enforces a clear separation between read and write formats:
    - Read (GET): Returns nested object under the field name (e.g., 'project')
    - Write (POST/PUT): Only accepts IDs with suffix (e.g., 'project_id' or 'taxa_ids')

    This explicit naming makes the API contract clearer - you're sending IDs, not objects.

    Features:
    - Single relationships: read as 'field', write as 'field_id'
    - Many-to-many relationships: read as 'field', write as 'field_ids'
    - Optimized queries for many-to-many (bulk lookup instead of N+1)
    - Clear validation error messages
    - Context propagation to nested serializers
    - Type-safe with proper annotations

    Args:
        nested_serializer: The serializer class to use for nested representation
        queryset: QuerySet to validate IDs against (respects permissions/filtering)
        many: Whether this is a many-to-many relationship (default: False)
        **kwargs: Additional field options (required, allow_null, etc.)

    Examples:
        Basic usage:
        ```python
        class TagSerializer(serializers.ModelSerializer):
            # Single relationship
            project = NestedWritableField(
                nested_serializer=ProjectNestedSerializer,
                queryset=Project.objects.all()
            )

            # Many-to-many relationship
            taxa = NestedWritableField(
                nested_serializer=TaxonNestedSerializer,
                queryset=Taxon.objects.all(),
                many=True,
                required=False
            )

            class Meta:
                model = Tag
                fields = ["id", "name", "project", "taxa"]
        ```

        API Input/Output:
        ```python
        # GET /api/tags/1/ returns:
        {
            "id": 1,
            "name": "Wildlife Tag",
            "project": {"id": 5, "name": "Forest Study"},
            "taxa": [
                {"id": 10, "name": "Oak Tree"},
                {"id": 11, "name": "Pine Tree"}
            ]
        }

        # POST/PUT requires ID suffix format:
        {
            "name": "New Tag",
            "project_id": 5,        # Required format for single relationship
            "taxa_ids": [10, 11]    # Required format for many relationship
        }

        # This format is NOT accepted (will be treated as missing field):
        {
            "name": "New Tag",
            "project": 5,           # ❌ Won't work - must use project_id
            "taxa": [10, 11]        # ❌ Won't work - must use taxa_ids
        }
        ```

    Performance Notes:
        - Leverages DRF's PrimaryKeyRelatedField for validation (no duplication)
        - Uses provided queryset for security (respects permissions)
        - Bulk operations handled efficiently by DRF
        - Context is propagated to nested serializers for access to request, etc.
    """

    def __init__(
        self, nested_serializer: type[serializers.Serializer], queryset: models.QuerySet, many: bool = False, **kwargs
    ):
        self.nested_serializer = nested_serializer
        self.queryset = queryset
        self.many = many
        self.field_name: str = ""  # Set by bind()

        # Create internal PrimaryKeyRelatedField for validation
        self._pk_field = serializers.PrimaryKeyRelatedField(
            queryset=queryset,
            many=many,
            **{k: v for k, v in kwargs.items() if k in ["required", "allow_null", "default"]},
        )

        super().__init__(**kwargs)

    def bind(self, field_name: str, parent: serializers.Serializer) -> None:
        """Called when field is bound to serializer"""
        super().bind(field_name, parent)
        self.field_name = field_name
        # Also bind the internal PK field
        self._pk_field.bind(field_name, parent)

    def to_representation(self, value: typing.Any) -> dict[str, typing.Any] | list[dict[str, typing.Any]] | None:
        """
        Convert model instance(s) to nested representation for GET requests.

        Args:
            value: Model instance (single) or related manager (many=True)

        Returns:
            Nested object representation or list of objects
        """
        if value is None:
            return None

        # Pass context to nested serializer (includes request, view, etc.)
        context = getattr(self, "context", {})

        if self.many:
            # value is a related manager (e.g., tag.taxa)
            instances = value.all()
            result = self.nested_serializer(instances, many=True, context=context).data
        else:
            # value is a single model instance
            result = self.nested_serializer(value, context=context).data

        return result

    def to_internal_value(self, data: typing.Any) -> models.Model | list[models.Model] | None:
        """
        Convert ID(s) to model instance(s) for POST/PUT requests.

        Delegates to PrimaryKeyRelatedField for all validation logic.

        Args:
            data: Single ID or list of IDs

        Returns:
            Model instance(s) corresponding to the ID(s)

        Raises:
            ValidationError: If ID format is invalid or object doesn't exist
        """
        return self._pk_field.to_internal_value(data)

    def get_value(self, dictionary: dict[str, typing.Any]) -> typing.Any:
        """
        Extract field value from input data.

        ONLY accepts ID suffix format ('field_id' or 'field_ids').
        Does NOT accept the base field name for writes.

        Args:
            dictionary: Input data from request

        Returns:
            Field value or serializers.empty if not found
        """
        if self.many:
            # Many-to-many: ONLY check for 'field_ids'
            expected_key = f"{self.field_name}_ids"
            if expected_key in dictionary:
                return dictionary[expected_key]
        else:
            # Single: ONLY check for 'field_id'
            expected_key = f"{self.field_name}_id"
            if expected_key in dictionary:
                return dictionary[expected_key]

        # Not found - this is expected behavior
        # The field will use its default or be marked as missing
        return serializers.empty

    def fail(self, key: str, **kwargs) -> None:
        """
        Override fail to provide helpful error messages about expected format.
        """
        if key == "required":
            if self.many:
                expected_key = f"{self.field_name}_ids"
                message = f"This field is required. Use '{expected_key}' with a list of IDs."
            else:
                expected_key = f"{self.field_name}_id"
                message = f"This field is required. Use '{expected_key}' with an ID value."
            raise serializers.ValidationError(message, code="required")

        super().fail(key, **kwargs)
