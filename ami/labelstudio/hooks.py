import requests
from rich import print

from ami.main.models import TaxaList, Taxon


def update_taxonomy_choices(endpoint: str, token: str, project_id: int, taxa_list_id: int | None = None):
    """
    Update the label_config for a project in Label Studio.
    """

    # Init session with auth token
    session = requests.Session()
    session.headers.update({"Authorization": f"Token {token}"})

    project = session.get(f"{endpoint}/api/projects/{project_id}").json()
    label_config = project["label_config"]
    print("Current label_config:", label_config)

    # Nested choices should look like this:
    """
    <Choice value="Archaea" />
    <Choice value="Bacteria" />
    <Choice value="Eukarya">
        <Choice value="Human" />
        <Choice value="Oppossum" />
        <Choice value="Extraterrestrial" />
    </Choice>
    """
    html = ""
    TaxaList.objects.get(id=taxa_list_id)
    # @TODO filter by taxa_list or move tree method to list manager
    for node in Taxon.objects.tree():
        taxon = node["taxon"]
        children = node["children"]
        if children:
            html += f'<Choice value="{taxon.name}">'
            for child in children:
                html += f'<Choice value="{child.name}" />'
            html += "</Choice>"
        else:
            html += f'<Choice value="{taxon.name}" />'

    # Replace the choices in the label_config
    label_config = label_config.replace("{{ taxonomy_choices }}", html)
    print("New label_config:", label_config)

    # # Update the project
    # resp = session.patch(
    #     f"{endpoint}/api/projects/{project_id}",
    #     json={"label_config": label_config},
    # )

    # resp.raise_for_status()
    # return resp.json()
