# Darwin Core Archive (DwC-A) Format Reference

## What is DwC-A?

A ZIP archive containing standardized biodiversity data files. The standard format for sharing occurrence and sampling-event data with GBIF, OBIS, and other biodiversity data aggregators.

## Archive Structure

```
archive.zip
├── meta.xml          # Required: describes file structure and term mappings
├── eml.xml           # Recommended: dataset metadata (Ecological Metadata Language)
├── event.txt         # Core file (tab-separated)
├── occurrence.txt    # Extension file (tab-separated)
└── (other extensions like multimedia.txt, measurementorfact.txt)
```

## Star Schema

One **core** file, surrounded by **extension** files. Extensions link back to the core via an ID column.

For sampling-event datasets (like AMI):
- **Core**: Event (one row per sampling event)
- **Extension**: Occurrence (many occurrences per event)

## meta.xml Specification

```xml
<?xml version="1.0" encoding="UTF-8"?>
<archive xmlns="http://rs.tdwg.org/dwc/text/"
    xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
    xmlns:xs="http://www.w3.org/2001/XMLSchema"
    xsi:schemaLocation="http://rs.tdwg.org/dwc/text/ http://rs.tdwg.org/dwc/text/tdwg_dwc_text.xsd"
    metadata="eml.xml">

  <core rowType="http://rs.tdwg.org/dwc/terms/Event"
        encoding="UTF-8"
        fieldsTerminatedBy="\t"
        linesTerminatedBy="\n"
        ignoreHeaderLines="1">
    <files>
      <location>event.txt</location>
    </files>
    <id index="0" />
    <field index="0" term="http://rs.tdwg.org/dwc/terms/eventID" />
    <field index="1" term="http://rs.tdwg.org/dwc/terms/eventDate" />
    <!-- more fields... -->
  </core>

  <extension rowType="http://rs.tdwg.org/dwc/terms/Occurrence"
             encoding="UTF-8"
             fieldsTerminatedBy="\t"
             linesTerminatedBy="\n"
             ignoreHeaderLines="1">
    <files>
      <location>occurrence.txt</location>
    </files>
    <coreid index="0" />
    <field index="1" term="http://rs.tdwg.org/dwc/terms/occurrenceID" />
    <field index="2" term="http://rs.tdwg.org/dwc/terms/scientificName" />
    <!-- more fields... -->
  </extension>

</archive>
```

### Key Attributes

| Attribute | Default | Notes |
|-----------|---------|-------|
| `rowType` | Required | URI: `http://rs.tdwg.org/dwc/terms/Event`, `...Occurrence`, `...Taxon` |
| `fieldsTerminatedBy` | `,` | Use `\t` for TSV (recommended for DwC-A) |
| `linesTerminatedBy` | `\n` | Standard newline |
| `fieldsEnclosedBy` | `"` | Quote character |
| `encoding` | `UTF-8` | Always use UTF-8 |
| `ignoreHeaderLines` | `0` | Set to `1` if header row present |
| `dateFormat` | `YYYY-MM-DD` | ISO 8601 |

### Field Element

- `index` (0-based): column position in the data file
- `term`: Darwin Core term URI
- `default`: constant value for all rows (no index needed)

### ID Elements

- `<id index="0" />` in core: column containing unique record ID
- `<coreid index="0" />` in extensions: column containing the core record's ID (foreign key)

## EML Metadata (eml.xml)

Describes the dataset: title, abstract, creators, geographic/temporal coverage, methods, etc. GBIF provides an EML profile. Minimum useful content:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<eml:eml xmlns:eml="https://eml.ecoinformatics.org/eml-2.2.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="https://eml.ecoinformatics.org/eml-2.2.0 https://eml.ecoinformatics.org/eml-2.2.0/eml.xsd"
         packageId="urn:ami:dataset:{project_id}" system="AMI">
  <dataset>
    <title>{project.name}</title>
    <creator>
      <organizationName>{project.owner or institution}</organizationName>
    </creator>
    <abstract>
      <para>{project.description}</para>
    </abstract>
    <intellectualRights>
      <para>License information here</para>
    </intellectualRights>
  </dataset>
</eml:eml>
```

## Key DwC Terms for AMI Data

### Event Terms (Core)

| DwC Term | AMI Source | Notes |
|----------|-----------|-------|
| eventID | `urn:ami:event:{project_slug}:{event.id}` | Globally unique |
| parentEventID | | Empty for now (could link to deployment-level events) |
| eventType | `"CameraTrapSession"` | Or custom vocabulary |
| eventDate | `event.start` / `event.end` as ISO interval | `2024-06-15/2024-06-16` |
| year | from `event.start` | |
| month | from `event.start` | |
| day | from `event.start` | |
| samplingProtocol | `"automated light trap with camera"` | Project-level constant |
| sampleSizeValue | `event.captures_count` | Number of images |
| sampleSizeUnit | `"images"` | |
| samplingEffort | `event.duration` formatted | e.g. "12 hours" |
| eventRemarks | | |
| **Location terms (on event)** | | |
| locationID | `deployment.name` or `site.name` | |
| decimalLatitude | `deployment.latitude` | |
| decimalLongitude | `deployment.longitude` | |
| geodeticDatum | `"WGS84"` | Assumed |
| coordinateUncertaintyInMeters | | Not currently stored |

### Occurrence Terms (Extension)

| DwC Term | AMI Source | Notes |
|----------|-----------|-------|
| eventID | Same as core eventID | Links occurrence to event |
| occurrenceID | `urn:ami:occurrence:{project_slug}:{occurrence.id}` | Globally unique |
| basisOfRecord | `"MachineObservation"` | All records |
| occurrenceStatus | `"present"` | Always present (we don't record absences) |
| scientificName | `occurrence.determination.name` | |
| taxonRank | `occurrence.determination.rank` | Lowercase |
| kingdom | from `determination.parents_json` | Walk parent chain |
| phylum | from `determination.parents_json` | |
| class | from `determination.parents_json` | |
| order | from `determination.parents_json` | |
| family | from `determination.parents_json` | |
| genus | from `determination.parents_json` | |
| specificEpithet | split from species name | Second word of binomial |
| vernacularName | `determination.common_name_en` | |
| taxonID | `determination.gbif_taxon_key` or internal URN | |
| individualCount | `occurrence.detections_count` | Number of detections |
| associatedMedia | Detection image URLs | Pipe-separated |
| identifiedBy | `"AMI ML Pipeline"` or identification user | |
| dateIdentified | `occurrence.created_at` or identification date | |
| identificationRemarks | Score info, algorithm used | |
| identificationVerificationStatus | Verified/Not verified | Based on identifications |

## Validation

- Core IDs must be unique
- Extension coreid values must reference existing core IDs
- No literal "NULL" values
- UTF-8 encoding throughout
- GBIF validator: https://www.gbif.org/tools/data-validator

## References

- DwC Text Guide: https://dwc.tdwg.org/text/
- GBIF DwC-A Guide: https://ipt.gbif.org/manual/en/ipt/latest/dwca-guide
- DwC Terms: https://dwc.tdwg.org/terms/
- Full terms reference downloaded to: `docs/claude/dwc-terms-reference.md`
