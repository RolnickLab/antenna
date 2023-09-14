import json
from typing import Optional, Union

import sqlalchemy
import torch
import torch.utils.data
import torchvision.transforms
from sentry_sdk import start_transaction
from trapdata import logger
from trapdata.common.schemas import FilePath
from trapdata.common.utils import slugify
from trapdata.db.models.queue import QueueManager
from trapdata.ml.utils import StopWatch, get_device, get_or_download_file


class BatchEmptyException(Exception):
    pass


def zero_okay_collate(batch):
    """
    If the queue is cleared or shortened before the original batch count is complete
    then the dataloader will crash. This catches the empty batch more gracefully.

    @TODO switch to streaming IterableDataset type.
    """
    if any([not item for item in batch]):
        logger.debug(f"There's a None in the batch of len {len(batch)}")
        return None
    else:
        return torch.utils.data.default_collate(batch)


class InferenceBaseClass:
    """
    Base class for all batch-inference models.

    This outlines a common interface for all classifiers and object detectors.
    Generic methods like `get_weights_from_url` are defined here, but
    methods that return NotImplementedError must be overridden in a subclass
    that is specific to each inference model.

    See examples in `classification.py` and `localization.py`
    """

    db_path: str | sqlalchemy.engine.URL
    image_base_path: FilePath
    name = "Unknown Inference Model"
    description = ""
    model_type = None
    device = None
    weights_path = None
    weights = None
    labels_path = None
    category_map = {}
    model: torch.nn.Module
    transforms: torchvision.transforms.Compose
    batch_size = 4
    num_workers = 1
    user_data_path = None
    type = "unknown"
    stage = 0
    single = True
    queue: QueueManager
    dataset: torch.utils.data.Dataset
    dataloader: torch.utils.data.DataLoader

    def __init__(
        self,
        db_path: str | sqlalchemy.engine.URL,
        image_base_path: FilePath,
        **kwargs,
    ):
        self.db_path = db_path
        self.image_base_path = image_base_path

        for k, v in kwargs.items():
            setattr(self, k, v)

        logger.info(f"Initializing inference class {self.name}")

        self.device = self.device or get_device()
        self.category_map = self.get_labels(self.labels_path)
        self.weights = self.get_weights(self.weights_path)
        self.transforms = self.get_transforms()
        self.queue = self.get_queue()
        self.dataset = self.get_dataset()
        self.dataloader = self.get_dataloader()
        logger.info(
            f"Loading {self.type} model (stage: {self.stage}) for {self.name} with {len(self.category_map or [])} categories"
        )
        self.model = self.get_model()

    @classmethod
    def get_key(cls):
        if hasattr(cls, "key") and cls.key:  # type: ignore
            return cls.key  # type: ignore
        else:
            return slugify(cls.name)

    def get_weights(self, weights_path):
        if weights_path:
            return get_or_download_file(weights_path, self.user_data_path, prefix="models")
        else:
            logger.warn(f"No weights specified for model {self.name}")

    def get_labels(self, labels_path):
        if labels_path:
            local_path = get_or_download_file(labels_path, self.user_data_path, prefix="models")

            with open(local_path) as f:
                labels = json.load(f)

            # @TODO would this be faster as a list? especially when getting the labels of multiple
            # indexes in one prediction
            index_to_label = {index: label for label, index in labels.items()}

            return index_to_label
        else:
            return {}

    def get_model(self) -> torch.nn.Module:
        """
        This method must be implemented by a subclass.

        Example:

        model = torch.nn.Module()
        checkpoint = torch.load(self.weights, map_location=self.device)
        model.load_state_dict(checkpoint["model_state_dict"])
        model = model.to(self.device)
        model.eval()
        return model
        """
        raise NotImplementedError

    def get_transforms(self) -> torchvision.transforms.Compose:
        """
        This method must be implemented by a subclass.

        Example:

        transforms = torchvision.transforms.Compose(
            [
                torchvision.transforms.ToTensor(),
            ]
        )
        return transforms
        """
        raise NotImplementedError

    def get_queue(self) -> QueueManager:
        """
        This method must be implemented by a subclass.
        Example:

        from trapdata.db.models.queue import DetectedObjectQueue
        def get_queue(self):
            return DetectedObjectQueue(self.db_path, self.image_base_path)
        """
        raise NotImplementedError

    def get_dataset(self) -> torch.utils.data.Dataset:
        """
        This method must be implemented by a subclass.

        Example:

        dataset = torch.utils.data.Dataset()
        return dataset
        """
        raise NotImplementedError

    def get_dataloader(self):
        """
        Prepare dataloader for streaming/iterable datasets from database
        """
        if self.single:
            logger.info(f"Preparing dataloader with batch size of {self.batch_size} in single worker mode.")
        else:
            logger.info(f"Preparing dataloader with batch size of {self.batch_size} and {self.num_workers} workers.")
        self.dataloader = torch.utils.data.DataLoader(
            self.dataset,
            num_workers=0 if self.single else self.num_workers,
            persistent_workers=False if self.single else True,
            shuffle=False,
            pin_memory=False if self.single else True,  # @TODO review this
            batch_size=None,  # Recommended setting for streaming datasets
            batch_sampler=None,  # Recommended setting for streaming datasets
        )
        return self.dataloader

    def predict_batch(self, batch):
        batch_input = batch.to(
            self.device,
            non_blocking=True,  # Block while in development, are we already in a background process?
        )
        batch_output = self.model(batch_input)
        return batch_output

    def post_process_single(self, item):
        return item

    def post_process_batch(self, batch_output):
        return [self.post_process_single(item) for item in batch_output]
        # Had problems with this generator and multiprocessing
        # for item in batch_output:
        #     yield self.post_process_single(item)

    def save_results(self, item_ids, batch_output):
        logger.warn("No save method configured for model. Doing nothing with results")
        return None

    @torch.no_grad()
    def run(self):
        torch.cuda.empty_cache()

        for i, batch in enumerate(self.dataloader):
            if not batch:
                # @TODO review this once we switch to streaming IterableDataset
                logger.info(f"Batch {i+1} is empty, skipping")
                continue

            item_ids, batch_input = batch

            logger.info(f"Processing batch {i+1}, about {len(self.dataloader)} remaining")

            # @TODO the StopWatch doesn't seem to work when there are multiple workers,
            # it always returns 0 seconds.
            with StopWatch() as batch_time:
                with start_transaction(op="inference_batch", name=self.name):
                    batch_output = self.predict_batch(batch_input)

            seconds_per_item = batch_time.duration / len(batch_output)
            logger.info(f"Inference time for batch: {batch_time}, " f"Seconds per item: {round(seconds_per_item, 2)}")

            batch_output = list(self.post_process_batch(batch_output))
            item_ids = item_ids.tolist()
            logger.info(f"Saving {len(item_ids)} results")
            self.save_results(item_ids, batch_output)
            logger.info(f"{self.name} Batch -- Done")

        logger.info(f"{self.name} -- Done")
