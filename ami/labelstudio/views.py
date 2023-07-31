from django.http import HttpResponse
from django.template.loader import render_to_string
from rest_framework import permissions, viewsets
from rest_framework.decorators import action

from ami.main.models import TaxaList, Taxon


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
