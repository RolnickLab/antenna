from .schemas import AlgorithmCategoryMapResponse, AlgorithmConfigResponse

RANDOM_DETECTOR = AlgorithmConfigResponse(
    name="Random Detector",
    key="random-detector",
    task_type="detection",
    description="Return bounding boxes at random locations within the image bounds.",
    version=1,
    version_name="v1",
    uri="https://huggingface.co/RolnickLab/random-detector",
    category_map=None,
)

CONSTANT_DETECTOR = AlgorithmConfigResponse(
    name="Constant Detector",
    key="constant-detector",
    task_type="detection",
    description="Return a fixed bounding box at a fixed location within the image bounds.",
    version=1,
    version_name="v1",
    uri="https://huggingface.co/RolnickLab/constant-detector",
    category_map=None,
)

RANDOM_BINARY_CLASSIFIER = AlgorithmConfigResponse(
    name="Random binary classifier",
    key="random-binary-classifier",
    task_type="classification",
    description="Randomly return a classification of 'Moth' or 'Not a moth'",
    version=1,
    version_name="v1",
    uri="https://huggingface.co/RolnickLab/random-binary-classifier",
    category_map=AlgorithmCategoryMapResponse(
        data=[
            {
                "index": 0,
                "gbif_key": "1234",
                "label": "Moth",
                "source": "manual",
                "taxon_rank": "SUPERFAMILY",
            },
            {
                "index": 1,
                "gbif_key": "4543",
                "label": "Not a moth",
                "source": "manual",
                "taxon_rank": "ORDER",
            },
        ],
        labels=["Moth", "Not a moth"],
        version="v1",
        description="A simple binary classifier",
        uri="https://huggingface.co/RolnickLab/random-binary-classifier",
    ),
)

CONSTANT_CLASSIFIER = AlgorithmConfigResponse(
    name="Constant classifier",
    key="constant-classifier",
    task_type="classification",
    description="Always return a classification of 'Moth'",
    version=1,
    version_name="v1",
    uri="https://huggingface.co/RolnickLab/constant-classifier",
    category_map=AlgorithmCategoryMapResponse(
        data=[
            {
                "index": 0,
                "gbif_key": "1234",
                "label": "Moth",
                "source": "manual",
                "taxon_rank": "SUPERFAMILY",
            }
        ],
        labels=["Moth"],
        version="v1",
        description="A classifier that always returns 'Moth'",
        uri="https://huggingface.co/RolnickLab/constant-classifier",
    ),
)

RANDOM_SPECIES_CLASSIFIER = AlgorithmConfigResponse(
    name="Random species classifier",
    key="random-species-classifier",
    task_type="classification",
    description="A random species classifier",
    version=1,
    version_name="v1",
    uri="https://huggingface.co/RolnickLab/random-species-classifier",
    category_map=AlgorithmCategoryMapResponse(
        data=[
            {
                "index": 0,
                "gbif_key": "1234",
                "label": "Vanessa atalanta",
                "source": "manual",
                "taxon_rank": "SPECIES",
            },
            {
                "index": 1,
                "gbif_key": "4543",
                "label": "Vanessa cardui",
                "source": "manual",
                "taxon_rank": "SPECIES",
            },
            {
                "index": 2,
                "gbif_key": "7890",
                "label": "Vanessa itea",
                "source": "manual",
                "taxon_rank": "SPECIES",
            },
        ],
        labels=["Vanessa atalanta", "Vanessa cardui", "Vanessa itea"],
        version="v1",
        description="A simple species classifier",
        uri="https://huggingface.co/RolnickLab/random-species-classifier",
    ),
)
