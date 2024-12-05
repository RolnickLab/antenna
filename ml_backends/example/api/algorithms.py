from .schemas import AlgorithmCategoryMap, AlgorithmResponse

RANDOM_DETECTOR = AlgorithmResponse(
    name="Random Detector",
    key="random-detector",
    task_type="detection",
    description="Return bounding boxes at random locations within the image bounds.",
    version=1,
    version_name="v1",
    url="https://huggingface.co/RolnickLab/random-detector",
    category_map=None,
)

RANDOM_BINARY_CLASSIFIER = AlgorithmResponse(
    name="Random binary classifier",
    key="random-binary-classifier",
    task_type="classification",
    description="Randomly return a classification of 'Moth' or 'Not a moth'",
    version=1,
    version_name="v1",
    url="https://huggingface.co/RolnickLab/random-binary-classifier",
    category_map=AlgorithmCategoryMap(
        data=[
            {"index": 0, "gbif_key": "1234", "label": "Moth", "source": "manual"},
            {"index": 1, "gbif_key": "4543", "label": "Not a moth", "source": "manual"},
        ],
        labels=["Moth", "Not a moth"],
        version="v1",
        description="A simple binary classifier",
        url="https://huggingface.co/RolnickLab/random-binary-classifier",
    ),
)

RANDOM_SPECIES_CLASSIFIER = AlgorithmResponse(
    name="Random species classifier",
    key="random-species-classifier",
    task_type="classification",
    description="A random species classifier",
    version=1,
    version_name="v1",
    url="https://huggingface.co/RolnickLab/random-species-classifier",
    category_map=AlgorithmCategoryMap(
        data=[
            {"index": 0, "gbif_key": "1234", "label": "Vanessa atalanta", "source": "manual"},
            {"index": 1, "gbif_key": "4543", "label": "Vanessa cardui", "source": "manual"},
            {"index": 2, "gbif_key": "7890", "label": "Vanessa itea", "source": "manual"},
        ],
        labels=["Vanessa atalanta", "Vanessa cardui", "Vanessa itea"],
        version="v1",
        description="A simple species classifier",
        url="https://huggigface.co/RolnickLab/random-species-classifier",
    ),
)


ALGORITHM_CHOICES = {
    RANDOM_DETECTOR.key: RANDOM_DETECTOR,
    RANDOM_BINARY_CLASSIFIER.key: RANDOM_BINARY_CLASSIFIER,
    RANDOM_SPECIES_CLASSIFIER.key: RANDOM_SPECIES_CLASSIFIER,
}
