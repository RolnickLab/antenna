# Database Schema - Entity Relationship Diagram

This diagram shows the Antenna database schema organized by domain layers, with key relationships between them.

```mermaid
erDiagram
    %% ============================================================================
    %% LAYER 1: PROJECT & USERS
    %% ============================================================================
    User ||--o{ Project : "owns"
    User }o--o{ Project : "members (M2M)"
    User ||--o{ Identification : "creates"
    User ||--o{ DataExport : "creates"

    %% ============================================================================
    %% LAYER 2: INFRASTRUCTURE (Monitoring Stations)
    %% ============================================================================
    Project ||--o{ Site : "has"
    Project ||--o{ Device : "has"
    Project ||--o{ Deployment : "has"
    Project ||--o{ S3StorageSource : "has"

    Site ||--o{ Deployment : "located_at"
    Device ||--o{ Deployment : "uses"
    S3StorageSource ||--o{ Deployment : "data_source"

    %% ============================================================================
    %% LAYER 3: DATA COLLECTION (Images & Events)
    %% ============================================================================
    Deployment ||--o{ Event : "has"
    Deployment ||--o{ SourceImage : "captures"
    Project ||--o{ SourceImage : "owns"
    Event ||--o{ SourceImage : "groups"

    Project ||--o{ SourceImageCollection : "has"
    SourceImageCollection }o--o{ SourceImage : "contains (M2M)"

    %% ============================================================================
    %% LAYER 4: ML RESULTS (Detections & Classifications)
    %% ============================================================================
    SourceImage ||--o{ Detection : "has"
    Detection ||--o{ Classification : "has"

    Occurrence ||--o{ Detection : "aggregates"
    Project ||--o{ Occurrence : "has"
    Event ||--o{ Occurrence : "has"
    Deployment ||--o{ Occurrence : "has"

    %% ============================================================================
    %% LAYER 5: TAXONOMY (Species & Identifications)
    %% ============================================================================
    Project }o--o{ Taxon : "visible_taxa (M2M)"
    Taxon ||--o{ Taxon : "parent (self-ref)"
    Taxon ||--o{ Taxon : "synonym_of (self-ref)"

    Occurrence ||--o| Taxon : "determination"
    Occurrence ||--o{ Identification : "has"
    Classification ||--o| Taxon : "predicted"
    Identification ||--o| Taxon : "identified_as"

    Identification ||--o| Identification : "agrees_with (self-ref)"
    Identification ||--o| Classification : "agrees_with_prediction"

    Project ||--o{ TaxaList : "has"
    TaxaList }o--o{ Taxon : "includes (M2M)"

    Project ||--o{ Tag : "has"
    Tag }o--o{ Taxon : "tags (M2M)"

    %% ============================================================================
    %% LAYER 6: ML ORCHESTRATION (Pipelines & Algorithms)
    %% ============================================================================
    Project }o--o{ Pipeline : "enabled_via (through ProjectPipelineConfig)"
    Project }o--o{ ProcessingService : "uses (M2M)"

    Pipeline }o--o{ Algorithm : "composed_of (M2M)"
    Pipeline }o--o{ ProcessingService : "served_by (M2M)"

    Algorithm ||--o| AlgorithmCategoryMap : "uses"
    Algorithm ||--o{ Detection : "created_by"
    Algorithm ||--o{ Classification : "created_by"

    %% ============================================================================
    %% LAYER 7: JOBS & EXPORTS
    %% ============================================================================
    Project ||--o{ Job : "runs"
    Deployment ||--o{ Job : "processes"
    Pipeline ||--o{ Job : "executes"
    SourceImageCollection ||--o{ Job : "processes"
    SourceImage ||--o{ Job : "processes_single"

    Project ||--o{ DataExport : "exports"
    DataExport ||--|| Job : "generates_via"

    %% ============================================================================
    %% ENTITY DEFINITIONS (with key fields)
    %% ============================================================================

    User {
        bigint id PK
        string email UK
        string name
    }

    Project {
        bigint id PK
        string name
        bigint owner_id FK
        boolean is_draft
        int priority
    }

    Site {
        bigint id PK
        string name
        bigint project_id FK
        float latitude
        float longitude
    }

    Device {
        bigint id PK
        string name
        bigint project_id FK
    }

    Deployment {
        bigint id PK
        string name
        bigint project_id FK
        bigint research_site_id FK
        bigint device_id FK
        bigint data_source_id FK
        int events_count
        int captures_count
    }

    S3StorageSource {
        bigint id PK
        bigint project_id FK
        string endpoint_url
        string bucket
    }

    Event {
        bigint id PK
        bigint project_id FK
        bigint deployment_id FK
        string group_by UK
        datetime start
        datetime end
    }

    SourceImage {
        bigint id PK
        bigint deployment_id FK
        bigint event_id FK
        bigint project_id FK
        string path UK
        datetime timestamp
        int detections_count
    }

    SourceImageCollection {
        bigint id PK
        bigint project_id FK
        string name
        string method
        json kwargs
    }

    Detection {
        bigint id PK
        bigint source_image_id FK
        bigint occurrence_id FK
        bigint detection_algorithm_id FK
        json bbox
        string path
        float detection_score
    }

    Classification {
        bigint id PK
        bigint detection_id FK
        bigint taxon_id FK
        bigint algorithm_id FK
        bigint category_map_id FK
        float score
    }

    Occurrence {
        bigint id PK
        bigint determination_id FK
        bigint event_id FK
        bigint deployment_id FK
        bigint project_id FK
        float determination_score
    }

    Taxon {
        bigint id PK
        string name UK
        string rank
        bigint parent_id FK
        bigint synonym_of_id FK
        json parents_json
    }

    TaxaList {
        bigint id PK
        string name
    }

    Tag {
        bigint id PK
        string name UK
        bigint project_id FK
    }

    Identification {
        bigint id PK
        bigint user_id FK
        bigint taxon_id FK
        bigint occurrence_id FK
        bigint agreed_with_identification_id FK
        bigint agreed_with_prediction_id FK
        boolean withdrawn
    }

    Pipeline {
        bigint id PK
        string name UK
        string slug
        int version UK
        json default_config
    }

    Algorithm {
        bigint id PK
        string name UK
        string key
        int version UK
        string task_type
        bigint category_map_id FK
    }

    AlgorithmCategoryMap {
        bigint id PK
        json data
        array labels
        bigint labels_hash
    }

    ProcessingService {
        bigint id PK
        string name
        string endpoint_url
        boolean last_checked_live
        float last_checked_latency
    }

    ProjectPipelineConfig {
        bigint id PK
        bigint project_id FK
        bigint pipeline_id FK
        boolean enabled
        json config
    }

    Job {
        bigint id PK
        bigint project_id FK
        bigint deployment_id FK
        bigint pipeline_id FK
        bigint source_image_collection_id FK
        bigint source_image_single_id FK
        string status
        string job_type_key
        json progress
        string task_id
    }

    DataExport {
        bigint id PK
        bigint user_id FK
        bigint project_id FK
        string format
        json filters
        string file_url
    }
```

## Diagram Organization

- **Layer 1**: User authentication and project ownership
- **Layer 2**: Physical infrastructure (sites, devices, monitoring stations)
- **Layer 3**: Data collection (images, events, collections)
- **Layer 4**: ML processing results (detections, classifications, occurrences)
- **Layer 5**: Taxonomy and human review (species, identifications)
- **Layer 6**: ML pipeline orchestration (algorithms, pipelines, services)
- **Layer 7**: Asynchronous processing (jobs, exports)

## Key Relationship Patterns

- `||--o{` = One-to-Many (FK relationship)
- `}o--o{` = Many-to-Many (M2M relationship)
- `||--o|` = One-to-One or Many-to-One (required FK)
- `UK` = Unique constraint
- `PK` = Primary key
- `FK` = Foreign key

## Generating Updated Diagrams

If the schema changes, regenerate the Django model graph with:

```bash
docker compose run --rm django python manage.py graph_models -a -o models.dot --dot
dot -Tsvg models.dot > models.svg
```
