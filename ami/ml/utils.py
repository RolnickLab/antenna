import datetime
import os
import pathlib
import time
import urllib.request
from dataclasses import dataclass
from typing import Optional

import pandas as pd
import torch
import torchvision
from trapdata import logger


def get_device(device_str=None) -> torch.device:
    """
    Select CUDA if available.

    @TODO add macOS Metal?
    @TODO check Kivy settings to see if user forced use of CPU
    """
    if not device_str:
        device_str = "cuda" if torch.cuda.is_available() else "cpu"
    device = torch.device(device_str)
    logger.info(f"Using device '{device}' for inference")
    return device


def get_or_download_file(path, destination_dir=None, prefix=None) -> pathlib.Path:
    """
    >>> filename, headers = get_weights("https://drive.google.com/file/d/1KdQc56WtnMWX9PUapy6cS0CdjC8VSdVe/view?usp=sharing")

    """
    if not path:
        raise Exception("Specify a URL or path to fetch file from.")

    # If path is a local path instead of a URL then urlretrieve will just return that path
    destination_dir = destination_dir or os.environ.get("LOCAL_WEIGHTS_PATH")
    fname = path.rsplit("/", 1)[-1]
    if destination_dir:
        destination_dir = pathlib.Path(destination_dir)
        if prefix:
            destination_dir = destination_dir / prefix
        if not destination_dir.exists():
            logger.info(f"Creating local directory {str(destination_dir)}")
            destination_dir.mkdir(parents=True, exist_ok=True)
        local_filepath = pathlib.Path(destination_dir) / fname
    else:
        raise Exception("No destination directory specified by LOCAL_WEIGHTS_PATH or app settings.")

    if local_filepath and local_filepath.exists():
        logger.info(f"Using existing {local_filepath}")
        return local_filepath

    else:
        logger.info(f"Downloading {path} to {destination_dir}")
        resulting_filepath, headers = urllib.request.urlretrieve(url=path, filename=local_filepath)
        resulting_filepath = pathlib.Path(resulting_filepath)
        logger.info(f"Downloaded to {resulting_filepath}")
        return resulting_filepath


def synchronize_clocks():
    if torch.cuda.is_available():
        torch.cuda.synchronize()
    else:
        pass


def bbox_relative(bbox_absolute, img_width, img_height):
    """
    Convert bounding box from absolute coordinates (x1, y1, x2, y2)
    like those used by pytorch, to coordinates that are relative
    percentages of the original image size like those used by
    the COCO cameratraps format.
    https://github.com/Microsoft/CameraTraps/blob/main/data_management/README.md#coco-cameratraps-format
    """

    box_numpy = bbox_absolute.detach().cpu().numpy()
    bbox_percent = [
        round(box_numpy[0] / img_width, 4),
        round(box_numpy[1] / img_height, 4),
        round(box_numpy[2] / img_width, 4),
        round(box_numpy[3] / img_height, 4),
    ]
    return bbox_percent


def crop_bbox(image, bbox):
    """
    Create cropped image from region specified in a bounding box.

    Bounding boxes are assumed to be in the format:
    [(top-left-coordinate-pair), (bottom-right-coordinate-pair)]
    or: [x1, y1, x2, y2]

    The image is assumed to be a numpy array that can be indexed using the
    coordinate pairs.
    """

    x1, y1, x2, y2 = bbox

    cropped_image = image[
        :,
        int(y1) : int(y2),
        int(x1) : int(x2),
    ]
    transform_to_PIL = torchvision.transforms.ToPILImage()
    cropped_image = transform_to_PIL(cropped_image)
    yield cropped_image


@dataclass
class Taxa:
    gbif_id: int
    name: str | None
    genus: str | None
    family: str | None
    source: str | None


def lookup_gbif_species(species_list_path: str, gbif_id: int) -> Taxa:
    """
    Look up taxa names from a Darwin Core Archive file (DwC-A).

    Example:
    https://docs.google.com/spreadsheets/d/1E3-GAB0PSKrnproAC44whigMvnAkbkwUmwXUHMKMOII/edit#gid=1916842176

    @TODO Optionally look up species name from GBIF API
    Example https://api.gbif.org/v1/species/5231190
    """
    local_path = get_or_download_file(species_list_path, destination_dir="taxonomy")
    df = pd.read_csv(local_path)
    # look up single row by gbif_id
    try:
        row = df.loc[df["taxon_key_gbif_id"] == gbif_id].iloc[0]
    except IndexError:
        logger.error(f"Could not find species with gbif_id {gbif_id}")
        return Taxa(gbif_id=gbif_id, name=str(gbif_id), genus=None, family=None, source=None)

    species = Taxa(
        gbif_id=gbif_id,
        name=row["search_species_name"],
        genus=row["genus_name"],
        family=row["family_name"],
        source=row["source"],
    )

    return species


class StopWatch:
    """
    Measure inference time with GPU support.

    >>> with stopwatch() as t:
    >>>     sleep(5)
    >>> int(t.duration)
    >>> 5
    """

    def __enter__(self):
        synchronize_clocks()
        # self.start = time.perf_counter()
        self.start = time.time()
        return self

    def __exit__(self, type, value, traceback):
        synchronize_clocks()
        # self.end = time.perf_counter()
        self.end = time.time()
        self.duration = self.end - self.start

    def __repr__(self):
        start = datetime.datetime.fromtimestamp(self.start).strftime("%H:%M:%S")
        end = datetime.datetime.fromtimestamp(self.end).strftime("%H:%M:%S")
        seconds = int(round(self.duration, 1))
        return f"Started: {start}, Ended: {end}, Duration: {seconds} seconds"
