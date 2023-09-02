import logging

import requests
from django.http import HttpResponse
from django.template.loader import render_to_string
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from ami.labelstudio.models import LabelStudioConfig
from ami.labelstudio.serializers import (
    LabelStudioDetectionSerializer,
    LabelStudioOccurrenceSerializer,
    LabelStudioSourceImageSerializer,
)
from ami.main.api.views import DefaultReadOnlyViewSet
from ami.main.models import Detection, Occurrence, SourceImage, TaxaList, Taxon

logger = logging.getLogger(__name__)


class LabelStudioFlatPaginator(PageNumberPagination):
    """
    A custom paginator that does not nest the data under a "results" key.

    This is needed for Label Studio to work. Generally you will want all of the results in one page.

    @TODO eventually each task should be it's own JSON file and this will not be needed.
    """

    page_size = 1000
    page_size_query_param = "page_size"
    page_query_param = "page"
    max_page_size = 10000

    def get_paginated_response(self, data):
        return Response(data)


class LabelStudioSourceImageViewSet(DefaultReadOnlyViewSet):
    """Endpoint for importing data to annotate in Label Studio."""

    queryset = SourceImage.objects.select_related("event", "event__deployment", "event__deployment__data_source")
    serializer_class = LabelStudioSourceImageSerializer
    pagination_class = LabelStudioFlatPaginator
    filterset_fields = ["event", "deployment", "deployment__project"]


class LabelStudioDetectionViewSet(DefaultReadOnlyViewSet):
    """ """

    queryset = Detection.objects.all()
    serializer_class = LabelStudioDetectionSerializer
    filterset_fields = ["source_image__event", "source_image__deployment", "source_image__deployment__project"]
    pagination_class = LabelStudioFlatPaginator


class LabelStudioOccurrenceViewSet(DefaultReadOnlyViewSet):
    """ """

    queryset = Occurrence.objects.all()
    serializer_class = LabelStudioOccurrenceSerializer
    filterset_fields = ["event", "deployment", "project"]
    pagination_class = LabelStudioFlatPaginator


class LabelStudioHooksViewSet(viewsets.ViewSet):
    """Endpoints for Label Studio to send data to."""

    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=["post"], name="all")
    def all(self, request):
        data = request.data
        hook_name = data.get("action")
        logger.info(f"Received hook from Label Studio: {hook_name}")
        if hook_name == "PROJECT_UPDATED":
            return self.update_project(request)
        else:
            import json

            logger.info(json.dumps(data, indent=2))

            return Response({"action": "hook_name", "data": data})

    def update_project(self, request):
        """ """
        # from ami.labelstudio.hooks import update_project_after_save
        project = request.data["project"]
        # update_project_after_save(project=project, request=request)
        return Response({"action": "update_project", "data": project})


class LabelStudioConfigViewSet(viewsets.ViewSet):
    """ """

    permission_classes = [permissions.AllowAny]

    @action(detail=False, methods=["get"], name="objectdetection")
    def objectdetection(self, request):
        """ """
        data = {
            "label_config": {
                "labels": [
                    {"id": 1, "name": "Object"},
                ],
            }
        }

        content = render_to_string("labelstudio/initial_object_detection.xml", data)

        return HttpResponse(content, content_type="text/xml")

    @action(detail=False, methods=["get"], name="binaryclassification")
    def binaryclassification(self, request):
        """ """
        data = {
            "label_config": {
                "labels": [
                    {"id": 1, "name": "Moth"},
                    {"id": 2, "name": "Non-Moth"},
                ],
            }
        }

        content = render_to_string("labelstudio/binary_classification.xml", data)

        return HttpResponse(content, content_type="text/xml")

    @action(detail=False, methods=["get"], name="speciesclassification")
    def speciesclassification(self, request):
        """ """
        taxa_list_id = request.query_params.get("taxa_list", None)
        if taxa_list_id:
            taxa_list = TaxaList.objects.get(id=taxa_list_id)
            taxa_tree = taxa_list.taxa.tree()
        else:
            taxa_tree = Taxon.objects.tree()

        """
        # Recursively build the XML from taxa_tree
        # Which looks like:
        # {"taxon": <Taxon: 1>, "children": [{"taxon": <Taxon: 2>, "children": []}]}}

        # Example of a nested Choice XML
        <Choice value="Parent">
        <Choice value="Child">
            <Choice value="Grandchild" />
        </Choice>
        </Choice>
        """

        def _node_to_xml(node):
            xml = f'<Choice value="{str(node["taxon"])}">\n'
            for child in node["children"]:
                xml += _node_to_xml(child)
            xml += "</Choice>\n"
            return xml

        taxonomy_choices_xml = _node_to_xml(taxa_tree)
        data = {
            "label_config": {
                "taxonomy_choices_xml": taxonomy_choices_xml,
            }
        }

        content = render_to_string("labelstudio/species_classification.xml", data)

        return HttpResponse(content, content_type="text/xml")


def get_labelstudio_config() -> LabelStudioConfig:
    config = LabelStudioConfig.objects.first()
    if not config:
        raise Exception("No LabelStudioConfig found")


def populate_object_detection_tasks(debug=False):
    """
    Format source images as Label Studio tasks for object detection and post to the Label Studio API.
    """

    config = get_labelstudio_config()
    project_id = config.object_detection_project_id
    import_endpoint = f"{config.base_url}/api/projects/{project_id}/import"

    data = {
        "data": [],
    }
    from ami.labelstudio.serializers import LabelStudioSourceImageSerializer

    if debug:
        source_images = SourceImage.objects.order_by("?")[:1]
        logger.info(f"Sending debug task for {source_images[0]} to {import_endpoint}")
    else:
        source_images = SourceImage.objects.all()

    for source_image in source_images:
        serializer = LabelStudioSourceImageSerializer(source_image)
        data["data"].append(serializer.data)

    if debug:
        logger.info(f"Would have sent {len(data['data'])} tasks to {import_endpoint}")
    else:
        requests.post(
            import_endpoint,
            headers={"Authorization": f"Token {config.access_token}"},
            json=data,
        )


def populate_binary_classification_tasks():
    pass


def populate_species_classification_tasks():
    pass
