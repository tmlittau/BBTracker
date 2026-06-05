"""Pure image processing for progress photos (Pillow).

Two responsibilities, both privacy/consistency related:
* `process_image` — validate it's a real image, apply EXIF orientation then DROP
  all EXIF (strips GPS/camera metadata), normalise to JPEG. Returns clean bytes +
  dimensions.
* `make_thumbnail` — a small JPEG for grids/ghost-overlay.

Pure functions (bytes in, bytes out) so they unit-test without storage or the ORM.
"""
from __future__ import annotations

from io import BytesIO

from PIL import Image, ImageOps, UnidentifiedImageError

JPEG_QUALITY = 88
THUMB_MAX_PX = 400
MAX_DIMENSION = 4000  # downscale enormous uploads


class InvalidImageError(ValueError):
    """Raised when uploaded bytes are not a decodable image."""


def _load(raw: bytes) -> Image.Image:
    try:
        img = Image.open(BytesIO(raw))
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImageError("Not a valid image file.") from exc
    return img


def process_image(raw: bytes) -> tuple[bytes, int, int]:
    """Return (clean_jpeg_bytes, width, height) with EXIF stripped + orientation applied."""
    img = _load(raw)
    # Apply the camera's EXIF orientation, then the re-save drops EXIF entirely.
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    if max(img.size) > MAX_DIMENSION:
        img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=JPEG_QUALITY)  # no exif= → metadata stripped
    return buf.getvalue(), img.width, img.height


def make_thumbnail(raw: bytes, max_px: int = THUMB_MAX_PX) -> bytes:
    """Return a small JPEG thumbnail (longest side ≤ max_px)."""
    img = _load(raw)
    img = ImageOps.exif_transpose(img)
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    img.thumbnail((max_px, max_px))
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=80)
    return buf.getvalue()
