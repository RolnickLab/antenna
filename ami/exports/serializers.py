from rest_framework import serializers

from ami.base.serializers import DefaultSerializer
from ami.jobs.models import Job
from ami.jobs.serializers import JobListSerializer
from ami.main.api.serializers import UserNestedSerializer
from ami.main.models import Project

from .models import DataExport


class DataExportJobNestedSerializer(JobListSerializer):
    """
    Job Nested serializer for DataExport.
    """

    class Meta:
        model = Job
        fields = [
            "id",
            "name",
            "project",
            "progress",
            "result",
        ]


class DataExportSerializer(DefaultSerializer):
    """
    Serializer for DataExport
    """

    job = DataExportJobNestedSerializer(read_only=True)  # Nested job serializer
    user = UserNestedSerializer(read_only=True)
    project = serializers.PrimaryKeyRelatedField(queryset=Project.objects.all(), write_only=True)
    filters_display_one = serializers.SerializerMethodField()
    filters_display_two = serializers.SerializerMethodField()

    class Meta:
        model = DataExport
        fields = [
            "id",
            "user",
            "project",
            "format",
            "filters",
            "filters_display_one",
            "filters_display_two",
            "job",
            "file_url",
            "created_at",
            "updated_at",
        ]

    def get_filters_display_one(self, obj):
        """ """
        related_model_serializers = {
            "collection": "ami.main.api.serializers.SourceImageCollectionNestedSerializer",
            # "taxa_list": "ami.main.api.serializers.TaxonListNestedSerializer",
        }
        filters = obj.filters
        filters_display = {}

        for key, value in filters.items():
            if key in related_model_serializers:
                serializer_path = related_model_serializers[key]
                from django.utils.module_loading import import_string

                try:
                    Serializer = import_string(serializer_path)
                    Model = Serializer.Meta.model
                    instance = Model.objects.get(pk=value)
                    serializer = Serializer(instance, context=self.context)
                    filters_display[key] = serializer.data
                except (ImportError, RuntimeError):
                    raise ImportError(f"Serializer {serializer_path} could not be imported.")
                    # filters_display[key] = value
                except Model.DoesNotExist:
                    filters_display[key] = f"{Model.__name__} with id {value.pk} not found."
                except Exception as e:
                    raise e
            else:
                filters_display[key] = value

        return filters_display

    def get_filters_display_two(self, obj):
        """
        Import the model dynamically and generate a name based on the model representation.
        """
        related_models = {
            "collection": "main.SourceImageCollection",
            "taxa_list": "main.TaxaList",
        }
        filters = obj.filters
        filters_display = {}

        from django.apps import apps

        for key, value in filters.items():
            if key in related_models:
                model_path = related_models[key]
                Model = apps.get_model(model_path)
                model_name = Model.__name__

                try:
                    instance = Model.objects.get(pk=value)
                    filters_display[key] = {"id": value, "name": str(instance)}
                except Model.DoesNotExist:
                    raise ValueError(f"{model_name} with id {value} not found.")
                except Exception as e:
                    raise e
            else:
                filters_display[key] = value

        return filters_display
