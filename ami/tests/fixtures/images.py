import colorsys
import dataclasses
import datetime
import json
import os
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def random_base_color() -> tuple[int, int, int]:
    h = random.random()
    s = random.uniform(0.5, 1.0)
    v = random.uniform(0.5, 1.0)
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def similar_color(base_color: tuple[int, int, int], variation: float = 0.1) -> tuple[int, int, int]:
    r, g, b = base_color
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    h = (h + random.uniform(-variation, variation)) % 1.0
    s = max(0, min(1, s + random.uniform(-variation, variation)))
    v = max(0, min(1, v + random.uniform(-variation, variation)))
    r, g, b = colorsys.hsv_to_rgb(h, s, v)
    return (int(r * 255), int(g * 255), int(b * 255))


def create_background(width: int, height: int) -> Image.Image:
    r = random.randint(220, 240)
    g = random.randint(220, 240)
    b = random.randint(220, 240)
    return Image.new("RGB", (width, height), (r, g, b))


def add_noise(image: Image.Image) -> Image.Image:
    # Add random pixels of noise using numpy. only 1% of pixels will be changed
    # https://stackoverflow.com/questions/42147776/how-to-add-noise-to-an-image-in-python-without-pil
    data = np.array(image)
    mask = np.random.randint(0, 1000, size=data.shape[:2])
    data[mask < 1] = np.random.randint(0, 255, size=(3,))
    return Image.fromarray(data)


def generate_fake_moth(
    image: Image.Image, x: int, y: int, size: int, identifier: str, color: tuple[int, int, int], rotation: float
) -> dict:
    moth_img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    moth_draw = ImageDraw.Draw(moth_img)

    body_width = size // 4
    body_height = size * 2 // 3
    moth_draw.ellipse(
        [
            size // 2 - body_width // 2,
            size // 2 - body_height // 2,
            size // 2 + body_width // 2,
            size // 2 + body_height // 2,
        ],
        fill=similar_color(color),
    )

    head_size = size // 6
    moth_draw.ellipse(
        [
            size // 2 - head_size // 2,
            size // 2 - body_height // 2 - head_size // 2,
            size // 2 + head_size // 2,
            size // 2 - body_height // 2 + head_size // 2,
        ],
        fill=similar_color(color),
    )

    antenna_color = similar_color(color)
    moth_draw.line(
        [size // 2 - head_size // 4, size // 2 - body_height // 2, size // 4, size // 4], fill=antenna_color, width=1
    )
    moth_draw.line(
        [size // 2 + head_size // 4, size // 2 - body_height // 2, 3 * size // 4, size // 4],
        fill=antenna_color,
        width=1,
    )

    wing_color = similar_color(color)
    moth_draw.polygon(
        [
            (size // 2, size // 2 - body_height // 4),
            (0, size // 2),
            (size // 4, 3 * size // 4),
            (size // 2, 2 * size // 3),
            (3 * size // 4, 3 * size // 4),
            (size, size // 2),
        ],
        fill=wing_color,
    )

    # Add identifier
    font = ImageFont.load_default()

    moth_draw.text(
        (size // 2, size // 2),
        identifier,
        fill=(0, 0, 0),
        font=font,
        anchor="mm",
    )

    rotated_moth = moth_img.rotate(rotation, expand=True)

    image.paste(rotated_moth, (x - rotated_moth.width // 2, y - rotated_moth.height // 2), rotated_moth)

    return {
        "identifier": identifier,
        "x": x - rotated_moth.width // 2,
        "y": y - rotated_moth.height // 2,
        "width": rotated_moth.width,
        "height": rotated_moth.height,
        "rotation": rotation,
    }


@dataclasses.dataclass
class BoundingBoxWithIdentifier:
    identifier: str
    bbox: tuple[float, float, float, float]


@dataclasses.dataclass
class GeneratedTestFrame:
    series_id: str
    width: int
    height: int
    timestamp: datetime.datetime
    image: Image.Image
    filename: str
    bounding_boxes: list[BoundingBoxWithIdentifier]
    object_store_key: str | None = None


def generate_moth_series(
    num_frames: int = 3,
    width: int = 1024,
    height: int = 768,
    num_moths: int | None = None,
    beginning_timestamp: datetime.datetime | None = None,
    minutes_interval: int = 90,
    minutes_interval_variation: int = 10,
    save_images: bool = True,
    output_dir: str = "generated_test_captures",
) -> list[GeneratedTestFrame]:
    background = create_background(width, height)
    moths = []
    image_data = []

    num_moths = num_moths or random.randint(2, 8)

    # pick random day, start at 10pm in the last 10 years
    if beginning_timestamp is None:
        beginning_timestamp = datetime.datetime.now().replace(
            hour=22, minute=0, second=0, microsecond=0
        ) - datetime.timedelta(days=random.randint(0, 365 * 10))

    # use the starting day for the series as the series id
    series_id = beginning_timestamp.strftime("%Y-%m-%d")

    # Generate unique identifiers
    # identifiers = ["".join(random.choices(string.ascii_uppercase + string.digits, k=2)) for _ in range(num_moths)]
    # The font is very hard to read, so replace with a simple number repeated 3 times
    identifiers = [f"{i}{i}{i}" for i in range(num_moths)]

    # Initialize moths
    for i in range(num_moths):
        size = random.randint(30, 60)
        x = random.randint(size // 2, width - size // 2)
        y = random.randint(size // 2, height - size // 2)
        color = random_base_color()
        rotation = random.uniform(0, 360)
        moths.append(
            {"identifier": identifiers[i], "size": size, "x": x, "y": y, "color": color, "rotation": rotation}
        )

    for frame in range(num_frames):
        timestamp = beginning_timestamp + datetime.timedelta(minutes=frame * minutes_interval)
        timestamp += datetime.timedelta(
            minutes=random.randint(-minutes_interval_variation, minutes_interval_variation)
        )
        image = background.copy()
        bounding_boxes = []

        for moth in moths:
            # Update position and rotation
            # Add multiply factor based on interval minutes to make movement more noticeable. min is 1, max is 120.
            mult_factor = max(minutes_interval / 120, 1) + 2
            # moth["x"] += random.randint(-10, 10)
            # moth["y"] += random.randint(-10, 10)
            # moth["rotation"] += random.uniform(-15, 15)
            moth["x"] += int(random.randint(-10, 10) * mult_factor)
            moth["y"] += int(random.randint(-10, 10) * mult_factor)
            moth["rotation"] += int(random.uniform(-15, 15) * mult_factor)

            # Ensure moth stays within frame
            moth["x"] = max(moth["size"] // 2, min(width - moth["size"] // 2, moth["x"]))
            moth["y"] = max(moth["size"] // 2, min(height - moth["size"] // 2, moth["y"]))

            moth_data = generate_fake_moth(
                image, moth["x"], moth["y"], moth["size"], moth["identifier"], moth["color"], moth["rotation"]
            )
            moth_bbox = (
                moth_data["x"],
                moth_data["y"],
                (moth_data["x"] + moth_data["width"]),
                (moth_data["y"] + moth_data["height"]),
            )
            bounding_boxes.append(BoundingBoxWithIdentifier(moth["identifier"], moth_bbox))

        image = add_noise(image)

        image_filename = f"session_{series_id}_capture_{timestamp.strftime('%Y%m%d%H%M%S')}.jpg"

        frame_data = GeneratedTestFrame(
            series_id=series_id,
            width=width,
            height=height,
            timestamp=timestamp,
            filename=image_filename,
            bounding_boxes=bounding_boxes,
            image=image,
        )

        if save_images:
            # Make sure the output directory exists
            os.makedirs(output_dir, exist_ok=True)
            image_filepath = os.path.join(output_dir, image_filename)
            image.save(image_filepath)

        image_data.append(frame_data)

    return image_data


def generate_multiple_series(
    num_series: int,
    frames_per_series: int,
    width: int = 800,
    height: int = 600,
    min_moths: int = 2,
    max_moths: int = 8,
) -> None:
    all_series_data = []
    for _i in range(num_series):
        num_moths = random.randint(min_moths, max_moths)
        series_data = generate_moth_series(frames_per_series, width, height, num_moths)
        all_series_data.extend(series_data)

    with open("image_data.json", "w") as f:
        json.dump(all_series_data, f, indent=2)


if __name__ == "__main__":
    generate_multiple_series(num_series=3, frames_per_series=10)  # Generate 3 series with 10 frames each
