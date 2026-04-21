"""EML dataset metadata generation for DwC-A.

Currently emits EML 2.1.1; Task 8 upgrades to 2.2.0 with computed coverage and
a methods section.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from django.utils import timezone
from django.utils.text import slugify


def generate_eml_xml(project) -> str:
    """Generate minimal EML 2.1.1 metadata XML for the dataset."""
    project_slug = slugify(project.name)
    now = timezone.now().strftime("%Y-%m-%dT%H:%M:%S")

    eml = ET.Element("eml:eml")
    eml.set("xmlns:eml", "eml://ecoinformatics.org/eml-2.1.1")
    eml.set("xmlns:dc", "http://purl.org/dc/terms/")
    eml.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
    eml.set(
        "xsi:schemaLocation",
        "eml://ecoinformatics.org/eml-2.1.1 https://eml.ecoinformatics.org/eml-2.1.1/eml.xsd",
    )
    eml.set("packageId", f"urn:ami:dataset:{project_slug}:{now}")
    eml.set("system", "AMI")

    dataset = ET.SubElement(eml, "dataset")

    title = ET.SubElement(dataset, "title")
    title.text = project.name

    creator = ET.SubElement(dataset, "creator")
    org = ET.SubElement(creator, "organizationName")
    org.text = "Automated Monitoring of Insects (AMI)"
    if project.owner and project.owner.name:
        individual = ET.SubElement(creator, "individualName")
        surname = ET.SubElement(individual, "surName")
        surname.text = project.owner.name

    abstract = ET.SubElement(dataset, "abstract")
    para = ET.SubElement(abstract, "para")
    para.text = project.description or f"Biodiversity monitoring data from {project.name}."

    contact = ET.SubElement(dataset, "contact")
    contact_org = ET.SubElement(contact, "organizationName")
    contact_org.text = "Automated Monitoring of Insects (AMI)"

    rights = ET.SubElement(dataset, "intellectualRights")
    rights_para = ET.SubElement(rights, "para")
    project_license = (getattr(project, "license", "") or "").strip()
    if project_license:
        rights_para.text = project_license
    else:
        rights_para.text = "All rights reserved. No license specified."

    if getattr(project, "rights_holder", ""):
        additional = ET.SubElement(dataset, "additionalInfo")
        additional_para = ET.SubElement(additional, "para")
        additional_para.text = f"Rights holder: {project.rights_holder}"

    ET.indent(eml, space="  ")
    xml_str = ET.tostring(eml, encoding="unicode", xml_declaration=False)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str + "\n"
