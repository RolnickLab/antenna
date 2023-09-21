import html
import logging

import requests
from django.http import HttpResponse
from django.template.loader import render_to_string
from rest_framework import permissions, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import LimitOffsetPagination
from rest_framework.response import Response

from ami.labelstudio.models import LabelStudioConfig
from ami.labelstudio.serializers import (
    LabelStudioDetectionSerializer,
    LabelStudioOccurrenceSerializer,
    LabelStudioSourceImageSerializer,
)
from ami.main.api.views import DefaultReadOnlyViewSet
from ami.main.models import Deployment, Detection, Occurrence, Project, SourceImage, TaxaList, Taxon

logger = logging.getLogger(__name__)


def taxa_tree_to_xml(taxa_tree):
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

    def _node_to_xml(node, level=0):
        indent = "  " * level
        value = html.escape(str(node["taxon"]))
        xml = f'\n{indent}<Choice value="{value}">'
        for child in node["children"]:
            xml += _node_to_xml(child, level + 1)
        xml += f"{indent}</Choice>\n"
        return xml

    taxonomy_choices_xml = _node_to_xml(taxa_tree)
    return taxonomy_choices_xml


class LabelStudioFlatPaginator(LimitOffsetPagination):
    """
    A custom paginator that does not nest the data under a "results" key.

    This is needed for Label Studio to work. Generally you will want all of the results in one page.

    @TODO eventually each task should be it's own JSON file and this will not be needed.
    """

    limit = 100

    def get_paginated_response(self, data):
        return Response(data)


class LabelStudioSourceImageViewSet(DefaultReadOnlyViewSet):
    """Endpoint for importing data to annotate in Label Studio."""

    queryset = SourceImage.objects.select_related("event", "event__deployment", "event__deployment__data_source")
    serializer_class = LabelStudioSourceImageSerializer
    pagination_class = LabelStudioFlatPaginator
    filterset_fields = ["event", "deployment", "deployment__project"]

    @action(detail=False, methods=["get"], name="interval")
    def interval(self, request):
        """
        Return a sample of captures based on time intervals.
        URL parameters:
        - `deployment`: limit to a specific deployment<br>
        - `project`: limit to all deployments in a specific project<br>
        - `event_day_interval`: number of days between events<br>
        - `capture_minute_interval`: number of minutes between captures<br>
        - `limit`: maximum number of captures to return<br>
        Example: `/api/labelstudio/captures/interval/?project=1&event_day_interval=3&capture_minute_interval=30&limit=100`  # noqa
        Objects are returned in a format ready to import as a list of Label Studio tasks.
        """
        from ami.main.models import sample_captures, sample_events

        deployment_id = request.query_params.get("deployment", None)
        project_id = request.query_params.get("project", None)
        day_interval = int(request.query_params.get("event_day_interval", 3))
        minute_interval = int(request.query_params.get("capture_minute_interval", 30))
        max_num = int(request.query_params.get("limit", 100))
        captures = []
        if deployment_id:
            deployments = [Deployment.objects.get(id=deployment_id)]
        elif project_id:
            project = Project.objects.get(id=project_id)
            deployments = Deployment.objects.filter(project=project)
        else:
            deployments = Deployment.objects.all()
        for deployment in deployments:
            events = sample_events(deployment=deployment, day_interval=day_interval)
            for capture in sample_captures(
                deployment=deployment, events=list(events), minute_interval=minute_interval
            ):
                captures.append(capture)
                if len(captures) >= max_num:
                    break
        return Response(self.get_serializer(captures, many=True).data)


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
            taxa_tree = taxa_list.taxa.tree()  # type: ignore
        else:
            taxa_tree = Taxon.objects.tree()

        data = {
            "label_config": {
                "taxonomy_choices_xml": taxa_tree_to_xml(taxa_tree),
            }
        }

        content = render_to_string("labelstudio/species_classification.xml", data)

        return HttpResponse(content, content_type="text/xml")

    @action(detail=False, methods=["get"], name="all_in_one")
    def all_in_one(self, request):
        """ """
        taxa_list_id = request.query_params.get("taxa_list", None)
        if taxa_list_id:
            taxa_list = TaxaList.objects.get(id=taxa_list_id)
            taxa_tree = taxa_list.taxa.tree()  # type: ignore
        else:
            taxa_tree = Taxon.objects.tree()

        data = {
            "label_config": {
                "taxonomy_choices_xml": taxa_tree_to_xml(taxa_tree),
            }
        }

        content = render_to_string("labelstudio/all_in_one.xml", data)

        return HttpResponse(content, content_type="text/xml")


def get_labelstudio_config() -> LabelStudioConfig | None:
    return LabelStudioConfig.objects.first()


def populate_object_detection_tasks(debug=False):
    """
    Format source images as Label Studio tasks for object detection and post to the Label Studio API.
    """

    config = get_labelstudio_config()
    if not config:
        raise Exception("No LabelStudioConfig found")
    project_id = config.project_id
    # Label Studio API endpoint for importing tasks
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
