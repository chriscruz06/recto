"""Reading and writing PNGs without OpenCV touching the filesystem.

cv2.imwrite and cv2.imread hand the path down to a C++ layer that cannot open
a filename containing non-ASCII characters on Windows, and they report the
failure by returning False or None rather than raising. Encoding in memory and
moving the bytes through pathlib avoids both behaviours, so every image read
and write in the codebase goes through here.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np


def write_png(path: Path, image: np.ndarray) -> None:
    """Write an image as PNG, creating parent directories as needed."""
    ok, buffer = cv2.imencode(".png", image)
    if not ok:
        raise RuntimeError(f"could not encode {path.name} as PNG")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(buffer.tobytes())


def read_png(path: Path, *, greyscale: bool = True) -> np.ndarray:
    """Read a PNG, greyscale by default."""
    flag = cv2.IMREAD_GRAYSCALE if greyscale else cv2.IMREAD_COLOR
    data = np.frombuffer(path.read_bytes(), dtype=np.uint8)
    image = cv2.imdecode(data, flag)
    if image is None:
        raise RuntimeError(f"could not decode {path}")
    return image
