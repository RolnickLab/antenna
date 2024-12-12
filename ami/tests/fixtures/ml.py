from ami.ml.schemas import AlgorithmCategoryMapResponse, AlgorithmResponse

RANDOM_DETECTOR = AlgorithmResponse(
    name="Random Detector",
    key="random-detector",
    task_type="detection",
    description="Return bounding boxes at random locations within the image bounds.",
    version=1,
    version_name="v1",
    uri="https://huggingface.co/RolnickLab/random-detector",
    category_map=None,
)

RANDOM_BINARY_CLASSIFIER = AlgorithmResponse(
    name="Random binary classifier",
    key="random-binary-classifier",
    task_type="classification",
    description="Randomly return a classification of 'Moth' or 'Not a moth'",
    version=1,
    version_name="v1",
    uri="https://huggingface.co/RolnickLab/random-binary-classifier",
    category_map=AlgorithmCategoryMapResponse(
        data=[
            {"index": 0, "gbif_key": "1234", "label": "Moth", "source": "manual"},
            {"index": 1, "gbif_key": "4543", "label": "Not a moth", "source": "manual"},
        ],
        labels=["Moth", "Not a moth"],
        version="v1",
        description="Class mapping  for a simple binary classifier",
        uri="https://huggingface.co/RolnickLab/random-binary-classifier/classes.txt",
    ),
)

RANDOM_SPECIES_CLASSIFIER = AlgorithmResponse(
    name="Random species classifier",
    key="random-species-classifier",
    task_type="classification",
    description="A random species classifier",
    version=1,
    version_name="v1",
    uri="https://huggingface.co/RolnickLab/random-species-classifier",
    category_map=AlgorithmCategoryMapResponse(
        data=[
            {"index": 0, "gbif_key": "1234", "label": "Vanessa atalanta", "source": "manual"},
            {"index": 1, "gbif_key": "4543", "label": "Vanessa cardui", "source": "manual"},
            {"index": 2, "gbif_key": "7890", "label": "Vanessa itea", "source": "manual"},
        ],
        labels=["Vanessa atalanta", "Vanessa cardui", "Vanessa itea"],
        version="v1",
        description="",
        uri="https://huggigface.co/RolnickLab/random-species-classifier/classes.txt",
    ),
)


CONSTANT_SPECIES_CLASSIFIER = AlgorithmResponse(
    name="Constant species classifier",
    key="constant-species-classifier",
    task_type="classification",
    description="A species classifier that always returns the same species",
    version=1,
    version_name="v1",
    uri="https://huggingface.co/RolnickLab/constant-species-classifier",
    category_map=AlgorithmCategoryMapResponse(
        data=[
            {"index": 0, "gbif_key": "1234", "label": "Vanessa atalanta", "source": "manual"},
            {"index": 1, "gbif_key": "4543", "label": "Vanessa cardui", "source": "manual"},
            {"index": 2, "gbif_key": "7890", "label": "Vanessa itea", "source": "manual"},
        ],
        labels=["Vanessa atalanta", "Vanessa cardui", "Vanessa itea"],
        version="v1",
        description="",
        uri="https://huggigface.co/RolnickLab/constant-species-classifier/classes.txt",
    ),
)
ALGORITHM_CHOICES = {
    RANDOM_DETECTOR.key: RANDOM_DETECTOR,
    RANDOM_BINARY_CLASSIFIER.key: RANDOM_BINARY_CLASSIFIER,
    RANDOM_SPECIES_CLASSIFIER.key: RANDOM_SPECIES_CLASSIFIER,
    CONSTANT_SPECIES_CLASSIFIER.key: CONSTANT_SPECIES_CLASSIFIER,
}
