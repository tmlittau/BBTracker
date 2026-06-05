from datetime import date
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.diary.models import CheckIn, Pose, ProgressPhoto
from apps.diary.storage import get_storage

pytestmark = pytest.mark.django_db


@pytest.fixture
def user(db):
    return User.objects.create_user(email="a@example.com", password="x")


@pytest.fixture
def other(db):
    return User.objects.create_user(email="b@example.com", password="x")


@pytest.fixture
def api(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


@pytest.fixture
def pose(db):
    return Pose.objects.create(name="Front double biceps", slug="front-double-biceps",
                               view="front", order=1)


def _upload(width=800, height=600, fmt="PNG", color=(90, 20, 20)) -> SimpleUploadedFile:
    buf = BytesIO()
    Image.new("RGB", (width, height), color).save(buf, format=fmt)
    return SimpleUploadedFile("photo.png", buf.getvalue(), content_type=f"image/{fmt.lower()}")


def test_requires_auth():
    assert APIClient().get("/api/v1/diary/photos/").status_code in (401, 403)


# --- Check-ins ---

def test_create_checkin(api, user):
    resp = api.post(
        "/api/v1/diary/check-ins/",
        {"date": "2026-05-31", "bodyweight": "84.5", "energy": 4, "sleep": 3,
         "mood": 5, "motivation": 4, "soreness": 2, "notes": "felt strong"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    assert CheckIn.objects.get(owner=user).bodyweight == pytest.approx(84.5)


def test_duplicate_checkin_date_rejected(api):
    api.post("/api/v1/diary/check-ins/", {"date": "2026-05-31"}, format="json")
    resp = api.post("/api/v1/diary/check-ins/", {"date": "2026-05-31"}, format="json")
    assert resp.status_code == 400


def test_checkin_score_out_of_range_rejected(api):
    resp = api.post(
        "/api/v1/diary/check-ins/", {"date": "2026-05-31", "energy": 9}, format="json"
    )
    assert resp.status_code == 400


def test_checkin_owner_isolation(api, other):
    theirs = CheckIn.objects.create(owner=other, date=date(2026, 5, 31))
    assert api.get(f"/api/v1/diary/check-ins/{theirs.id}/").status_code == 404
    listed = api.get("/api/v1/diary/check-ins/").json()["results"]
    assert theirs.id not in {c["id"] for c in listed}


# --- Photos ---

def test_upload_photo_processes_and_stores(api, user, pose):
    resp = api.post(
        "/api/v1/diary/photos/",
        {"image": _upload(800, 600), "pose": pose.id, "taken_on": "2026-05-31",
         "notes": "week 1"},
        format="multipart",
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["width"] == 800 and body["height"] == 600
    assert body["pose_name"] == "Front double biceps"
    assert body["image_url"].endswith("/image/")
    assert body["thumb_url"].endswith("variant=thumb")
    assert body["content_type"] == "image/jpeg"  # normalised from PNG

    photo = ProgressPhoto.objects.get(id=body["id"])
    # Both objects actually landed in storage.
    assert get_storage().get(photo.object_key)[:2] == b"\xff\xd8"  # JPEG
    assert get_storage().get(photo.thumb_key)[:2] == b"\xff\xd8"


def test_stream_image_full_and_thumb(api, pose):
    pid = api.post(
        "/api/v1/diary/photos/",
        {"image": _upload(1200, 600), "pose": pose.id, "taken_on": "2026-05-31"},
        format="multipart",
    ).json()["id"]

    full = api.get(f"/api/v1/diary/photos/{pid}/image/")
    assert full.status_code == 200
    assert full["Content-Type"] == "image/jpeg"
    full_bytes = b"".join(full.streaming_content) if full.streaming else full.content

    thumb = api.get(f"/api/v1/diary/photos/{pid}/image/?variant=thumb")
    assert thumb.status_code == 200
    assert len(thumb.content) < len(full_bytes)  # thumb is smaller


def test_invalid_image_rejected(api, pose):
    bad = SimpleUploadedFile("x.png", b"not an image", content_type="image/png")
    resp = api.post(
        "/api/v1/diary/photos/",
        {"image": bad, "taken_on": "2026-05-31"},
        format="multipart",
    )
    assert resp.status_code == 400


def test_latest_photo_for_pose(api, pose):
    api.post("/api/v1/diary/photos/",
             {"image": _upload(), "pose": pose.id, "taken_on": "2026-05-01"},
             format="multipart")
    newer = api.post("/api/v1/diary/photos/",
                     {"image": _upload(), "pose": pose.id, "taken_on": "2026-05-20"},
                     format="multipart").json()
    resp = api.get(f"/api/v1/diary/photos/latest/?pose={pose.id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == newer["id"]


def test_latest_empty_when_no_photos(api, pose):
    resp = api.get(f"/api/v1/diary/photos/latest/?pose={pose.id}")
    assert resp.status_code == 200
    assert resp.json() == {}


def test_cannot_stream_others_photo(api, other, pose):
    storage = get_storage()
    storage.put("other/x.jpg", b"\xff\xd8secret", "image/jpeg")
    theirs = ProgressPhoto.objects.create(
        owner=other, pose=pose, taken_on=date(2026, 5, 31),
        object_key="other/x.jpg", thumb_key="", width=10, height=10, bytes=8,
    )
    assert api.get(f"/api/v1/diary/photos/{theirs.id}/image/").status_code == 404


def test_delete_photo_removes_storage_objects(api, pose):
    photo = api.post("/api/v1/diary/photos/",
                     {"image": _upload(), "pose": pose.id, "taken_on": "2026-05-31"},
                     format="multipart").json()
    obj = ProgressPhoto.objects.get(id=photo["id"])
    key, thumb_key = obj.object_key, obj.thumb_key
    assert api.delete(f"/api/v1/diary/photos/{photo['id']}/").status_code == 204
    storage = get_storage()
    with pytest.raises(FileNotFoundError):
        storage.get(key)
    with pytest.raises(FileNotFoundError):
        storage.get(thumb_key)


def test_photo_owner_isolation_list(api, other, pose):
    ProgressPhoto.objects.create(
        owner=other, pose=pose, taken_on=date(2026, 5, 31),
        object_key="other/y.jpg", width=1, height=1, bytes=1,
    )
    listed = api.get("/api/v1/diary/photos/").json()["results"]
    assert listed == []
