"""Pure image-processing tests — generate images in-memory, no storage/ORM."""
from io import BytesIO

import pytest
from PIL import Image

from apps.diary.images import (
    InvalidImageError,
    make_thumbnail,
    process_image,
)


def _png(width=800, height=600, color=(120, 30, 30)) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format="PNG")
    return buf.getvalue()


def _jpeg_with_exif(width=1000, height=500) -> bytes:
    # A plain JPEG; Pillow won't attach EXIF unless asked, so we inject an
    # orientation tag to prove process_image drops it.
    buf = BytesIO()
    img = Image.new("RGB", (width, height), (10, 10, 10))
    exif = img.getexif()
    exif[274] = 6  # Orientation = rotate 90°
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue()


class TestProcessImage:
    def test_returns_jpeg_and_dimensions(self):
        clean, w, h = process_image(_png(800, 600))
        assert (w, h) == (800, 600)
        # Output is JPEG (starts with the JPEG SOI marker).
        assert clean[:2] == b"\xff\xd8"

    def test_strips_exif(self):
        clean, _, _ = process_image(_jpeg_with_exif())
        reloaded = Image.open(BytesIO(clean))
        # No EXIF / no orientation tag survives the re-encode.
        assert dict(reloaded.getexif()) == {}

    def test_applies_exif_orientation_then_drops_it(self):
        # Orientation 6 means the stored 1000×500 should become 500×1000 once applied.
        clean, w, h = process_image(_jpeg_with_exif(1000, 500))
        assert (w, h) == (500, 1000)

    def test_downscales_huge_images(self):
        clean, w, h = process_image(_png(6000, 3000))
        assert max(w, h) <= 4000

    def test_rejects_non_image(self):
        with pytest.raises(InvalidImageError):
            process_image(b"this is not an image")


class TestThumbnail:
    def test_thumbnail_is_small_jpeg(self):
        thumb = make_thumbnail(_png(2000, 1000), max_px=400)
        img = Image.open(BytesIO(thumb))
        assert max(img.size) <= 400
        assert thumb[:2] == b"\xff\xd8"

    def test_thumbnail_smaller_than_original(self):
        original = _png(2000, 1000)
        assert len(make_thumbnail(original)) < len(original)
