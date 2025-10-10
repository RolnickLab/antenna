# Object Model Diagram: ML Pipeline System

```mermaid
classDiagram
    %% Core ML Pipeline Classes
    class Pipeline {
        +string slug
        +string name
        +string description
        +int version
        +string version_name
        +stages[] PipelineStage
        +default_config PipelineRequestConfigParameters
        --
        +get_config(project_id) PipelineRequestConfigParameters
        +collect_images() Iterable~SourceImage~
        +process_images() PipelineResultsResponse
        +choose_processing_service_for_pipeline() ProcessingService
    }

    class Algorithm {
        +string key
        +string name
        +AlgorithmTaskType task_type
        +string description
        +int version
        +string version_name
        +string uri
        --
        +detection_task_types[] AlgorithmTaskType
        +classification_task_types[] AlgorithmTaskType
        +has_valid_category_map() boolean
    }

    class AlgorithmCategoryMap {
        +data JSONField
        +labels[] string
        +int labels_hash
        +string version
        +string description
        +string uri
        --
        +make_labels_hash() int
        +get_category() int
        +with_taxa() dict[]
    }

    class PipelineStage {
        +string key
        +string name
        +string description
        +boolean enabled
        +params[] ConfigurableStageParam
    }

    %% Job System Classes
    class Job {
        +string name
        +string queue
        +datetime scheduled_at
        +datetime started_at
        +datetime finished_at
        +JobState status
        +JobProgress progress
        +JobLogs logs
        +params JSONField
        +result JSONField
        +string task_id
        +int delay
        +int limit
        +boolean shuffle
        +string job_type_key
        --
        +job_type() JobType
        +update_status() void
        +logger JobLogger
    }

    %% Configuration Classes
    class ProjectPipelineConfig {
        +boolean enabled
        +config JSONField
        --
        +get_config() dict
    }

    class Project {
        +string name
        +string slug
        +feature_flags JSONField
        --
        +default_processing_pipeline Pipeline
    }

    %% Enums
    class AlgorithmTaskType {
        <<enumeration>>
        DETECTION
        LOCALIZATION
        SEGMENTATION
        CLASSIFICATION
        EMBEDDING
        TRACKING
        TAGGING
        REGRESSION
        CAPTIONING
        GENERATION
        TRANSLATION
        SUMMARIZATION
        QUESTION_ANSWERING
        DEPTH_ESTIMATION
        POSE_ESTIMATION
        SIZE_ESTIMATION
        OTHER
        UNKNOWN
    }


    %% Relationships
    Pipeline "M" -- "M" Algorithm : algorithms
    Pipeline "1" -- "many" PipelineStage : stages
    Pipeline "1" -- "many" Job : jobs
    Pipeline "1" -- "many" ProjectPipelineConfig : project_pipeline_configs

    Algorithm "1" -- "0..1" AlgorithmCategoryMap : category_map
    Algorithm "1" -- "1" AlgorithmTaskType : task_type

    Job "0..1" -- "1" Pipeline : pipeline
    Job "1" -- "1" Project : project

    Project "1" -- "many" ProjectPipelineConfig : project_pipeline_configs
    ProjectPipelineConfig "1" -- "1" Pipeline : pipeline
    ProjectPipelineConfig "1" -- "1" Project : project

    %% Notes
    note for Pipeline "Identified by unique slug\nAuto-generated from name + version + UUID"
    note for Algorithm "Identified by unique key\nAuto-generated from name + version"
    note for Job "MLJob is the primary job type\nfor running ML pipelines"
```

## Key Relationships Summary

### Core ML Pipeline Flow:
1. **ProcessingService** → registers → **Pipeline** → contains → **Algorithm**
2. **Project** → configures → **Pipeline** through **ProjectPipelineConfig**
3. **Job** → executes → **Pipeline** → uses → **ProcessingService**

### Model Identification:
- **Pipeline**: Identified by unique `slug` (string) - auto-generated from `name + version + UUID`
- **Algorithm**: Identified by unique `key` (string) - auto-generated from `name + version`
- **Job**: Uses standard Django `id` but also has `task_id` for Celery integration

### Stage Management:
- **Pipeline** contains **PipelineStage** objects (for configuration display)
- **Job** tracks execution through **JobProgressStageDetail** objects (for runtime progress)
- Both share the same base **ConfigurableStage** schema

### Algorithm Classification:
- **Algorithm** has task types (detection, classification, etc.)
- Classification algorithms require **AlgorithmCategoryMap** for label mapping
- Detection algorithms don't require category maps

### Job Execution Flow:
1. **Job** is created with a **Pipeline** reference
2. **Pipeline** selects appropriate **ProcessingService**
3. **ProcessingService** executes algorithms and returns results
4. **Job** tracks progress through **JobProgress** and **JobProgressStageDetail**
